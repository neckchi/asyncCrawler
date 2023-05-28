from src.main.crawler_modal.async_crawler import *
from src.main.logger_factory.logger import LoggerFactory
from src.main.schemas.service_loops import Services
from src.main.carrier_services.helpers import order_counter,split_list_of_dicts,find_dictionaries_by_value
from src.main.crawler_modal.csv_operation import FileManager
from src.main.schemas import settings
from datetime import datetime,timedelta
import orjson  #Orjson is built in C, its performing way better than python built in json
import calendar
import uuid
import concurrent.futures
import functools
import time
import csv

carrier: str = 'hdmu'
logger = LoggerFactory.get_logger(__name__, log_level="INFO")

def find_dictionaries_by_values(lst:list,key:str,value:str) ->dict:
    result:list = []
    for d in lst:
        if d.get(key) == value:
            etd = calendar.day_abbr[datetime.strptime(d['etdDt'], '%Y%m%d%H%M').weekday()]
            eta = calendar.day_abbr[datetime.strptime(d['etbDt'], '%Y%m%d%H%M').weekday()]
            result.append({'etd':etd,'eta':eta})
    return result[-1]

def hyundai_mapping(crawler_result: list,network_results:list,lookup_network:list, writer: csv.DictWriter):

    for service_url, service_route in zip(network_results, crawler_result):
        direction_lookup: dict = {'N': 'NORTHBOUND', 'S': 'SOUTHBOUND', 'E': 'EASTBOUND', 'W': 'WESTBOUND'}
        service_code: str = str(service_url).split('srchByLoopOptLoop=', 1)[1][:3]
        service_name:str = find_dictionaries_by_value(lst=lookup_network,key='service_code',value=service_code)[0].get('service_name')
        vessel_voyage = orjson.loads(service_route.text).get('vskSkdDtls')
        if vessel_voyage:
            route: list = orjson.loads(service_route.text)['hdrList']
            route_with_direction = split_list_of_dicts(route, 'skdDirCd')
            for key, value in route_with_direction.items():
                direction_code = key
                direction = direction_lookup.get(direction_code, 'UNKNOWN')
                for port_sequence, port_route in enumerate(value):
                    port_code = port_route.get('portCd')
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
                    match_result = find_dictionaries_by_values(vessel_voyage, 'portCd', port_code)
                    pol: Services = Services(**common,
                                             startDay=match_result['eta'].upper(),
                                             tt=0,
                                             order=order_counter(port_sequence, 'L'),
                                             locationType='L')
                    writer.writerow(pol.dict())
                    pod: Services = Services(**common,
                                             startDay=match_result['etd'].upper(),
                                             tt=0,
                                             order=order_counter(port_sequence, 'D'),
                                             locationType='D')
                    writer.writerow(pod.dict())

async def hyundai_crawler():
    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    with FileManager(mode='w', scac=f'{carrier}') as writer:
        service_network = Crawler(
            crawler_type='API',
            method='POST',
            sleep=None,
            urls=[settings.hdmu_service_url],
            workers=5,
            limit=10,
        )
        await service_network.run()
        service_network_result:list = [{'service_code':str(data.get('optCd')).split('#',1)[1], 'service_name': str(data.get('optNm'))}for service_group in service_network.result for data in orjson.loads(service_group.text)['RTN_JSON3']]
        now:datetime = datetime.now()
        date_from: str = now.strftime("%Y%m%d")
        date_to:str = (now + timedelta(days= 120)).strftime("%Y%m%d")
        service_routing_url:list =[settings.hdmu_route_url.format(loop=dict(result).get('service_code'),date_from=date_from,date_to=date_to) for result in service_network_result]

        services_seen = sorted(service_network.seen)
        logger.info("Service Network Results:")
        for url in services_seen:
            logger.info(url)
        logger.info(f"Service Network Crawled: {len(service_network.done)} URLs")
        logger.info(f"Service Network Processed: {len(services_seen)} URLs")

        service_routing = Crawler(
            crawler_type='API',
            method='POST',
            sleep=4,
            urls=service_routing_url,
            workers=5,
            limit=10,
        )
        await service_routing.run()

        # Using additional thread to speed up the entire processing for FileOperationIO task
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool, functools.partial(hyundai_mapping, crawler_result=service_routing.result,network_results=service_routing.done,lookup_network = service_network_result, writer=writer))

        services_routing_seen = sorted(service_routing.seen)
        logger.info("Service Routing Results:")
        for url in services_routing_seen:
            logger.info(url)
        logger.info(f"Service Routing Crawled: {len(service_routing.done)} URLs")
        logger.info(f"Service Routing Processed: {len(services_routing_seen)} URLs")
        logger.info(f"Anything pending?: {result}")
        end = time.perf_counter()

        logger.info(f"Done in {end - start:.2f}s")



# asyncio.get_event_loop().run_until_complete(hyundai_crawler())

# asyncio.run(hyundai_crawler(),debug=True)