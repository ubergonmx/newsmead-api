from typing import Any, Optional
from app.models.article import Article, Filter
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
        return self

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

    async def run_query(self, query, params=None, is_many=False):
        cursor = await self.conn.cursor()
        try:
            if is_many:
                await cursor.executemany(query, params)
            else:
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

    async def insert_data(self, data: list[dict[str, Any]], table_name: str):
        if not data:
            return

        columns = ", ".join(data[0].keys())
        placeholders = ", ".join(["?" for _ in range(len(data[0]))])
        query = (
            f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders});"
        )
        values = [tuple(record.values()) for record in data]
        await self.run_query(query, values, is_many=True)

    async def insert_articles(self, articles: list[Article]):
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
                    article_dict["body"] = ""
                    empty_count += 1

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

    async def get_articles(self, filter: Filter, page: int = 1, page_size: int = 10):
        conditions = []
        params = []

        if filter.source is not None:
            conditions.append("source = ?")
            params.append(filter.source)

        if filter.category is not None:
            conditions.append("category = ?")
            params.append(filter.category)

        if filter.startDate is not None:
            conditions.append("date >= ?")
            params.append(filter.startDate)

        if filter.endDate is not None:
            conditions.append("date <= ?")
            params.append(filter.endDate)

        conditions_sql = " AND ".join(conditions)
        query = (
            f"SELECT * FROM articles WHERE {conditions_sql} ORDER BY {filter.sortBy or 'date'} LIMIT ? OFFSET ?;"
            if conditions
            else f"SELECT * FROM articles ORDER BY {filter.sortBy or 'date'} LIMIT ? OFFSET ?;"
        )

        offset = (page - 1) * page_size
        params.extend([page_size, offset])

        return Article().model_load(await self.fetch(query, tuple(params)))

    async def get_empty_articles(self, provider: str) -> list[Article]:
        query = "SELECT * FROM articles WHERE (author = '' OR body = '' OR image_url = '') AND source = ?;"
        return Article().model_load(await self.fetch(query, (provider,)))

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

    async def filter_new_urls(
        self, articles: list[Article], category: str = None
    ) -> list[Article]:
        if not articles:
            return []

        if not await self.table_exists("articles"):
            return articles

        # Fetch existing URLs asynchronously
        existing_urls = await self.get_existing_urls(category=category)

        # Use asyncio.gather to parallelize URL filtering
        tasks = [self.filter_url(article, existing_urls) for article in articles]
        filtered_articles = await asyncio.gather(*tasks)

        return [article for article in filtered_articles if article is not None]

    async def get_existing_urls(self, category: str = None) -> set:
        if not await self.table_exists("articles"):
            return set()
        query = "SELECT url FROM articles"
        query += " WHERE category=?" if category else ""
        params = (category,) if category else None
        result = await self.fetch(query, params)
        return set(url[0] for url in result)

    async def filter_url(self, article: Article, existing_urls: set) -> Article:
        if article.url not in existing_urls:
            return article
        return None

    async def url_exists(self, url):
        query = "SELECT 1 FROM articles WHERE url=?;"
        result = await self.fetch(query, (url,))
        return bool(result)

    async def update_empty_articles(self, articles: list[Article]):
        if not articles:
            return

        if not await self.table_exists("articles"):
            return

        query = "UPDATE articles SET author=?, body=?, image_url=? WHERE url=?;"
        params = [
            (article.author, article.body, article.image_url, article.url)
            for article in articles
        ]
        await self.run_query(query, params)


async def get_db() -> AsyncDatabase:
    async with AsyncDatabase() as db:
        yield db
