import asyncio
from carrier_services import cosco
from logger_factory import log_cleaning



if __name__ == '__main__':
    log_cleaning.cleaning(-30)
    async def main():
        services_run = await asyncio.gather(cosco.cosco_crawler())
        return services_run

    asyncio.run(main())

