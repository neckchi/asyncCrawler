from src.main.crawler_modal.async_crawler import *
from src.main.crawler_modal.csv_operation import FileManager
from src.main.schemas import settings
from src.main.schemas.service_loops import Services
from src.main.carrier_services.helpers import order_counter
import asyncio
import re
import itertools
import datetime
import calendar
import csv
import uuid
import concurrent.futures
import functools

carrier: str = 'ymlu'
logger = LoggerFactory.get_logger(__name__, log_level="INFO")

def yangming_mapping(crawler_result: list,network_results:list, writer: csv.DictWriter):
    direction_lookup: dict = {'N': 'NORTHBOUND', 'S': 'SOUTHBOUND', 'E': 'EASTBOUND', 'W': 'WESTBOUND'}
    for link, routing in zip(network_results, crawler_result):
        # date_regrex = re.compile(r"(.*\d{2}/\d{2})")
        # if routing and len(routing) > 0 and list(filter(date_regrex.match, routing)):
        if routing:
            # location_string: str = str(routing[0]).split('Comn Voy.', 1)[1] if date_regrex.search(routing[1]) else str(routing[1]).split('Comn Voy.', 1)[1]
            location_string: str = str(routing[0]).split('Comn Voy.', 1)[1]
            location_list: list = [location_string[i:i + 5] for i in range(0, len(location_string), 5)]
            # vessel_voyage: list = re.split(r"(\d{2}/\d{2})", str(routing[1])) if date_regrex.search(routing[1]) else re.split(r"(\d{2}/\d{2})", str(routing[2]))
            service_code = str(link).split('svc=', 1)[1][:3]
            direction_code: str = link[-1]
            direction: str = direction_lookup.get(direction_code, 'UNKNOWN')
            # transit_date: list = [transit_date for transit_date in vessel_voyage if date_regrex.search(transit_date)]
            # transit_day: list = [calendar.day_abbr[datetime.date(month=int(ttd[1:2]), day=int(ttd[3::]),year=datetime.date.today().year).weekday()] for ttd in transit_date]
            # first_transit_date = datetime.datetime.strptime(transit_date[0], "%m/%d")
            # transit_diff = [abs((datetime.datetime.strptime(trd, "%m/%d") - first_transit_date).days) for trd in transit_date]
            for port_sequence,port in enumerate(location_list):
                common: dict = {'changeMode': None, 'allianceID': None, 'alliancePoolID': None,
                                'tradeID': None,
                                'oiServiceID': ''.join([service_code, carrier.upper()]),
                                'carrierID': carrier.upper(),
                                'serviceID': service_code + ' ' + ''.join(['[', direction_code, ']']),
                                'service': service_code,
                                'direction': direction,
                                'frequency': 'WEEKLY',
                                'portCode': port,
                                'relatedID': uuid.uuid5(uuid.NAMESPACE_DNS,f'{carrier.upper()}-{service_code}-{direction}')}
                pol: Services = Services(**common,
                                         # startDay=transit_day[0+port_sequence*2].upper(),
                                         # tt=transit_diff[0+port_sequence*2],
                                         startDay= 'SUN',
                                         tt = 0,
                                         order=order_counter(port_sequence, 'L'),
                                         locationType='L')
                writer.writerow(pol.dict())
                pod: Services = Services(**common,
                                         # startDay=transit_day[1+port_sequence*2].upper(),
                                         # tt=transit_diff[1+port_sequence*2],
                                         startDay='SUN',
                                         tt=0,
                                         order=order_counter(port_sequence, 'D'),
                                         locationType='D')
                writer.writerow(pod.dict())
        else:
            pass

async def yangming_crawler():
    loop = asyncio.get_running_loop()
    with FileManager(mode='w', scac=f'{carrier}') as writer:
        logger.info(f'Created CSV header for {carrier}')
        service_network = Crawler(
            crawler_type='Web',
            parent_element='select',
            html_id=["ContentPlaceHolder1_ddlSearchName"],
            next_element='option',
            urls=[settings.ymlu_service_url],
            workers=3,
            limit=10000,
        )
        await service_network.run()


        service_codes:list = list(str(service_network.result[0]).split('\\n'))
        service_network_results:list = [service_code for service_code in service_codes if len(service_code) ==3]
        service_directions:list = list(itertools.product(service_network_results,['W','S','E','N']))
        service_direction_url:list = [settings.ymlu_route_url.format(service=srs[0],direction=srs[1]) for srs in service_directions]
        service_network.logging_url(task_name='YangMing Service Network')

        service_routing = Crawler(
            crawler_type='Web',
            method='GET',
            parent_element='tr',
            # html_class=['sche_field_name','sche_field_odd'],
            html_class=['sche_field_name'],
            next_element='td',
            sleep=5,
            urls=service_direction_url,
            workers=3,
            limit=5000,
        )

        await service_routing.run()
        print(f'Done:{service_routing.done}')

        # Using additional thread to speed up the entire processing for FileOperationIO task
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool, functools.partial(yangming_mapping, crawler_result=service_routing.result,network_results=service_routing.done, writer=writer))

        service_routing.logging_url(task_name='YangMing Service Routing')
