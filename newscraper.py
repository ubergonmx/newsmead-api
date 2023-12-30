from abc import ABC, abstractmethod
from enum import Enum
import httpx
import asyncio
import xml.etree.ElementTree as ET
import datetime


class Category(Enum):
    News = "News"
    Opinion = "Opinion"
    Sports = "Sports"
    Technology = "Technology"
    Lifestyle = "Lifestyle"
    Business = "Business"
    Entertainment = "Entertainment"


class Provider(Enum):
    GMANews = "gmanews"
    Philstar = "philstar"
    News5 = "news5"
    ManilaBulletin = "manilabulletin"
    INQUIRER = "inquirer"


class ScraperStrategy(ABC):
    @property
    @abstractmethod
    def _category_mapping(self) -> dict:
        pass

    @property
    @abstractmethod
    def _rss_url(self) -> str:
        pass

    async def scrape_all(self):
        results = []
        for category in self._category_mapping:
            category_results = await self.scrape_category(category)
            results.extend(category_results)
        return results

    async def scrape_category(self, category: Category) -> list:
        if category in self._category_mapping:
            mapped_category = self._category_mapping[category]
            print(f"{self._cname()} scraping for {category} ({mapped_category})")

            # Replace the [category] placeholder with the mapped category
            rss_url = self._rss_url.replace("[category]", mapped_category)

            # Fetch and parse the RSS feed asynchronously
            rss_root = await self.fetch_rss(rss_url)

            # Extract URLs from the RSS feed
            urls = await self.parse_rss(rss_root, mapped_category)

            # Scrape each URL asynchronously and return the results
            tasks = [self.scrape_url(url) for url in urls]
            return await asyncio.gather(*tasks)
        else:
            print(f"Category mapping not defined for {self._cname()}: {category}")

    @abstractmethod
    async def scrape_url(self, url: str) -> dict:
        pass

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
                print("RSS status code:", rss_response.status_code)
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
                "category": self.get_reversed_mapping()[category].value,
                "source": Provider.GMANews.value,
                "url": link,
                # "description": description,
                "date": self.parse_date(pub_date),
                "image_url": image_url,
            }

            # Append the dictionary to the list of articles
            articles.append(article)


class NewsScraper:
    async def __init__(self, strategy: ScraperStrategy):
        self.strategy = strategy

    async def scrape_all(self) -> list:
        try:
            return self.strategy.scrape_all()
        except Exception as e:
            print(f"Error scraping {self.strategy._cname()}: {e}")
            return []

    async def scrape_category(self, category: Category) -> list:
        try:
            return self.strategy.scrape_category(category)
        except Exception as e:
            print(f"Error scraping {self.strategy._cname()}: {e}")
            return []

    async def scrape_url(self, url: str) -> dict:
        try:
            return self.strategy.scrape_url(url)
        except Exception as e:
            print(f"Error scraping {self.strategy._cname()}: {e}")
            return []


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


# Example usage:
gma_scraper = GMANewsScraper()

news_scraper_gma = NewsScraper(gma_scraper)

news_scraper_gma.scrape_category(Category.Technology)
