from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from time import sleep
from database_utils import insert_data, db_path
import requests, os, sqlite3
from datetime import datetime
from enum import Enum
import xml.etree.ElementTree as ET
from newspaper import Article
import readtime


class Provider(Enum):
    GMANews = "gmanews"
    Philstar = "philstar"
    News5 = "news5"
    ManilaBulletin = "manilabulletin"
    INQUIRER = "inquirer"


class Category(Enum):
    News = "News"
    Opinion = "Opinion"
    Sports = "Sports"
    Technology = "Technology"
    Lifestyle = "Lifestyle"
    Business = "Business"
    Entertainment = "Entertainment"


class NewsScraper:
    def __init__(self, provider, conn=None):
        self.provider = provider
        self.conn = (
            sqlite3.connect(db_path(), check_same_thread=False)
            if conn is None
            else conn
        )

    def fetch_rss(self, url):
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

    def scrape(self):
        if self.provider == Provider.GMANews:
            return GMANews(self.conn).scrape()
        elif self.provider == Provider.Philstar:
            return Philstar(self.conn).scrape()
        elif self.provider == Provider.News5:
            return News5(self.conn).scrape()
        elif self.provider == Provider.ManilaBulletin:
            return ManilaBulletin(self.conn).scrape()
        elif self.provider == Provider.INQUIRER:
            return Inquirer(self.conn).scrape()
        else:
            raise Exception("Invalid provider")

    def scrape_article(self, article):
        try:
            response = requests.get(article["url"])

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
            news_article = Article(response.url)
            news_article.download()

            # Check if the article was successfully downloaded
            if news_article.download_state == 2:
                # Parse the article
                news_article.parse()
            else:
                # Print the error code
                print("Article download state:", news_article.download_state)
                # Return a flag to remove the article from the list
                return False

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

            # Sleep for 30 seconds
            sleep(30)

        except Exception as e:
            # logging.error("Error parsing article: %s", str(e))
            print("Error parsing article: ", str(e))
            # Return a flag to remove the article from the list
            return False

        # Return a flag to keep the article in the list
        return True

    def insert_articles(self, articles):
        print("Inserting articles...")
        data = []
        for article in articles:
            # Convert the article to a tuple and add it to the data list
            # (date, category, source, title, author, url, body, image_url, read_time)
            data.append(
                (
                    article["date"],
                    article["category"],
                    article["source"],
                    article["title"],
                    article["author"],
                    article["url"],
                    article["body"],
                    article["image_url"],
                    article["read_time"],
                )
            )
        insert_data(conn=self.conn, data=data)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()


class GMANews(NewsScraper):
    def __init__(self, conn):
        self.url = "https://data.gmanetwork.com/gno/rss/[category]/feed.xml"
        self.category_map = {
            Category.News: "news",
            Category.Opinion: "opinion",
            Category.Sports: "sports",
            Category.Technology: "scitech",
            Category.Lifestyle: "lifestyle",
            Category.Business: "money",
            Category.Entertainment: "showbiz",
        }
        self.conn = conn

    def parse_rss(self, url, category_map):
        articles = []
        reversed_category_map = {v: k for k, v in category_map.items()}

        # Fetch the RSS feed for each category
        for category in category_map.values():
            root = self.fetch_rss(url.replace("[category]", category))

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
                image_url = (
                    media_content.get("url") if media_content is not None else None
                )

                # Create a dictionary for each article
                article = {
                    "title": title,
                    "category": reversed_category_map[category].value,
                    "source": Provider.GMANews.value,
                    "url": link,
                    # "description": description,
                    "date": self.parse_date(pub_date),
                    "image_url": image_url,
                }

                # Append the dictionary to the list of articles
                articles.append(article)

        return articles

    def scrape(self):
        articles = self.parse_rss(self.url, self.category_map)
        article_limit = 20
        i = 0
        for article in articles[:article_limit]:
            i += 1
            print("Parsing article #", i, ": ", article["url"], sep="")
            success = self.scrape_article(article)
            if not success:
                articles.remove(article)

        # Get articles that has only authors key
        articles = list(filter(lambda article: "author" in article.keys(), articles))

        # Insert the articles to the database
        self.insert_articles(articles)

        print("Done scraping GMA News")

    def scrape_article_custom(self, article):
        # Download the article
        response = requests.get(article["url"])

        # Check if the article was successfully downloaded
        # if response.status_code == 200:
        #     # Parse the HTML document
        #     soup = BeautifulSoup(response.content, "html.parser")

        #     # Get author in meta tag
        #     author = soup.find("meta", {"name": "author"})

        #     # Extract the article's body
        #     body = soup.find("div", {"class": "article-content"})
        #     body = body.text if body is not None else None

        #     # Extract the article's author
        #     author = soup.find("div", {"class": "author"})
        #     author = author.text if author is not None else None

        #     # Add the body and author to the article dictionary
        #     article["body"] = body
        #     article["author"] = author
        #     article["read_time"] = str(readtime.of_text(body))

        #     # Insert the article to the database
        #     insert_data(conn=self.conn, data=[article])

        #     # Print the article
        #     print(article)

        #     # Sleep for 1 minute
        #     sleep(60)
        pass


class Philstar:
    def scrape(self):
        pass


class News5:
    def scrape(self):
        pass


class ManilaBulletin:
    def scrape(self):
        pass


class Inquirer:
    def scrape(self):
        pass


# Test
# with NewsScraper(Provider.GMANews) as scraper:
#     scraper.scrape()
