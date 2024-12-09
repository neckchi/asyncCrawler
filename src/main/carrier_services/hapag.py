from src.main.crawler_modal.async_crawler import *
from src.main.carrier_services.helpers import order_counter
from src.main.crawler_modal.csv_operation import FileManager
from src.main.schemas.service_loops import Services
from src.main.schemas import settings
import orjson  # Orjson is built in RUST, its performing way better than python in built json
import uuid
import concurrent.futures
import functools
import csv
import calendar

carrier: str = 'hlcu'
logger = LoggerFactory.get_logger(__name__, log_level="INFO")
# hlcu_service_loop:tuple = ('AA7',	'ADX',	'AG2',	'AG3',	'AL2',	'AL3',	'AL4',	'AL5',	'AL6',	'AL7',	'AN1',	'AN2',	'ANP',	'AOF',	'AR1',	'AS2',	'ASE',	'AT1',	'AT2',	'ATA',	'AWA',	'BAX',	'BF2',	'CAT',	'CCE',	'CCF',	'CES',	'CIX',	'CON',	'CUS',	'EA2',	'EA3',	'EA4',	'EC1',	'EC2',	'EC5',	'EC6',	'ECX',	'EMX',	'FE2',	'FE3',	'FE4',	'FE5',	'FE9',	'FP1',	'GC2',	'GCS',	'GEM',	'GM8',	'GS1',	'IEX',	'IG1',	'IMX',	'IN2',	'IO3',	'IOS',	'JCS',	'JDX',	'JP1',	'JSJ',	'KWF',	'MCA',	'MD1',	'MD2',	'MD3',	'MIA',	'MSE',	'MSW',	'MWX',	'NAX',	'NPX',	'PAF',	'PEX',	'PID',	'PN1',	'PN2',	'PN3',	'PN4',	'PS3',	'PS4',	'PS6',	'PS7',	'PSX',	'RS3',	'S2A',	'SA1',	'SA2',	'SAL',	'SAT',	'SAX',	'SEA',	'SEC',	'SS1',	'SS2',	'SWX',	'TEX',	'TNE',	'TPI',	'TPM',	'TSX',	'USW',	'VCF',	'VIS',	'WA1',	'WAX',	'WBS',	'WNF',	'WS2',	'WS3',	'WS4',	'WSF',	'WSN',	'WWA')
hlcu_service_loop: tuple = ('AGX',	'AL1',	'AL2',	'AL3',	'AL4',	'AL6',	'BFS',	'BS1',	'BS2',	'BS3',	'BS4',	'EM1',	'EM2',	'EM3',	'EM4',	'FLS',	'IEX',	'IMX',	'IOS',	'JD1',	'JD2',	'JD3',	'JP1',	'KS1',	'KS3',	'MBS',	'MFS',	'MGX',
                            'NE1',	'NE2',	'NE3',	'NE4',	'OGS',	'PGS',	'PKS',	'RSS',	'SB1',	'SB2',	'SC1',	'SE1',	'SE2',	'SE3',	'SOS',	'TCS',	'TSS',	'UGS',	'US1',	'US2',	'US3',	'US4',	'VS1',	'VS2',	'WC1',	'WC2',	'WC3',	'WC4',	'WC5',	'WM1',	'WM2',	'WM3')


def hapag_mapping(crawler_result: list, writer: csv.DictWriter):
    for routing in crawler_result:
        direction: str = 'ROUND'
        service_code: str = routing.get('serviceCode')

        def create_common_dict(port_code): return {
            'changeMode': None,
            'allianceID': None,
            'alliancePoolID': None,
            'tradeID': None,
            'oiServiceID': ''.join([service_code, carrier.upper()]),
            'carrierID': carrier.upper(),
            'serviceID': service_code + ' [R]',
            'service': service_code,
            'direction': direction,
            'frequency': 'WEEKLY',
            'portCode': port_code,
            'relatedID': uuid.uuid5(uuid.NAMESPACE_DNS, f'{carrier.upper()}-{service_code}-{direction}')}
        for port_sequence, port_rotation in enumerate(routing.get('portCalls')):
            port_code: str = port_rotation.get('portCode')
            pol: Services = Services(**create_common_dict(port_code),
                                     startDay=calendar.day_abbr[(eta := port_rotation.get(
                                         'arrival').get('fisRvDay')) % 7].upper(),
                                     tt=eta,
                                     order=order_counter(port_sequence, 'L'),
                                     locationType='L')
            writer.writerow(pol.model_dump())
            pod: Services = Services(**create_common_dict(port_code),
                                     startDay=calendar.day_abbr[(etd := port_rotation.get(
                                         'departure').get('fisRvDay')) % 7].upper(),
                                     tt=etd,
                                     order=order_counter(port_sequence, 'D'),
                                     locationType='D')
            writer.writerow(pod.model_dump())


async def hapag_crawler():
    loop = asyncio.get_running_loop()
    with FileManager(mode='w', scac=f'{carrier}') as writer:
        service_routing = Crawler(
            crawler_type='API',
            method='GET',
            sleep=1,
            urls=[settings.hlcu_service_url.format(
                loop=loop_code) for loop_code in hlcu_service_loop],
            specific_headers={'Authorization': f'Basic {settings.hlcu_token.get_secret_value()}', 'X-IBM-Client-ID': settings.hlcu_client_id.get_secret_value(),
                              'X-IBM-Client-Secret': settings.hlcu_client_secret.get_secret_value()},
            workers=6,
            limit=100000,
        )
        await service_routing.run()
        service_routing_result: list = [orjson.loads(
            routing.read()) for routing in service_routing.result]

        # Using additional thread to speed up the entire processing for FileOperationIO task
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, functools.partial(hapag_mapping, crawler_result=service_routing_result, writer=writer))
        service_routing.logging_url(task_name='Hapag Service Routing')
