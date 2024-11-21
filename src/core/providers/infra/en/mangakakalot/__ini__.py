from typing import List
from bs4 import BeautifulSoup
from core.__seedwork.infra.http import Http
from core.providers.infra.template.base import Base
from core.download.application.use_cases import DownloadUseCase
from core.providers.domain.entities import Chapter, Pages, Manga

class MangaKakalotProvider(Base):
    name = 'Manga Kakalot'
    lang = 'en'
    domain = ['mangakakalot.com']

    def __init__(self) -> None:
        self.headers = {'referer': 'https://chapmanganato.to/'}
    
    def getManga(self, link: str) -> Manga:
        response = Http.get(link)
        print(response.content)
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.select_one('div.manga-info-top h1')

        return Manga(link, title.get_text().strip())

    def getChapters(self, id: str) -> List[Chapter]:
        response = Http.get(id)
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.select_one('div.manga-info-top h1')
        chapter_div = soup.select_one('div.chapter-list')
        chapters = chapter_div.select('div.row a')
        list = []
        for ch in chapters:
            list.append(Chapter(ch.get('href'), ch.get_text().strip(), title.get_text().strip()))
        return list

    def getPages(self, ch: Chapter) -> Pages:
        response = Http.get(ch.id)
        soup = BeautifulSoup(response.content, 'html.parser')
        pages_div = soup.select_one('div.container-chapter-reader')
        pages = pages_div.select('img')
        list = []
        for pg in pages:
            list.append(pg.get('src'))
        return Pages(ch.id, ch.number, ch.name, list)
    
    def download(self, pages: Pages, fn: any, headers=None, cookies=None):
        if headers is not None:
            headers = headers | self.headers
        else:
            headers = self.headers
        return DownloadUseCase().execute(pages=pages, fn=fn, headers=headers, cookies=cookies)

