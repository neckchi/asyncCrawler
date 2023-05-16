import asyncio
from carrier_services import cosco,evergreen,yangming
from logger_factory import log_cleaning

if __name__ == '__main__':
    log_cleaning.cleaning(-30)
    async def main():
        # services_run = await asyncio.gather(yangming.yangming_crawler(),evergreen.evergreen_crawler(),cosco.cosco_crawler())
        services_run = await asyncio.gather(evergreen.evergreen_crawler(),yangming.yangming_crawler())
        return services_run

    asyncio.get_event_loop().run_until_complete(main())
    # asyncio.run(main())
