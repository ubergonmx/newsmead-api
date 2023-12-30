from abc import ABC, abstractmethod
from enum import Enum
import httpx
import xml.etree.ElementTree as ET


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
    @abstractmethod
    async def scrape_all(self):
        pass

    @abstractmethod
    async def scrape_category(self, category: Category):
        pass

    @abstractmethod
    async def scrape_url(self, url: str):
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

    def parse_date(self, date):
        # Parse the date
        date = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %z")

        # Return the date in the format Nov 01, 2020
        return date.strftime("%b %d, %Y")


class GMANewsScraper(ScraperStrategy):
    rss_url = "https://data.gmanetwork.com/gno/rss/[category]/feed.xml"
    category_mapping = {
        Category.News: "news",
        Category.Opinion: "opinion",
        Category.Sports: "sports",
        Category.Technology: "scitech",
        Category.Lifestyle: "lifestyle",
        Category.Business: "money",
        Category.Entertainment: "showbiz",
    }

    async def scrape_all(self):
        for category in self.category_mapping:
            self.scrape_category(category)

    async def scrape_category(self, category: Category):
        if category in self.category_mapping:
            mapped_category = self.category_mapping[category]
            print(f"Scraping GMA News for {category} ({mapped_category})")
        else:
            print(f"Category mapping not defined for GMA News: {category}")

    async def scrape_url(self, url: str):
        return super().scrape_url(url)


class PhilstarScraper(ScraperStrategy):
    category_mapping = {Category.Opinion: "Opinion"}

    async def scrape_all(self):
        for category in self.category_mapping:
            self.scrape_category(category)

    async def scrape_category(self, category: Category):
        if category in self.category_mapping:
            mapped_category = self.category_mapping[category]
            print(f"Scraping Philstar for {category} ({mapped_category})")
        else:
            print(f"Category mapping not defined for Philstar: {category}")

    async def scrape_url(self, url: str):
        return super().scrape_url(url)


class NewsScraper:
    async def __init__(self, strategy: ScraperStrategy):
        self.strategy = strategy

    async def scrape_all(self):
        return self.strategy.scrape_all()

    async def scrape_category(self, category: Category):
        return self.strategy.scrape(category)

    async def scrape_url(self, url: str):
        return self.strategy.scrape_url(url)


# Define a mapping between Provider and ScraperStrategy
provider_strategy_mapping = {
    Provider.GMANews: GMANewsScraper(),
    Provider.Philstar: PhilstarScraper(),
    # Add mappings for other providers
}


async def get_scraper_strategy(provider: Provider) -> ScraperStrategy:
    return provider_strategy_mapping.get(provider)


# Example usage:
gma_scraper = GMANewsScraper()
philstar_scraper = PhilstarScraper()

news_scraper_gma = NewsScraper(gma_scraper)
news_scraper_philstar = NewsScraper(philstar_scraper)

news_scraper_gma.scrape_category(Category.Technology)
news_scraper_philstar.scrape_category(Category.Opinion)
