import asyncio
from src.main.carrier_services import yangming
from src.main.logger_factory import log_cleaning

if __name__ == '__main__':
    log_cleaning.cleaning(-30)
    async def main():
        services_run = await asyncio.gather(yangming.yangming_crawler())
        return services_run

    asyncio.get_event_loop().run_until_complete(main())
