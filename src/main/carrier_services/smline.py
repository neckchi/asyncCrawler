from src.main.crawler_modal.async_crawler import *
from src.main.carrier_services.helpers import order_counter,split_list_of_dicts,find_dictionaries_by_value
from src.main.crawler_modal.csv_operation import FileManager
from src.main.schemas.service_loops import Services
from src.main.schemas import settings
import concurrent.futures
import asyncio
import orjson
import csv
import functools
import uuid

carrier: str = 'smlm'
logger = LoggerFactory.get_logger(__name__, log_level="INFO")
def smline_mapping(crawler_result: list,network_results:list,lookup_network:list, writer: csv.DictWriter):
    for service,routing in zip(network_results,crawler_result):
        service_code:str = service.split('vsl_slan_cd=',1)[1]
        service_name:str = find_dictionaries_by_value(lst = lookup_network,key='service_code',value=service_code)[0].get('service_name')
        routing_list:list = orjson.loads(routing.text)['list']
        routing_direction = split_list_of_dicts(lst=routing_list,key='skdDirCd')
        for direction_code,rotation_list in routing_direction.items():
            direction_lookup: dict = {'N': 'NORTHBOUND', 'S': 'SOUTHBOUND', 'E': 'EASTBOUND', 'W': 'WESTBOUND'}
            direction:str = direction_lookup.get(direction_code, 'UNKNOWN')
            for port_sequence,rotation in enumerate(rotation_list):
                port_code:str = rotation['portCd']
                common: dict = {'changeMode': None, 'allianceID': None, 'alliancePoolID': None,
                                'tradeID': None,
                                'oiServiceID': ''.join([service_code, carrier.upper()]),
                                'carrierID': carrier.upper(),
                                'serviceID': service_code + ' ' + ''.join(['[', direction_code, ']']),
                                'service': service_name,
                                'direction': direction,
                                'frequency': 'WEEKLY',
                                'portCode': port_code,
                                'relatedID': uuid.uuid5(uuid.NAMESPACE_DNS,f'{carrier.upper()}-{service_code}-{direction}')}

                pol: Services = Services(**common,
                                         startDay='SUN',
                                         tt=0,
                                         order=order_counter(port_sequence, 'L'),
                                         locationType='L')
                writer.writerow(pol.dict())
                pod: Services = Services(**common,
                                         startDay='SUN',
                                         tt=0,
                                         order=order_counter(port_sequence, 'D'),
                                         locationType='D')
                writer.writerow(pod.dict())


async def smline_crawler():
    loop = asyncio.get_running_loop()
    with FileManager(mode='w', scac=f'{carrier}') as writer:
        extra_header:dict = {'Host':settings.smlm_host,'Origin':settings.smlm_origin,'Referer':settings.smlm_referer}
        service_network = Crawler(
            crawler_type='API',
            method='GET',
            sleep=5,
            urls=[settings.smlm_service_url.format(network = network_code) for network_code in ['AA','MN']],
            specific_headers=extra_header,
            workers=3,
            limit=100,
        )
        await service_network.run()

        service_network_set:list =[{'service_code':data['vslSlanCd'],'service_name':data['vslSlanNm']} for services in service_network.result for data in orjson.loads(services.text)['list']]
        service_routing_urls:list = [settings.smlm_route_url.format(service=service['service_code']) for service in service_network_set]

        service_network.logging_url(task_name='SM Line Service Network')


        service_routing = Crawler(
            crawler_type='API',
            method='GET',
            sleep=6,
            urls=service_routing_urls,
            specific_headers=extra_header,
            workers=5,
            limit=1000,
        )
        await service_routing.run()

        # Using additional thread to speed up the entire processing for FileOperationIO task
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool, functools.partial(smline_mapping, crawler_result=service_routing.result,
                                        network_results=service_routing.done, lookup_network=service_network_set,writer=writer))

        service_routing.logging_url(task_name='SM Line Service Routing')


