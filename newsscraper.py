from abc import ABC, abstractmethod
from enum import Enum
from typing import NamedTuple
from bs4 import BeautifulSoup
from newspaper import Article
from datetime import datetime
import os
import httpx
import asyncio
import xml.etree.ElementTree as ET
import readtime
import logging
import feedparser

# [ ] TODO: Import typing module to be precise with types (especially return types)

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
    # Philstar = "philstar"
    # News5 = "news5"
    ManilaBulletin = "manilabulletin"
    # INQUIRER = "inquirer"


class Config(NamedTuple):
    provider_name: str
    category_mapping: dict
    rss_url: str
    default_author: str


# [ ] TODO: Remove unnecessary comments
# [ ] TODO: Add timer to benchmark performance
class ScraperStrategy(ABC):
    @property
    @abstractmethod
    def config(self) -> Config:
        pass

    async def scrape_all(self, proxy_scraper=None) -> list:
        results = []
        for category in self.config.category_mapping:
            category_results = await self.scrape_category(category, proxy_scraper)
            results.extend(category_results)
        return results

    async def scrape_category(self, category: Category, proxy_scraper=None) -> list:
        if category in self.config.category_mapping:
            articles = await self.fetch_and_parse_rss(category)

            scraped_articles = await self.scrape_articles(articles, proxy_scraper)

            log.info(f"{self._cname()} scraping for {category} complete")
            return scraped_articles
        else:
            log.error(f"Category mapping not defined for {self._cname()}: {category}")

    async def scrape_articles(self, articles: list, proxy_scraper=None) -> list:
        tasks = [self.scrape_article(article) for article in articles]
        results = await asyncio.gather(*tasks)

        success = []
        failed = []
        for result in results:
            if result[0]:
                success.append(result[1])
            else:
                failed.append(result[1])

        if len(failed) > 0:
            log.info(
                f"{self._cname()} failed to scrape {len(failed)} articles. Retrying..."
            )
            tasks = [
                self.scrape_article_with_retries(article, proxy_scraper)
                for article in failed
            ]
            results = await asyncio.gather(*tasks)
            for result in results:
                success.append(result[1])

        log.info(f"{self._cname()} scraped {len(success)} articles")
        return success

    async def scrape_article(self, article: dict, proxy: dict = None) -> tuple:
        async with httpx.AsyncClient(follow_redirects=True, proxies=proxy) as client:
            try:
                response = await client.get(article["url"])
                response.raise_for_status()
            except httpx.HTTPError as e:
                exc = "\n".join(
                    line
                    for line in str(e).split("\n")
                    if not line.startswith("For more information check: ")
                )
                log.error(
                    f"HTTP Exception {'' if proxy is None else '(proxy: ' + list(proxy.values())[0] + ')'}: {exc}"
                )
                return (False, article)

            # Parse the HTML document with BeautifulSoup to get the author
            soup = BeautifulSoup(response.content, "html.parser")
            author = soup.find("meta", {"name": "author"})
            if author is not None:
                author = author.get("content")
                if "," in author:
                    author = author.split(",")[0]
                author = author.strip()
            else:
                author = None

            # Parse the article using newspaper3k
            news_article = Article(str(response.url))
            news_article.download(input_html=response.content)
            news_article.parse()

            # Add the article's body, author, and read time to the dictionary
            article["body"] = news_article.text
            article["author"] = (
                author
                if author is not None and news_article.authors[0] != author
                else news_article.authors[0].strip()
                if news_article.authors
                else self.config.default_author
            )

            # Check if the author is all caps, convert to title case
            if article["author"].isupper():
                article["author"] = article["author"].title()

            article["read_time"] = str(readtime.of_text(news_article.text))

        return (True, article)

    async def scrape_article_with_retries(
        self,
        article,
        proxy_scraper,
        max_retries=10,
    ) -> tuple:
        for i in range(max_retries):
            proxy = proxy_scraper.get_next_proxy()
            log.info(
                f"Using proxy: {list(proxy.values())[0]} ({i+1}/{max_retries}) -> {article['url']}"
            )
            result = await self.scrape_article(article, proxy)
            if result[0]:
                return result
            else:
                if i == max_retries - 1:
                    return (False, article)
                else:
                    continue

    async def fetch_and_parse_rss(self, category: Category, save=True) -> list:
        articles = []
        async with httpx.AsyncClient() as client:
            mapped_category = self.config.category_mapping[category]
            log.info(f"{self._cname()} scraping for {category} ({mapped_category})")

            rss_url = self.config.rss_url.replace("[category]", mapped_category)
            rss_response = await client.get(rss_url)

            if rss_response.status_code == 200:
                if save:
                    await self.save_rss(rss_response.content, category)
                feed = feedparser.parse(rss_response.content)

                for entry in feed.entries:
                    article = {
                        "date": self.parse_date(entry.published),
                        "category": category.value,
                        "source": self.config.provider_name,
                        "title": entry.title,
                        "url": entry.link,
                        "image_url": entry.media_content[0]["url"]
                        if "media_content" in entry
                        else None,
                    }
                    articles.append(article)
            else:
                log.error(f"RSS status code: {rss_response.status_code}")
                return []

            return articles

    async def save_rss(self, rss_content: bytes, category: Category):
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_hr_min = datetime.now().strftime("%H-%M")

        os.makedirs(f"feeds/{current_date}", exist_ok=True)

        filename = f"feeds/{current_date}/{self.config.provider_name}-{category.value}-{current_hr_min}.xml"

        with open(filename, "wb") as f:
            f.write(rss_content)

        log.info(f"Saved RSS feed to {filename}")

    def _cname(self):
        return self.__class__.__name__

    def parse_date(self, date):
        date = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %z")
        return date.strftime("%b %d, %Y")


class GMANewsScraper(ScraperStrategy):
    @property
    def config(self) -> Config:
        return Config(
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


# class PhilstarScraper(ScraperStrategy):
#     @property
#     def config(self) -> Config:
#         return Config(
#             provider_name=Provider.Philstar.value,
#             category_mapping={
#                 Category.News: "headlines",
#                 Category.Opinion: "opinion",
#                 Category.Sports: "sports",
#                 Category.Technology: "technology",
#                 Category.Lifestyle: "lifestyle",
#                 Category.Business: "business",
#                 Category.Entertainment: "entertainment",
#             },
#             rss_url="https://www.philstar.com/rss/[category]",
#             default_author="Philstar.com",
#         )


class ManilaBulletinScraper(ScraperStrategy):
    @property
    def config(self) -> Config:
        return Config(
            provider_name=Provider.ManilaBulletin.value,
            category_mapping={
                category: category.value.lower() for category in Category
            },
            rss_url="https://mb.com.ph/rss/[category]",
            default_author="Manila Bulletin",
        )


class NewsScraper:
    def __init__(self, strategy: ScraperStrategy):
        self.strategy = strategy

    async def scrape_all(self, proxy_scraper) -> list:
        return await self.strategy.scrape_all(proxy_scraper=proxy_scraper)

    async def scrape_category(self, category: Category) -> list:
        return await self.strategy.scrape_category(category)

    async def scrape_articles(self, articles: list, proxy_scraper=None) -> list:
        return await self.strategy.scrape_articles(articles, proxy_scraper)

    # async def scrape_url(self, url: str) -> dict:
    #     return await self.strategy.scrape_article(url)


# Define a mapping between Provider and ScraperStrategy
provider_strategy_mapping = {
    Provider.GMANews: GMANewsScraper(),
    # Provider.Philstar: PhilstarScraper(),
    # Provider.News5: News5Scraper(),
    Provider.ManilaBulletin: ManilaBulletinScraper(),
    # Provider.INQUIRER: InquirerScraper(),
}


async def get_scraper_strategy(provider: Provider) -> ScraperStrategy:
    return provider_strategy_mapping.get(provider)
