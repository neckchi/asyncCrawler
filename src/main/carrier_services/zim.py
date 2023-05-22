from src.main.crawler_modal.async_crawler import *
async def zim_crawler():
    service_network = Crawler(
        crawler_type='API',
        method='GET',
        sleep=None,
        urls=['https://www.zim.com/api/v2/trade/GetTrades'],
        workers=5,
        limit=5000,
    )
    await service_network.run()

    print(service_network.result)

asyncio.get_event_loop().run_until_complete(zim_crawler())

# asyncio.run(hyundai_crawler(),debug=True)