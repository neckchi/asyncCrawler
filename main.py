import asyncio
from src.main.carrier_services import yangming,evergreen,cosco,hyundai,cmacgm,smline,one
from src.main.logger_factory import log_cleaning

if __name__ == '__main__':
    log_cleaning.cleaning(-30)
    async def main():
        # services_run = await asyncio.gather(hyundai.hyundai_crawler(),cosco.cosco_crawler(),yangming.yangming_crawler(),evergreen.evergreen_crawler(),cmacgm.cma_crawler())

        #testing
        services_run = await asyncio.gather(one.one_crawler())
        return services_run

    asyncio.get_event_loop().run_until_complete(main())
