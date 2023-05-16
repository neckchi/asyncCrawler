from typing import Callable, Iterable
from bs4 import BeautifulSoup
import asyncio
import httpx


class Crawler():
    def __init__(self,crawler_type:str, urls: Iterable[str],parent_element:str|None = None,html_class:list|None= None,
                 html_id:list|None= None,next_element:str |None = None,
                 filter_url: Callable[[str, str], str | None] = None, sleep: int = None, workers: int = 10,
                 limit: int = 25,):
        timeout = httpx.Timeout(50.0, read=None, connect=60.0)
        limits = httpx.Limits(max_keepalive_connections=60, max_connections=None)
        self.client: httpx.AsyncClient = httpx.AsyncClient(verify=False, timeout=timeout, limits=limits)
        # self.loop = asyncio.get_event_loop()
        self.type:str = crawler_type
        self.parent_element:str = parent_element
        self.html_class:list = html_class
        self.html_id:list = html_id
        self.element:str|None = next_element
        self.sleep_dllm = sleep
        self.start_urls: set = set(urls)
        self.todo: asyncio.Queue = asyncio.Queue()
        self.found_links: set = set()
        self.seen: set = set()
        self.done: list = list()
        self.result: list = list()
        self.filter_url = filter_url
        self.num_workers = workers
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
        # retry 20 times
        while (retries := 20) > 0:
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
        # rate limit here...many website will auto ban IP address if they detect too many connection and too fast
        if self.sleep_dllm is None:
            pass
        else:
            await asyncio.sleep(self.sleep_dllm)
        response = await self.client.get(url=url,follow_redirects=True)
        found_links = await self.parse_links(base_url=str(response.url), response=response)
        await self.on_found_links(found_links)
        self.done.append(url)

    async def parse_links(self, base_url: str, response: httpx.Response) -> set[str]:
        if self.type == 'API':
            self.found_links.add(base_url)
            self.result.append(response)
        else:
            soup = BeautifulSoup(response.text,'html.parser')
            self.found_links.add(base_url)
            parsed_soup = soup.findAll(self.parent_element, class_=self.html_class) if self.html_class else soup.findAll(self.parent_element, id=self.html_id)
            if self.element =='ahref':
                for service in parsed_soup:
                    link = service.findNext('a')['href'].strip()
                    self.result.append(link)
            elif self.element in ('td','option'):
                self.result.append([service.text.strip() for service in parsed_soup if '-----' not in service.text])
            else:self.result.append(parsed_soup)
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
