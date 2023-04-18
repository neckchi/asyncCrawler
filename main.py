import asyncio
import datetime
import os
from carrier_services import cosco
from logger_factory import log_cleaning
from mft_connections.sftp_connections import Sftp
from schemas import settings


if __name__ == '__main__':
    log_cleaning.cleaning(-30)
    asyncio.run(cosco.cosco_crawler())

    # Connect KN SFTP
    sftp = Sftp(
        hostname=settings.mft_server.get_secret_value(),
        username=settings.mft_user.get_secret_value(),
        password=settings.mft_password.get_secret_value()
    )
    sftp.connect()
    # Upload the service loop
    today: datetime = datetime.datetime.now()
    timestamp: datetime = today.strftime("%Y%m%dT%H%M%S%f")
    local_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cosco_services\cosco_port_rotation.csv')
    target_path = '/pub/inbound/services/cosu'
    target_file = f'cosco_services_{timestamp}.csv'
    try:
        sftp.upload(source_local_path=local_file,remote_path=target_path,file_name=target_file)
    except IOError:
        pass
    finally:
    # Disconnect KN SFTP
        sftp.disconnect()
