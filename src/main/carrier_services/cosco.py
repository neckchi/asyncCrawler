from src.main.crawler_modal.async_crawler import *
from src.main.crawler_modal.csv_operation import FileManager
from src.main.schemas.service_loops import Services
from urllib.parse import urlparse
from src.main.carrier_services.helpers import order_counter, find_closest_location_code
from src.main.mft_connections.sftp_connections import Sftp
from src.main.schemas import settings
import concurrent.futures
import functools
import uuid
import orjson  # Orjson is built in C, its performing way better than python built in json
import time
import csv

carrier: str = 'cosu'


def cosco_mapping(crawler_result: list, writer: csv.DictWriter):
    # File Operation IO tasks - sort out the file,do mapping based on csv schemas
    direction_lookup: dict = {
        'N': 'NORTHBOUND', 'S': 'SOUTHBOUND', 'E': 'EASTBOUND', 'W': 'WESTBOUND'}
    for call_port in crawler_result:
        service_code: str = urlparse(
            str(call_port.url)).path[31:].split('.do')[0]
        for data in orjson.loads(call_port.read())['data']['content']:
            direction_code: str | None = str(
                data.get('direction', 'U'))[0].strip()
            direction: str = direction_lookup.get(direction_code, 'UNKNOWN')
            for port_sequence, ports in enumerate(data['ports'], start=0):
                port_name: str = str(ports.get('callPort')
                                     ).upper().replace(' ', '')
                etd_day: str | None = str(ports.get('callPortEtd')).upper().strip() if str(
                    ports.get('callPortEtd')).isalpha() else str(ports.get('callPortEtdTime')).upper().strip()
                etd_time: str | None = ports.get('callPortEtdTime') if str(
                    ports.get('callPortEtdTime')).isnumeric() else ports.get('callPortEtd')
                eta_day: str | None = str(ports.get('callPortEta')).upper().strip() if str(
                    ports.get('callPortEta')).isalpha() else str(ports.get('callPortEtaTime')).upper().strip()
                eta_time: str | None = ports.get('callPortEtaTime') if str(
                    ports.get('callPortEtaTime')).isnumeric() else ports.get('callPortEta')
                common: dict = {'changeMode': None, 'allianceID': None, 'alliancePoolID': None,
                                'tradeID': None,
                                'oiServiceID': ''.join([service_code, carrier.upper()]),
                                'carrierID': carrier.upper(),
                                'serviceID': service_code + ' ' + ''.join(['[', direction_code, ']']),
                                'service': service_code,
                                'direction': direction,
                                'frequency': 'WEEKLY',
                                'portCode': find_closest_location_code(port_name),
                                'relatedID': uuid.uuid5(uuid.NAMESPACE_DNS, f'{carrier.upper()}-{service_code}-{direction}')}
                if ports.get('callPortEtaTime') is not None:
                    pol: Services = Services(**common,
                                             startDay=eta_day.replace('TEU', 'THU').replace(
                                                 'WES', 'WED').replace('NONE', etd_day),
                                             tt=eta_time if eta_time.isnumeric() else 5,
                                             order=order_counter(
                                                 port_sequence, 'L'),
                                             locationType='L')
                    writer.writerow(pol.model_dump())
                if ports.get('callPortEtdTime') is not None:
                    pod: Services = Services(**common,
                                             startDay=etd_day.replace('TEU', 'THU').replace(
                                                 'WES', 'WED').replace('NONE', eta_day),
                                             tt=etd_time,
                                             order=order_counter(
                                                 port_sequence, 'D'),
                                             locationType='D')
                    writer.writerow(pod.model_dump())


async def cosco_crawler():
    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    with FileManager(mode='w', scac=f'{carrier}') as writer:
        # COSCO Service Groups
        service_groups = Crawler(
            crawler_type='API',
            sleep=None,
            urls=[settings.cosu_service_url.format(i) for i in range(11, 19)],
            workers=3,
            limit=5100,
        )
        await service_groups.run()
        service_groups_result = [{data.get('serLpGroupUuid'): data.get('serLpGroupNameEn')} for service_group in
                                 service_groups.result for data in
                                 orjson.loads(service_group.read())['data']['content']]

        service_groups.logging_url(task_name='COSCO Service Groups')

        # COSCO Route Services
        route_services = Crawler(
            crawler_type='API',
            sleep=4,
            urls=[settings.cosu_route_url.format(
                next(iter(rs.keys())))
                for rs in service_groups_result],
            workers=3,
            limit=5100,
        )
        await route_services.run()

        route_services_result = [{data.get('serLpCode'): data.get('serLpNameEn')} for route_service in
                                 route_services.result for data in
                                 orjson.loads(route_service.read())['data']['content']]

        route_services.logging_url(task_name='COSCO Route Services')

        # COSCO CALL PORTS
        call_ports = Crawler(
            crawler_type='API',
            sleep=4,
            urls=[settings.cosu_ports_url.format(next(iter(cp.keys())))
                  for cp in route_services_result],
            workers=3,
            limit=5100,
        )
        await call_ports.run()

        # Using additional thread to speed up the entire processing for FileOperationIO task
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool, functools.partial(cosco_mapping, crawler_result=call_ports.result, writer=writer))

        call_ports.logging_url(task_name='COSCO CALL PORTS')

    # # Connect KN SFTP
    # sftp = Sftp(
    #     hostname=settings.mft_server.get_secret_value(),
    #     username=settings.mft_user.get_secret_value(),
    #     password=settings.mft_password.get_secret_value()
    # )
    # sftp.connect()
    # # Upload the service loop
    # today: datetime = datetime.datetime.now()
    # timestamp: datetime = today.strftime("%Y%m%dT%H%M%S%f")
    # local_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cosco_services\cosco_port_rotation.csv')
    # target_path = f'/pub/inbound/services/{carrier}'
    # target_file = f'{carrier}_services_{timestamp}.csv'
    # try:
    #     sftp.upload(source_local_path=local_file,remote_path=target_path,file_name=target_file)
    # except IOError:
    #     pass
    # finally:
    # # Disconnect KN SFTP
    #     sftp.disconnect()

# asyncio.run(cosco(), debug=True)
