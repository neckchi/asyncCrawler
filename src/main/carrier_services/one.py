from playwright.async_api import async_playwright
from src.main.carrier_services.helpers import order_counter, split_list_of_dicts, find_dictionaries_by_value
from src.main.crawler_modal.csv_operation import FileManager
from src.main.crawler_modal import browser_headers
from src.main.schemas.service_loops import Services
from random import randint
import concurrent.futures
import asyncio
import csv
import functools
import uuid

carrier: str = 'oney'


async def one_crawler():
    async with async_playwright() as playwright:
        await one_playwright(playwright)


def get_random_header(header_list: list[dict]):
    random_index = randint(0, len(header_list) - 1)
    return header_list[random_index]

def one_mapping(crawler_result: list, network_results: list, lookup_network: list, writer: csv.DictWriter):
    for service, routing in zip(network_results, crawler_result):
        service_code: str = service
        service_name: str = find_dictionaries_by_value(lst=lookup_network, key='service_code', value=service_code)[0].get('service_name')
        routing_direction: dict = split_list_of_dicts(lst=routing, key='directionCode')
        for direction_code, rotation_list in routing_direction.items():
            direction_lookup: dict = {'N': 'NORTHBOUND', 'S': 'SOUTHBOUND', 'E': 'EASTBOUND', 'W': 'WESTBOUND'}
            direction: str = direction_lookup.get(direction_code, 'UNKNOWN')
            for port_sequence, rotation in enumerate(rotation_list):
                port_code: str = rotation['portCode']
                common: dict = {'changeMode': None, 'allianceID': None, 'alliancePoolID': None,
                                'tradeID': None,
                                'oiServiceID': ''.join([service_code, carrier.upper()]),
                                'carrierID': carrier.upper(),
                                'serviceID': service_code + ' ' + ''.join(['[', direction_code, ']']),
                                'service': service_name,
                                'direction': direction,
                                'frequency': 'WEEKLY',
                                'portCode': port_code,
                                'relatedID': uuid.uuid5(uuid.NAMESPACE_DNS,
                                                        f'{carrier.upper()}-{service_code}-{direction}')}

                pol: Services = Services(**common,
                                         startDay='SUN',
                                         tt=0,
                                         order=order_counter(port_sequence, 'L'),
                                         locationType='L')
                writer.writerow(pol.dict())
                pod: Services = Services(**common,
                                         startDay='SUN',
                                         tt=0,
                                         order=order_counter(port_sequence, 'D'),
                                         locationType='D')
                writer.writerow(pod.dict())


async def one_playwright(playwright):
    loop = asyncio.get_running_loop()
    sem = asyncio.Semaphore(3)
    headers: dict = get_random_header(header_list=browser_headers.headers_list)

    # Open New Page
    async def open_new_page(context):
        page = await context.new_page()
        await page.set_extra_http_headers(headers)
        return page

    # Main Logic after going to their landing page
    async def scrap_post_info(context, main_page: str, sub_page: str):
        #Considering the browser and network performance,Limit concurrent scrapping operation to 3 pages only everytime.
        async with sem:
            page = await open_new_page(context)
            await page.goto(main_page, wait_until = 'load')
            await page.locator("//button[@id='menu:continent-from-combo-box:trigger']").click()
            await page.locator(f'#{sub_page}').click()

            # Search All possible ONE service network
            async with page.expect_response(lambda request: request.status == 200 and str(request.url).startswith('https://ecomm.one-line.com/api/v1/schedule/long-range/shipping-lanes?fromContinentCode')) as network_response_info:
                await page.locator("//button[contains(@class, 'ScheduleButton_base__ivpyn') and contains(@class, 'ScheduleButton_colorPrimary__phL_p') and contains(@class, 'ScheduleButton_variantFilled__R6vgG') and contains(@class, 'ScheduleButton_sizeMd__0xGYi')]").click()
                service_networks = await network_response_info.value
                get_text_from_response = await service_networks.json()

                # Service_Code
                await page.locator(".LongRangeServices_services__oCs7I").wait_for(state='visible')
                service_code_links = await page.locator(".LongRangeServices_service__39aZi").all()
                for service_code in service_code_links:
                    async with page.expect_response(lambda request: request.status == 200 and str(request.url).startswith('https://ecomm.one-line.com/api/v1/schedule/long-range?shippingLaneName'),timeout=0) as service_response_info:
                        await service_code.click()
                    service_routing = await service_response_info.value
                    get_text_from_service_response = await service_routing.json()
                    get_url_from_service_response = service_routing.url[-3:]
                    service_networks_set: list = [{'service_code': service_network['shippingLaneCode'],'service_name': service_network['shippingLaneName']} for service_network in get_text_from_response['shippingLanes']]
                    print(service_networks_set)
                    print(get_text_from_service_response)
                    one_service_network.extend(service_networks_set)
                    one_service_routing.append(get_text_from_service_response['ports'])
                    one_service_url.append(get_url_from_service_response)
            await page.close()

    # Open csv file
    with FileManager(mode='w', scac=f'{carrier}') as writer:
        # Launch Browser
        chromium = playwright.chromium
        browser = await chromium.launch(channel="chrome", slow_mo=2000)
        context = await browser.new_context()
        page = await open_new_page(context)

        # Go To ONE website
        one_service_network: list = []
        one_service_url: list = []
        one_service_routing: list = []

        # Wait and Get the ONE region list
        await page.goto("https://ecomm.one-line.com/one-ecom/schedule/long-range-schedule", wait_until = 'load')
        await page.locator("//button[contains(@class, 'ScheduleButton_base__ivpyn') and contains(@class, 'ScheduleButton_colorPrimary__phL_p') and contains(@class, 'ScheduleButton_variantFilled__R6vgG') and contains(@class, 'ScheduleButton_sizeMd__0xGYi')]").wait_for()
        service_network_continents:list = await page.locator('.ComboBoxItem_item__HtRS3').all()

        task:list = [asyncio.create_task(scrap_post_info(context=context,main_page='https://ecomm.one-line.com/one-ecom/schedule/long-range-schedule',sub_page=await service_network_continent.evaluate("node => node.id"))) for service_network_continent in service_network_continents[0:5]]
        await asyncio.gather(*task)
        await browser.close()

        # Using additional thread to speed up the entire processing for FileOperationIO task
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, functools.partial(one_mapping, crawler_result=one_service_routing,network_results=one_service_url,lookup_network=one_service_network,writer=writer))
