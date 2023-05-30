from src.main.crawler_modal.async_crawler import *
from src.main.crawler_modal.csv_operation import FileManager
from src.main.schemas.service_loops import Services
from src.main.carrier_services.helpers import order_counter,find_dictionaries_by_value
from src.main.schemas import settings
import itertools
import csv
import uuid
import concurrent.futures
import functools
import ast
import urllib.parse


carrier: str = 'eglv'
logger = LoggerFactory.get_logger(__name__, log_level="INFO")

def check_extended(service_list: list, element: str):
    return [index for index, value in enumerate(service_list, start=0) if index >= 0 and value == element]


def location_mapping(location_string:str):
    # Replace \x with % and split the string by newline character
    list_strings:list = location_string.replace('\\x', '%').split('\n')
    result:list = []
    for ls in list_strings:
        # Skip empty strings
        if ls == '':
            continue
        # Convert string to list
        list_data = ast.literal_eval(ls)
        # Decode URL-encoded components in the list
        decoded_list:list = [[urllib.parse.unquote(element) for element in sublist] for sublist in list_data]
        result.append(decoded_list)
    final_result = list(itertools.chain(*result))
    return final_result

def evergreen_mapping(crawler_result: list,network_results:list,lookup_network:list,lookup_location:list,writer: csv.DictWriter):
    direction_lookup: dict = {'N': 'NORTHBOUND', 'S': 'SOUTHBOUND', 'E': 'EASTBOUND', 'W': 'WESTBOUND'}

    for index, (srr,direct) in enumerate(zip(crawler_result,network_results), start=1):
        if srr:
            service_code:str = srr[0]
            direction_code:str = direct[-1]
            service_name:str = find_dictionaries_by_value(lst=lookup_network,key='a_link',value=f'/tvs2/jsp/TVS2_ServiceProfile.jsp?line={service_code}&segment={direction_code}')[0].get('a_text',service_code)
            direction: str = direction_lookup.get(direction_code, 'UNKNOWN')
            extended_port = list(itertools.chain(*[itertools.takewhile(lambda x: x != 'ETA', srr[ep + 1::]) for ep in check_extended(srr, service_code)]))
            extended_eta = list(itertools.chain(*[itertools.takewhile(lambda x: x != 'ETD', srr[eta + 1::]) for eta in check_extended(srr, 'ETA')]))
            extended_etd = list(itertools.chain(*[itertools.takewhile(lambda x: x != 'T/S TIME', srr[etd + 1::]) for etd in check_extended(srr, 'ETD')]))
            extended_tss = list(itertools.chain(*[itertools.takewhile(lambda x: x != service_code, srr[tss + 1::]) for tss in check_extended(srr, 'T/S TIME')]))
            for port_sequence, (port, eta, etd, tss) in enumerate(zip(extended_port, extended_eta, extended_etd, extended_tss)):
                un_location_code:str = find_dictionaries_by_value(lst = lookup_location,key='location_name',value=port)[0].get('location_code')
                common: dict = {'changeMode': None, 'allianceID': None, 'alliancePoolID': None,
                                'tradeID': None,
                                'oiServiceID': ''.join([service_code, carrier.upper()]),
                                'carrierID': carrier.upper(),
                                'serviceID': service_code + ' ' + ''.join(['[', 'U' if direction_code == '9' else direction_code, ']']),
                                'service': service_name,
                                'direction': direction,
                                'frequency': 'WEEKLY',
                                'portCode': un_location_code if un_location_code not in ('UNKNOWN','A6%5d','35%5d') else f'TBA - {port}',
                                'relatedID': uuid.uuid5(uuid.NAMESPACE_DNS,f'{carrier.upper()}-{service_code}-{direction}')}
                if eta is not None:
                    pol: Services = Services(**common,
                                             startDay=eta.upper(),
                                             tt=tss if tss else 0,
                                             order=order_counter(port_sequence, 'L'),
                                             locationType='L')
                    writer.writerow(pol.dict())
                if etd is not None:
                    pod: Services = Services(**common,
                                             startDay=etd.upper(),
                                             tt=tss if tss else 0,
                                             order=order_counter(port_sequence, 'D'),
                                             locationType='D')
                    writer.writerow(pod.dict())
        else:
            pass


async def evergreen_crawler():
    loop = asyncio.get_running_loop()
    with FileManager(mode = 'w',scac=f'{carrier}') as writer:
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
        network_results: list = [service for service in service_network.result if str(service['a_link']).startswith('/tvs2/jsp/')]

        service_network.logging_url(task_name='Evergreen Service Network')

        service_routing = Crawler(
            crawler_type='Web',
            parent_element='td',
            html_class=["f09tilb1", "f09rown2"],
            next_element='td',
            urls=[settings.eglv_route_url.format(result['a_link']) for result in network_results],
            sleep=4,
            workers=5,
            limit=5000,
        )
        await service_routing.run()

        location_name:set = set(itertools.chain(*[itertools.takewhile(lambda x: x != 'ETA', loc[ep + 1::])for loc in service_routing.result for ep in check_extended(loc, loc[0])]))

        call_location_code = Crawler(
            crawler_type='API',
            method='GET',
            sleep=1,
            urls=[settings.eglv_location_url.format(port=loc_name) for loc_name in location_name],
            workers=5,
            limit=20000,
        )

        await call_location_code.run()

        location_set:list[dict] = [{'location_code':str(location_mapping(location_string=location_code.text)[0][0]).split('%29%20%5b',1)[0][-5:] if location_mapping(location_string=location_code.text) else 'UNKNOWN',
                 'location_name': location_full_name.split('AutoCompleteServlet?scope=context&search=',1)[1].split('&')[0]}
                for location_code,location_full_name in zip(call_location_code.result,call_location_code.done)]


        # Using additional thread to speed up the entire processing for FileOperationIO task
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool, functools.partial(evergreen_mapping, crawler_result=service_routing.result,network_results=service_routing.done,
                                        lookup_network=network_results,lookup_location = location_set, writer=writer))

        service_routing.logging_url(task_name='Evergreen Service Routing')

