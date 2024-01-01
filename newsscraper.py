from abc import ABC, abstractmethod
from enum import Enum
from bs4 import BeautifulSoup
from newspaper import Article
from datetime import datetime
import httpx
import asyncio
import xml.etree.ElementTree as ET
import readtime
import logging

# [ ] TODO: Import typing module to be precise with types (especially return types)

# Configure logging
logger = logging.getLogger(__name__)


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
    News5 = "news5"
    ManilaBulletin = "manilabulletin"
    INQUIRER = "inquirer"


# [ ] TODO: Add timer to benchmark performance
class ScraperStrategy(ABC):
    @property
    @abstractmethod
    def _category_mapping(self) -> dict:
        pass

    @property
    @abstractmethod
    def _rss_url(self) -> str:
        pass

    async def scrape_all(self, proxy_scraper=None) -> list:
        results = []
        for category in self._category_mapping:
            category_results = await self.scrape_category(category, proxy_scraper)
            results.extend(category_results)
        return results

    async def scrape_category(self, category: Category, proxy_scraper=None) -> list:
        if category in self._category_mapping:
            mapped_category = self._category_mapping[category]
            logger.info(f"{self._cname()} scraping for {category} ({mapped_category})")

            # Replace the [category] placeholder with the mapped category
            rss_url = self._rss_url.replace("[category]", mapped_category)

            # Fetch and parse the RSS feed asynchronously
            rss_root = await self.fetch_rss(rss_url)

            # Extract URLs from the RSS feed
            articles = await self.parse_rss(rss_root, mapped_category)

            # Scrape each URL asynchronously and return the results
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
                logger.info(
                    f"{self._cname()} failed to scrape {len(failed)} articles. Retrying..."
                )
                tasks = [
                    self.scrape_article_with_retries(article, proxy_scraper)
                    for article in failed
                ]
                results = await asyncio.gather(*tasks)
                for result in results:
                    success.append(result[1])

            logger.info(f"{self._cname()} scraped {len(success)} articles")
            logger.info(f"{self._cname()} scraping for {category} complete")
            return success
        else:
            logger.error(
                f"Category mapping not defined for {self._cname()}: {category}"
            )

    @abstractmethod
    async def scrape_article(self, article: dict, proxy: dict = None) -> tuple:
        pass

    async def scrape_article_with_retries(
        self,
        article,
        proxy_scraper,
        max_retries=5,
    ) -> tuple:
        for i in range(max_retries):
            proxy = proxy_scraper.get_next_proxy()
            result = await self.scrape_article(article, proxy)
            if result[0]:
                return result
            else:
                if i == max_retries - 1:  # If this was the last retry
                    return (False, article)
                else:
                    continue  # Try again with the next proxy

    @abstractmethod
    async def parse_rss(self, root, category) -> list:
        pass

    async def fetch_rss(self, url: str):
        async with httpx.AsyncClient() as client:
            # Asynchronously download the RSS feed
            rss_response = await client.get(url)

            # Check if the RSS feed was successfully downloaded
            if rss_response.status_code == 200:
                # Parse the XML document
                root = ET.fromstring(rss_response.content)
            else:
                # Print the error code
                logger.error(f"RSS status code: {rss_response.status_code}")
                # Return an empty list
                return []

            # Return the root element
            return root

    def _cname(self):
        # return in Title Case
        return self.__class__.__name__

    def parse_date(self, date):
        # Parse the date
        date = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %z")

        # Return the date in the format Nov 01, 2020
        return date.strftime("%b %d, %Y")

    def get_reversed_mapping(self, mapping):
        return {v: k for k, v in mapping.items()}


class GMANewsScraper(ScraperStrategy):
    @property
    def _rss_url(self) -> str:
        return "https://data.gmanetwork.com/gno/rss/[category]/feed.xml"

    @property
    def _category_mapping(self) -> dict:
        return {
            Category.News: "news",
            Category.Opinion: "opinion",
            Category.Sports: "sports",
            Category.Technology: "scitech",
            Category.Lifestyle: "lifestyle",
            Category.Business: "money",
            Category.Entertainment: "showbiz",
        }

    async def parse_rss(self, root, category) -> list:
        articles = []
        reversed_mapping = self.get_reversed_mapping(self._category_mapping)
        # Iterate through each 'item' in the RSS feed
        for item in root.findall(".//item"):
            title = item.find("title").text
            link = item.find("link").text
            # description = item.find("description").text
            pub_date = item.find("pubDate").text

            # Extracting media content URL (image URL)
            media_content = item.find(
                ".//media:content",
                namespaces={"media": "http://search.yahoo.com/mrss/"},
            )
            image_url = media_content.get("url") if media_content is not None else None

            # Create a dictionary for each article
            article = {
                "title": title,
                "category": reversed_mapping[category].value,
                "source": Provider.GMANews.value,
                "url": link,
                # "description": description,
                "date": self.parse_date(pub_date),
                "image_url": image_url,
            }

            # Append the dictionary to the list of articles
            articles.append(article)

        return articles

    async def scrape_article(self, article: dict, proxy: dict = None) -> tuple:
        async with httpx.AsyncClient(proxies=proxy) as client:
            try:
                # Asynchronously download the article
                response = await client.get(article["url"])
            except Exception as e:
                logger.error(f"Error downloading article: {str(e)}")
                return (False, article)

            # Check if the article was successfully downloaded
            if response.status_code != 200:
                # Print the error code
                logger.info(f"Article status code: {response.status_code}")
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
            news_article.download()

            # Check if the article was successfully downloaded
            if news_article.download_state == 2:
                # Parse the article
                news_article.parse()
            else:
                # Print the error code
                logger.error("Article download state:", news_article.download_state)
                return (False, article)

            # Add the article's body, author, and read time to the dictionary
            article["body"] = news_article.text
            article["author"] = (
                author.strip()
                if author is not None and news_article.authors[0] != author.strip()
                else news_article.authors[0].strip()
            )

            # Check if the author is all caps, convert to title case
            if article["author"].isupper():
                article["author"] = article["author"].title()

            article["read_time"] = str(readtime.of_text(news_article.text))

        return (True, article)


class NewsScraper:
    def __init__(self, strategy: ScraperStrategy):
        self.strategy = strategy

    async def scrape_all(self, proxy_scraper) -> list:
        return await self.strategy.scrape_all()

    async def scrape_category(self, category: Category) -> list:
        return await self.strategy.scrape_category(category)

    # async def scrape_url(self, url: str) -> dict:
    #     return await self.strategy.scrape_article(url)


# Define a mapping between Provider and ScraperStrategy
provider_strategy_mapping = {
    Provider.GMANews: GMANewsScraper(),
    # Provider.Philstar: PhilstarScraper(),
    # Provider.News5: News5Scraper(),
    # Provider.ManilaBulletin: ManilaBulletinScraper(),
    # Provider.INQUIRER: InquirerScraper(),
}


async def get_scraper_strategy(provider: Provider) -> ScraperStrategy:
    return provider_strategy_mapping.get(provider)
