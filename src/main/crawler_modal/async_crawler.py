from typing import Callable, Iterable,Literal,Type
from bs4 import BeautifulSoup
from random import randint
from src.main.crawler_modal import browser_headers
from urllib.parse import urlparse,parse_qs
import asyncio
import httpx



class Crawler():
    #Generate random user agent
    def get_random_header(header_list:list[dict]):
        random_index = randint(0, len(header_list) - 1)
        return header_list[random_index]

    def __init__(self, urls: Iterable[str],crawler_type = Literal['API','WEB'] ,method = Literal['GET','POST'],
                 specific_headers: dict | None = None,
                 parent_element:str|None = None,html_class:list|None= None,
                 html_id:list|None= None,next_element:str |None = None,
                 filter_url: Callable[[str, str], str | None] = None,
                 sleep: int = None,
                 workers: int = 10,
                 limit: int = 25,):

        timeout = httpx.Timeout(50.0, read=None, connect=60.0)
        limits = httpx.Limits(max_keepalive_connections=60, max_connections=None)
        self.type: Type[str] = crawler_type
        self.specific_headers:dict|None = specific_headers
        self.client: httpx.AsyncClient = httpx.AsyncClient(verify=False, timeout=timeout, limits=limits)
        self.method:Type[str] = method
        self.parent_element:str = parent_element
        self.html_class:list = html_class
        self.html_id:list = html_id
        self.element:str|None = next_element
        self.sleep_dllm:int = sleep
        self.start_urls: set = set(urls)
        self.todo: asyncio.Queue = asyncio.Queue()
        self.found_links: set = set()
        self.seen: set = set()
        self.done: list = list()
        self.result: list = list()
        self.filter_url = filter_url
        self.num_workers:int = workers
        self.limit: int = limit
        self.total: int = 0


    async def run(self):
        await self.on_found_links(self.start_urls)  # prime the queue
        # workers = [asyncio.create_task(self.worker()) for _ in range(self.num_workers)]
        workers = [asyncio.ensure_future(self.worker()) for _ in range(self.num_workers)]
        await self.todo.join()
        for worker in workers:
            worker.cancel()

    async def worker(self):
        while True:
            try:
                await self.process()
            except asyncio.CancelledError:
                return

    async def process(self):
        url = await self.todo.get()
        # retry 10 times
        while (retries := 10) > 0:
            try:
                await self.crawl(url)
                break
            except (httpx.TimeoutException, httpx.ConnectTimeout):
                await asyncio.sleep(3)
                retries -= 1
        if retries == 0:
            raise PermissionError
        else:

            self.todo.task_done()

    async def crawl(self, url: str):
        headers:dict = Crawler.get_random_header(header_list=browser_headers.headers_list)
        # rate limit here...many website will auto ban IP address if they detect too many connection and too fast
        if self.sleep_dllm is None:
            pass
        else:
            await asyncio.sleep(self.sleep_dllm)

        if self.method == 'GET':
            response = await self.client.get(url=url,headers=dict(headers,**self.specific_headers) if self.specific_headers is not None else headers,follow_redirects=True)
        else:
            parsed_url  = urlparse(url)
            base_url = f'{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}'
            body_data:dict|None = {key: value[0] for key,value in parse_qs(parsed_url.query).items()} if parsed_url.query else None
            response = await self.client.post(url=base_url,headers=dict(headers,**self.specific_headers)  if self.specific_headers is not None else headers,json = body_data,follow_redirects=True)
        found_links = await self.parse_links(base_url=url,response=response)
        await self.on_found_links(found_links)
        self.done.append(url)

    async def parse_links(self, base_url: str, response: httpx.Response) -> set[str]:
        if self.type == 'API':
            self.result.append(response)
        else:
            soup = BeautifulSoup(response.text,'html.parser')
            parsed_soup = soup.findAll(self.parent_element, class_=self.html_class) if self.html_class else soup.findAll(self.parent_element, id=self.html_id)
            if self.element =='ahref':
                for service in parsed_soup:
                    link = service.findNext('a')['href'].strip()
                    text = service.findNext('a').text
                    self.result.append({'a_link':link,'a_text':text})
            elif self.element in ('td','option'):
                self.result.append([service.text.strip() for service in parsed_soup if '-----' not in service.text])
            else:self.result.append(parsed_soup)
        self.found_links.add(base_url)
        return self.found_links


    async def on_found_links(self, urls: set[str]):
        new = urls - self.seen
        self.seen.update(new)
        # await save to database or file here...
        for url in new:
            await self.put_todo(url)

    async def put_todo(self, url: str):
        if self.total >= self.limit:
            return
        self.total += 1
        await self.todo.put(url)
