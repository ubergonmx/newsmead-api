from abc import ABC, abstractmethod
from enum import Enum


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
    def scrape_all(self):
        pass

    @abstractmethod
    def scrape_category(self, category: Category):
        pass

    @abstractmethod
    def scrape_url(self, url: str):
        pass

    def fetch_rss(self, url: str):
        # Download the RSS feed
        rss = requests.get(url)

        # Check if the RSS feed was successfully downloaded
        if rss.status_code == 200:
            # Parse the XML document
            root = ET.fromstring(rss.content)
        else:
            # Print the error code
            print("RSS status code:", rss.status_code)
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

    def scrape_all(self):
        for category in self.category_mapping:
            self.scrape_category(category)

    def scrape_category(self, category: Category):
        if category in self.category_mapping:
            mapped_category = self.category_mapping[category]
            print(f"Scraping GMA News for {category} ({mapped_category})")
        else:
            print(f"Category mapping not defined for GMA News: {category}")

    def scrape_url(self, url: str):
        return super().scrape_url(url)


class PhilstarScraper(ScraperStrategy):
    category_mapping = {Category.Opinion: "Opinion"}

    def scrape_all(self):
        for category in self.category_mapping:
            self.scrape_category(category)

    def scrape_category(self, category: Category):
        if category in self.category_mapping:
            mapped_category = self.category_mapping[category]
            print(f"Scraping Philstar for {category} ({mapped_category})")
        else:
            print(f"Category mapping not defined for Philstar: {category}")

    def scrape_url(self, url: str):
        return super().scrape_url(url)


class NewsScraper:
    def __init__(self, strategy: ScraperStrategy):
        self.strategy = strategy

    def scrape_all(self):
        return self.strategy.scrape_all()

    def scrape_category(self, category: Category):
        return self.strategy.scrape(category)

    def scrape_url(self, url: str):
        return self.strategy.scrape_url(url)


# Define a mapping between Provider and ScraperStrategy
provider_strategy_mapping = {
    Provider.GMANews: GMANewsScraper(),
    Provider.Philstar: PhilstarScraper(),
    # Add mappings for other providers
}


def get_scraper_strategy(provider: Provider) -> ScraperStrategy:
    return provider_strategy_mapping.get(provider)


# Example usage:
gma_scraper = GMANewsScraper()
philstar_scraper = PhilstarScraper()

news_scraper_gma = NewsScraper(gma_scraper)
news_scraper_philstar = NewsScraper(philstar_scraper)

news_scraper_gma.scrape_category(Category.Technology)
news_scraper_philstar.scrape_category(Category.Opinion)
