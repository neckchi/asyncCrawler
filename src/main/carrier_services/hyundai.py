from src.main.crawler_modal.async_crawler import *
from datetime import datetime,timedelta
import json


async def hyundai_crawler():

    service_network = Crawler(
        crawler_type='API',
        method='POST',
        sleep=None,
        urls=['https://www.hmm21.com/e-service/general/schedule/selectScheduleOptionJson.do'],
        workers=5,
        limit=5000,
    )
    await service_network.run()
    service_network_result:list = [str(data.get('optNm')) .split('[')[1][:3]for service_group in service_network.result for data in json.loads(service_group.text)['RTN_JSON3']][:2]
    now:datetime = datetime.now()
    date_from: str = now.strftime("%Y%m%d")
    date_to:str = (now + timedelta(days= 120)).strftime("%Y%m%d")
    service_routing_url:list =['https://www.hmm21.com/e-service/general/schedule/selectScheduleOptionJson.do?srchByLoopOptLoop={loop}&srchLongDateFrom={date_from}&srchLongDateTo={date_to}'.format(loop=result,date_from=date_from,date_to=date_to) for result in service_network_result]


    service_routing = Crawler(
        crawler_type='API',
        method='POST',
        sleep=4,
        urls=service_routing_url,
        workers=5,
        limit=5000,
    )
    await service_routing.run()

    service_route = [data for service_route in service_routing.result for data in json.loads(service_route.text)['hdrList']]


    print(service_routing.result)

asyncio.get_event_loop().run_until_complete(hyundai_crawler())

# asyncio.run(hyundai_crawler(),debug=True)