from crawler_modal.async_crawler import *
from crawler_modal.csv_operation import FileManager
from schemas.service_loops import Services
from logger_factory.logger import LoggerFactory
from carrier_services.helpers import order_counter
from schemas import settings
import time
import itertools
import csv
import uuid
import concurrent.futures
import functools

carrier: str = 'eglv'
logger = LoggerFactory.get_logger(__name__, log_level="INFO")

def check_extended(service_list: list, element: str):
    return [index for index, value in enumerate(service_list, start=0) if index >= 0 and value == element]

def evergreen_mapping(crawler_result: list,network_results:list, writer: csv.DictWriter):
    direction_lookup: dict = {'N': 'NORTHBOUND', 'S': 'SOUTHBOUND', 'E': 'EASTBOUND', 'W': 'WESTBOUND'}

    for index, (srr,direct) in enumerate(zip(crawler_result,network_results), start=1):
        if srr:
            service_code = srr[0]
            direction_code = direct[-1]
            direction: str = direction_lookup.get(direction_code, 'UNKNOWN')
            extended_port = list(itertools.chain(*[itertools.takewhile(lambda x: x != 'ETA', srr[ep + 1::]) for ep in check_extended(srr, service_code)]))
            extended_eta = list(itertools.chain(*[itertools.takewhile(lambda x: x != 'ETD', srr[eta + 1::]) for eta in check_extended(srr, 'ETA')]))
            extended_etd = list(itertools.chain(*[itertools.takewhile(lambda x: x != 'T/S TIME', srr[etd + 1::]) for etd in check_extended(srr, 'ETD')]))
            extended_tss = list(itertools.chain(*[itertools.takewhile(lambda x: x != service_code, srr[tss + 1::]) for tss in check_extended(srr, 'T/S TIME')]))
            for port_sequence, (port, eta, etd, tss) in enumerate(zip(extended_port, extended_eta, extended_etd, extended_tss)):
                common: dict = {'changeMode': None, 'allianceID': None, 'alliancePoolID': None,
                                'tradeID': None,
                                'oiServiceID': ''.join([service_code, carrier.upper()]),
                                'carrierID': carrier.upper(),
                                'serviceID': service_code + ' ' + ''.join(['[', 'U' if direction_code == '9' else direction_code, ']']),
                                'service': service_code,
                                'direction': direction,
                                'frequency': 'WEEKLY',
                                'portCode': port,
                                'relatedID': uuid.uuid5(uuid.NAMESPACE_DNS,f'{carrier.upper()}-{service_code}-{direction}')}
                if eta is not None:
                    pol: Services = Services(**common,
                                             startDay=eta.upper(),
                                             tt=tss,
                                             order=order_counter(port_sequence, 'L'),
                                             locationType='L')
                    writer.writerow(pol.dict())
                if etd is not None:
                    pod: Services = Services(**common,
                                             startDay=etd.upper(),
                                             tt=tss,
                                             order=order_counter(port_sequence, 'D'),
                                             locationType='D')
                    writer.writerow(pod.dict())
        else:
            pass


async def evergreen_crawler():
    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    with FileManager(mode = 'w',scac=f'{carrier}') as writer:
        logger.info(f'Created CSV header for {carrier}')
        service_network = Crawler(
            crawler_type='Web',
            parent_element='td',
            html_class=["f12rown1"],
            next_element='ahref',
            urls=[settings.eglv_service_url],
            workers=5,
            limit=10,
        )
        await service_network.run()
        network_results: list = [service for service in service_network.result if str(service).startswith('/tvs2/jsp/')]

        services_seen = sorted(service_network.seen)
        logger.info("Service Network Results:")
        for url in services_seen:
            logger.info(url)
        logger.info(f"Service Network Crawled: {len(service_network.done)} URLs")
        logger.info(f"Service Network Processed: {len(services_seen)} URLs")

        service_routing = Crawler(
            crawler_type='Web',
            parent_element='td',
            html_class=["f09tilb1", "f09rown2"],
            next_element='td',
            urls=[settings.eglv_route_url.format(result) for result in network_results],
            sleep=5,
            workers=5,
            limit=100,
        )
        await service_routing.run()

        # Using additional thread to speed up the entire processing for FileOperationIO task
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool, functools.partial(evergreen_mapping, crawler_result=service_routing.result,network_results=service_routing.done, writer=writer))

        services_routing_seen = sorted(service_routing.seen)
        logger.info("Service Routing Results:")
        for url in services_routing_seen:
            logger.info(url)
        logger.info(f"Service Routing Crawled: {len(service_routing.done)} URLs")
        logger.info(f"Service Routing Processed: {len(services_routing_seen)} URLs")
        logger.info(f"Anything pending?: {result}")
        end = time.perf_counter()

        logger.info(f"Done in {end - start:.2f}s")

