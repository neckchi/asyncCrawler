from src.main.crawler_modal.async_crawler import *
from src.main.carrier_services.helpers import order_counter,find_dictionaries_by_value,split_list_of_dicts
from src.main.crawler_modal.csv_operation import FileManager
from src.main.schemas.service_loops import Services
from src.main.schemas import settings
import orjson #Orjson is built in RUST, its performing way better than python in built json
import uuid
import concurrent.futures
import functools
import csv
import calendar

carrier: str = 'cmdu'
logger = LoggerFactory.get_logger(__name__, log_level="INFO")
def cma_mapping(crawler_result: list,network_results:list,lookup_network:list, writer: csv.DictWriter):
    carrier_code:dict = {'0001': 'CMDU', '0002': 'ANNU','0011': 'CHNL', '0014': 'CSFU', '0015': 'APLU'}
    direction_dict:dict = {'NORTH': 'NORTHBOUND', 'SOUTH': 'SOUTHBOUND', 'EAST': 'EASTBOUND',
                      'WEST': 'WESTBOUND','ROUND':'ROUND'}
    for url,routing in zip(network_results,crawler_result):
        service_code:str = str(url).split('/')[-2]
        lookup_service_network:dict = find_dictionaries_by_value(lst =lookup_network,key='service_code',value=service_code)[0]
        for carrier_service in lookup_service_network['carriers']:
            scac:str = carrier_code.get(carrier_service['shipcomp'],'UNKNOWN')
            service_code = carrier_service['code']
            service_name = lookup_service_network['service_name']
            for key,value in split_list_of_dicts(lst=routing,key='bound').items():
                direction: str = direction_dict.get(key, 'UNKNOWN')
                direction_code:str = direction[0]
                for port_sequence,port_rotation in enumerate(value):
                    port_code:str = port_rotation['port']['code']
                    transit_time:int = int(port_rotation['transitTime'])
                    day:str = calendar.day_abbr[transit_time % 7]
                    common: dict = {'changeMode': None, 'allianceID': None, 'alliancePoolID': None,
                                    'tradeID': None,
                                    'oiServiceID': ''.join([service_code, scac.upper()]),
                                    'carrierID': scac.upper(),
                                    'serviceID': service_code + ' ' + ''.join(['[', direction_code, ']']),
                                    'service': service_name,
                                    'direction': direction,
                                    'frequency': 'WEEKLY',
                                    'portCode': port_code,
                                    'relatedID': uuid.uuid5(uuid.NAMESPACE_DNS,f'{carrier.upper()}-{service_code}-{direction}')}
                    pol: Services = Services(**common,
                                             startDay=day.upper(),
                                             tt=transit_time,
                                             order=order_counter(port_sequence, 'L'),
                                             locationType='L')
                    writer.writerow(pol.dict())
                    pod: Services = Services(**common,
                                             startDay=day.upper(),
                                             tt=transit_time,
                                             order=order_counter(port_sequence, 'D'),
                                             locationType='D')
                    writer.writerow(pod.dict())
async def cma_crawler():
    loop = asyncio.get_running_loop()
    with FileManager(mode='w', scac=f'{carrier}') as writer:
        all_services:set = set()
        for n in range(0, 700, 50):
            n = f"{n}-{n + 49}"
            service_network = Crawler(
                crawler_type='API',
                method='GET',
                sleep=1,
                urls=[settings.cmdu_service_url],
                specific_headers= {'range': n,'KeyId': settings.cmdu_api_key.get_secret_value()},
                workers=4,
                limit=10000,
            )
            await service_network.run()
            for service in service_network.result:
                if service.status_code in (200,206):
                    all_services.add(service)
            # all_services.add(*service_network.result)
            service_network.logging_url(task_name='CMA CGM Service Network Group')
        service_network_result:list = [{'service_code':data['code'],'service_name':data['name'],'departure_dat':data['departureDay'],'carriers':data['carriers']} for sn in all_services for data in orjson.loads(sn.read())]



        service_routing = Crawler(
            crawler_type='API',
            method='GET',
            sleep=1,
            urls=[settings.cmdu_route_url.format(loop=network['service_code']) for network in service_network_result],
            specific_headers= {'range': '0-49','KeyId': settings.cmdu_api_key.get_secret_value()},
            workers=6,
            limit=100000,
        )
        await service_routing.run()
        service_routing_result:list = [orjson.loads(routing.read()) for routing in service_routing.result]

        # Using additional thread to speed up the entire processing for FileOperationIO task
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool, functools.partial(cma_mapping, crawler_result=service_routing_result, network_results=service_routing.done,lookup_network = service_network_result, writer=writer))
        service_routing.logging_url(task_name='CMA CGM Service Routing')
