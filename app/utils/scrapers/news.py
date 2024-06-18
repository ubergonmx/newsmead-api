# Copyright (c) ubergonmx. All rights reserved.
# Licensed under the BSD 2-Clause License.

from abc import ABC, abstractmethod
from enum import Enum
from typing import NamedTuple
from bs4 import BeautifulSoup
from newspaper import Article as ArticleScraper
from datetime import datetime
from dateutil.parser import parse
from fake_useragent import UserAgent
from app.database.asyncdb import AsyncDatabase
from app.models.article import Article
import app.backend.config as config
import os
import httpx
import asyncio
import readtime
import logging
import feedparser
import re
import aiofiles

# Configure logging
log = logging.getLogger(__name__)


class Category(Enum):
    News = "news"
    Opinion = "opinion"
    Sports = "sports"
    Technology = "technology"
    Lifestyle = "lifestyle"
    Business = "business"
    Entertainment = "entertainment"


class Provider(Enum):
    GMANews = "gmanews"
    Philstar = "philstar"
    # News5 = "news5"
    ManilaBulletin = "manilabulletin"
    INQUIRER = "inquirer"
    AbanteNews = "abantenews"


class ScraperConfig(NamedTuple):
    provider_name: str
    default_author: str
    category_mapping: dict[Category, str]
    rss_url: str = None
    webcrawler_urls: dict[Category, list[str]] = None


class ScraperStrategy(ABC):
    @property
    @abstractmethod
    def config(self) -> ScraperConfig:
        pass

    async def scrape_all(self, proxy_scraper=None) -> list[Article]:
        results = []
        for category in self.config.category_mapping:
            category_results = await self.scrape_category(category, proxy_scraper)
            results.extend(category_results)
        return results

    async def scrape_category(
        self, category: Category, proxy_scraper=None
    ) -> list[Article]:
        if category in self.config.category_mapping:
            log.info(f"{self._cname()} scraping for {category} started")

            articles = []
            articles.extend(await self.fetch_and_parse_rss(category, proxy_scraper))

            async with AsyncDatabase() as db:
                filtered_articles = await db.filter_new_urls(
                    articles, category=category.value
                )

            scraped_articles = await self.scrape_articles(
                filtered_articles, proxy_scraper
            )

            log.info(f"{self._cname()} scraping for {category} complete")
            return scraped_articles
        else:
            log.error(f"Category mapping not defined for {self._cname()}: {category}")
            return []

    async def scrape_url(self, url: str, proxy: dict = None) -> tuple:
        article = Article(
            date="",
            category="",
            source=self.config.provider_name,
            title="",
            url=url,
        )
        return await self.scrape_article(article, proxy_mounts=proxy)

    async def scrape_articles(
        self, articles: list[Article], proxy_scraper=None, chunk_size=25
    ) -> list[Article]:
        success = []
        failed = []

        for i in range(0, len(articles), chunk_size):
            tasks = [
                self.scrape_article(article) for article in articles[i : i + chunk_size]
            ]
            results = await asyncio.gather(*tasks)

            for result in results:
                if result[0]:
                    success.append(result[1])
                else:
                    failed.append(result[1])

        if len(failed) > 0:
            log.info(
                f"{self._cname()} failed to scrape {len(failed)} articles. Retrying..."
            )
            for i in range(0, len(failed), chunk_size):
                tasks = [
                    self.scrape_article_with_retries(article, proxy_scraper)
                    for article in failed[i : i + chunk_size]
                ]
                results = await asyncio.gather(*tasks)
                for result in results:
                    success.append(result[1])

        log.info(f"{self._cname()} scraped {len(success)} articles")
        return success

    async def scrape_article(
        self, article: Article, proxy_mounts: dict = None
    ) -> tuple:
        headers = {"User-Agent": UserAgent().random}
        async with httpx.AsyncClient(
            headers=headers, follow_redirects=True, mounts=proxy_mounts
        ) as client:
            try:
                response = await client.get(article.url)
                response.raise_for_status()
            except httpx.HTTPError as e:
                log.error(
                    f"HTTP Exception {'' if proxy_mounts is None else '(proxy: ' + list(proxy_mounts.values())[0] + ')'}: {e}"
                )
                return False, article

            if not response.content:
                log.error(f"Article has no content: {article.url}")
                return False, article

            soup = BeautifulSoup(response.content, "html.parser")
            author = self.extract_author(soup)

            news_article = ArticleScraper(str(response.url))
            news_article.download(input_html=response.content)
            news_article.parse()

            article.date = article.date or self.parse_date_complete(
                news_article.publish_date or datetime.now().isoformat()
            )
            article.title = article.title or news_article.title
            article.body = self.clean_body(news_article.text)
            article.author = (
                author
                if author is not None
                else (
                    news_article.authors[0].strip()
                    if news_article.authors
                    else self.config.default_author
                )
            )
            article.author = (
                article.author.title() if article.author.isupper() else article.author
            )
            article.author = (
                self.config.default_author if article.author == "" else article.author
            )
            article.url = str(response.url)
            article.image_url = article.image_url or news_article.top_image
            article.read_time = str(readtime.of_text(news_article.text))

            try:
                if article.movies:
                    # add movies to article as string "[Video: movies[0]]"
                    article.body += "\n\n" + "\n\n".join(
                        [f"[Video: {movie}]" for movie in article.movies]
                    )
            except:
                pass

        return True, article

    async def scrape_article_with_retries(
        self, article: Article, proxy_scraper, max_retries=10
    ) -> tuple:
        for i in range(max_retries):
            proxy_mounts = proxy_scraper.get_next_proxy_mounts()
            log.info(
                f"Using proxy: {list(proxy_mounts.values())[0]} ({i+1}/{max_retries}) -> {article.url}"
            )
            result = await self.scrape_article(article, proxy_mounts)
            if result[0]:
                return result
            elif i == max_retries - 1:
                return (False, article)

    async def fetch_and_parse_rss(
        self, category: Category, proxy_scraper, retries=10, save=True
    ) -> list[Article]:
        if self.config.rss_url is None:
            log.error(f"RSS URL not defined for {self.config.provider_name}")
            return []

        mapped_category = self.config.category_mapping[category]
        rss_url = self.config.rss_url.replace("[category]", mapped_category)
        log.info(f"RSS Feed URL: {rss_url}")

        rss_response = None
        while retries > 0:
            log.info(f"Fetching RSS feed for {category} ({retries} retries left)")
            proxy_mounts = (
                proxy_scraper.get_next_proxy_mounts() if retries < 10 else None
            )
            headers = {"User-Agent": UserAgent().random}
            try:
                async with httpx.AsyncClient(
                    headers=headers, mounts=proxy_mounts, follow_redirects=True
                ) as client:
                    rss_response = await client.get(rss_url)
            except httpx.HTTPError as e:
                log.error("Connection error: " + str(e))
                retries -= 1
                continue

            if rss_response.status_code != 200:
                log.error(f"RSS status code: {rss_response.status_code}")
                retries -= 1
            else:
                break

            if retries == 0:
                log.error(f"Failed to fetch RSS feed for {category}")
                return []

        if rss_response is None:
            log.error(f"No response from RSS feed for {category}")
            return []

        if save:
            await self.save_rss(rss_response.content, category)
        log.info(f"Parsing RSS feed for {category}")
        feed = feedparser.parse(rss_response.content)

        articles = []
        for entry in feed.entries:
            image_url = ""
            if "media_content" in entry and "url" in entry.media_content[0]:
                image_url = entry.media_content[0]["url"]
            article = Article(
                date=self.parse_date_complete(entry.published),
                category=category.value,
                source=self.config.provider_name,
                title=entry.title,
                url=entry.link,
                image_url=image_url,
            )
            articles.append(article)
        log.info(f"Parsed {len(articles)} articles from RSS feed")
        return articles

    async def save_rss(self, rss_content: bytes, category: Category):
        current_time = datetime.now().strftime("%Y-%m-%d-%H-%M")

        filename = os.path.join(
            config.get_rss_dir(),
            current_time[:10],  # Get the date part
            f"{self.config.provider_name}-{category.value}-{current_time[11:]}.xml",  # Get the time part
        )

        os.makedirs(os.path.dirname(filename), exist_ok=True)

        async with aiofiles.open(filename, "wb") as f:
            await f.write(rss_content)

        log.info(f"Saved RSS feed to {filename}")

    async def save_webcrawler(self, webcrawler_content: bytes, category: Category):
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_hr_min = datetime.now().strftime("%H-%M")

        filename = os.path.join(
            config.get_webcrawler_dir(),
            current_date,
            f"{self.config.provider_name}-{category.value}-{current_hr_min}.xml",
        )

        os.makedirs(os.path.dirname(filename), exist_ok=True)

        async with aiofiles.open(filename, "wb") as f:
            await f.write(webcrawler_content)

        log.info(f"Saved webcrawler feed to {filename}")

    def extract_author(self, soup: BeautifulSoup) -> str:
        author = soup.find("meta", {"name": "author"})
        if author is not None:
            return author.get("content").split(",")[0].strip()
        return None

    def clean_body(self, text: str) -> str:
        list_of_words = [
            "ADVERTISEMENT",
            "ADVERTORIAL",
            "SPONSORED CONTENT",
            "FEATURED STORIES",
        ]
        for word in list_of_words:
            text = text.replace(word, "")
        return text.strip()

    def _cname(self) -> str:
        return self.__class__.__name__

    def parse_date_complete(self, date) -> str:
        if isinstance(date, datetime):
            return date.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return parse(date).strftime("%Y-%m-%d %H:%M:%S")


class GMANewsScraper(ScraperStrategy):
    @property
    def config(self) -> ScraperConfig:
        return ScraperConfig(
            provider_name=Provider.GMANews.value,
            category_mapping={
                Category.News: "news",
                Category.Opinion: "opinion",
                Category.Sports: "sports",
                Category.Technology: "scitech",
                Category.Lifestyle: "lifestyle",
                Category.Business: "money",
                Category.Entertainment: "showbiz",
            },
            rss_url="https://data.gmanetwork.com/gno/rss/[category]/feed.xml",
            default_author="GMA News Online",
        )


class PhilstarScraper(ScraperStrategy):
    @property
    def config(self) -> ScraperConfig:
        return ScraperConfig(
            provider_name=Provider.Philstar.value,
            category_mapping={
                Category.News: "headlines",
                Category.Opinion: "opinion",
                Category.Sports: "sports",
                Category.Technology: "business/technology",
                Category.Lifestyle: "lifestyle",
                Category.Business: "business",
                Category.Entertainment: "entertainment",
            },
            rss_url="https://www.philstar.com/rss/[category]",
            default_author="Philstar.com",
        )

    def extract_author(self, soup: BeautifulSoup) -> str:
        author_tag = soup.find("div", class_="article__credits-author-pub")
        if author_tag:
            a_tags = author_tag.find_all("a")
            return a_tags[-1].text.strip() if a_tags else author_tag.text.strip()
        else:
            return None


class ManilaBulletinScraper(ScraperStrategy):
    @property
    def config(self) -> ScraperConfig:
        return ScraperConfig(
            provider_name=Provider.ManilaBulletin.value,
            category_mapping={
                category: category.value.lower() for category in Category
            },
            rss_url="https://mb.com.ph/rss/[category]",
            default_author="Manila Bulletin",
        )

    def extract_author(self, soup: BeautifulSoup) -> str:
        author_tag = soup.find(
            "a", class_="custom-text-link uppercase author-name-link pb-0 mt-1"
        )
        return author_tag.span.text if author_tag else None


class InquirerScraper(ScraperStrategy):
    @property
    def config(self) -> ScraperConfig:
        return ScraperConfig(
            provider_name=Provider.INQUIRER.value,
            category_mapping={
                Category.News: "newsinfo",
                Category.Opinion: "opinion",
                Category.Sports: "sports",
                Category.Technology: "technology",
                Category.Lifestyle: "lifestyle",
                Category.Business: "business",
                Category.Entertainment: "entertainment",
            },
            rss_url="https://[category].inquirer.net/feed",
            default_author="INQUIRER.net",
        )

    def extract_author(self, soup: BeautifulSoup) -> str:
        author = super().extract_author(soup)
        if author:
            return author

        script_tag = soup.find("script", text=re.compile(r"\'author_name\':"))
        if script_tag:
            author_name_match = re.search(
                r"\'author_name\': \'(.*?)\'", script_tag.text
            )
            return author_name_match.group(1).strip() if author_name_match else None

        # If author_name is empty in script, extract from the subsequent div tag
        div_tag = soup.find("div", id="art_plat")
        if div_tag:
            author_link = div_tag.find("a")
            return author_link.text.strip() if author_link else None


class AbanteNewsScraper(ScraperStrategy):
    @property
    def config(self) -> ScraperConfig:
        return ScraperConfig(
            provider_name=Provider.AbanteNews.value,
            category_mapping={
                Category.News: "news",
                Category.Opinion: "op",
                Category.Sports: "sports3",
                Category.Lifestyle: "lifestyle",
                Category.Business: "business",
                Category.Entertainment: "ent",
            },
            rss_url="https://www.abante.com.ph/category/[category]/feed/",
            default_author="Abante News",
        )

    def extract_author(self, soup: BeautifulSoup) -> str:
        return None


class NewsScraper:
    def __init__(self, strategy: ScraperStrategy):
        self.strategy = strategy

    async def scrape_all(self, proxy_scraper) -> list[Article]:
        return await self.strategy.scrape_all(proxy_scraper=proxy_scraper)

    async def scrape_category(
        self, category: Category, proxy_scraper=None
    ) -> list[Article]:
        return await self.strategy.scrape_category(category, proxy_scraper)

    async def scrape_articles(
        self, articles: list[Article], proxy_scraper=None
    ) -> list[Article]:
        return await self.strategy.scrape_articles(articles, proxy_scraper)

    async def scrape_url(self, url: str, proxy: dict = None) -> dict:
        return await self.strategy.scrape_url(url, proxy)


# Define a mapping between Provider and ScraperStrategy
provider_strategy_mapping = {
    Provider.GMANews: GMANewsScraper(),
    Provider.Philstar: PhilstarScraper(),
    Provider.ManilaBulletin: ManilaBulletinScraper(),
    Provider.INQUIRER: InquirerScraper(),
    # Provider.News5: News5Scraper(),
    Provider.AbanteNews: AbanteNewsScraper(),
}


def get_scraper_strategy(provider: Provider) -> ScraperStrategy:
    return provider_strategy_mapping.get(provider)
