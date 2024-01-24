from typing import List, Dict, Any
from app.models.article import Article
import asyncio
import os
import aiosqlite
import logging

# Configure logging
log = logging.getLogger(__name__)


class AsyncDatabase:
    def __init__(self, db_name=None):
        self.db_name = db_name or os.getenv("DB_NAME")

    async def __aenter__(self):
        self.conn = await aiosqlite.connect(self.db_name)
        return self.conn

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.conn.close()

    async def create_article_table(self):
        query = """
            CREATE TABLE IF NOT EXISTS articles (
                article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                category TEXT,
                source TEXT,
                title TEXT,
                author TEXT,
                url TEXT UNIQUE,
                body TEXT,
                image_url TEXT,
                read_time TEXT
            );
        """
        await self.run_query(query)

    async def create_behavior_table(self):
        query = """
            CREATE TABLE IF NOT EXISTS behavior (
                behavior_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                article_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (article_id) REFERENCES articles (article_id)
            );
        """
        await self.run_query(query)

    async def run_query(self, query, params=None):
        cursor = await self.conn.cursor()
        try:
            await cursor.execute(query, params)
            await self.conn.commit()
        except Exception as e:
            await self.conn.rollback()
            raise e

    async def fetch(self, query, params=None):
        cursor = await self.conn.execute(query, params)
        return await cursor.fetchall()

    async def table_exists(self, table_name):
        query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';"
        result = await self.fetch(query)
        return bool(result)

    async def drop_table(self, table_name):
        query = f"DROP TABLE IF EXISTS {table_name};"
        await self.run_query(query)

    async def show_table(self, table_name):
        query = f"SELECT * FROM {table_name};"
        return await self.fetch(query)

    async def insert_data(self, data: List[Dict[str, Any]], table_name: str):
        if not data:
            return

        columns = ", ".join(data[0].keys())
        placeholders = ", ".join(["?" for _ in range(len(data[0]))])
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders});"
        values = [tuple(record.values()) for record in data]
        await self.run_query(query, values)

    async def insert_articles(self, articles: List[Article]):
        if not articles:
            return

        if not await self.table_exists("articles"):
            await self.create_article_table()

        existing_urls = await self.get_existing_urls()

        new_articles = []
        invalid_count = 0
        existing_count = 0
        empty_count = 0

        for article in articles:
            try:
                article_dict = article.model_dump()

                # Check if article already exists in the database
                if article_dict["url"] in existing_urls:
                    log.info(f"Article already exists: {article_dict['title']}")
                    existing_count += 1
                    continue

                # Check if "body" key exists and article body is empty
                if "body" not in article_dict or not article_dict["body"]:
                    log.info(f"Article body is empty: {article_dict['title']}")
                    empty_count += 1
                    continue

                # Log the article to be inserted
                log_article = article_dict.copy()
                log_article["body"] = log_article["body"][:10]
                log.info(f"Inserting article: {log_article}")

                new_articles.append(article_dict)

            except ValueError as e:
                log.warning(f"Invalid article: {e}")
                invalid_count += 1

        if new_articles:
            await self.insert_data(new_articles, "articles")

        log.info(
            f"Inserted {len(new_articles)}/{len(articles)} (dup:-{existing_count}, inv:-{invalid_count}, emt:+{empty_count}, ok=+{len(new_articles)-empty_count}) articles."
        )

    async def get_articles(self):
        query = "SELECT * FROM articles;"
        return await self.fetch(query)

    async def get_articles_by_provider(self, provider, empty_body=False):
        condition = "IS" if empty_body else "IS NOT"
        query = f"SELECT * FROM articles WHERE source = ? AND body {condition} '';"
        return await self.fetch(query, (provider,))

    async def delete_duplicates(self):
        query = """
            DELETE FROM articles
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM articles
                GROUP BY url
            );
        """
        await self.run_query(query)

    async def filter_new_urls(self, urls: List[str]) -> List[str]:
        if not urls:
            return []

        # Fetch existing URLs asynchronously
        existing_urls = await self.get_existing_urls()

        # Use asyncio.gather to parallelize URL filtering
        tasks = [self.filter_url(url, existing_urls) for url in urls]
        filtered_urls = await asyncio.gather(*tasks)

        return [url for url in filtered_urls if url is not None]

    async def get_existing_urls(self) -> set:
        query = "SELECT url FROM articles"
        result = await self.execute(query)
        return set(url[0] for url in result.fetchall())

    async def filter_url(self, url: str, existing_urls: set) -> str:
        # Check if the URL already exists
        if url not in existing_urls:
            return url
        return None

    async def url_exists(self, url):
        query = "SELECT 1 FROM articles WHERE url=?;"
        result = await self.fetch(query, (url,))
        return bool(result)

    async def delete_empty_body_by_provider(self, provider):
        query = "DELETE FROM articles WHERE body = '' AND source = ?;"
        await self.run_query(query, (provider,))


async def get_db():
    async with AsyncDatabase() as db:
        yield db