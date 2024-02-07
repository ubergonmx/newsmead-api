from typing import Any, Optional
from app.models.article import Article, Filter
from app.utils.nlp.lang import Lang
from firebase_admin import firestore, credentials
import firebase_admin
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
            CREATE TABLE IF NOT EXISTS behaviors (
                behavior_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                history TEXT,
                impression_log TEXT
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

    async def execute_query(self, query, params=None):
        return await self.conn.execute(query, params)

    async def fetch(self, query, params=None):
        cursor = await self.execute_query(query, params)
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

    async def get_article_by_id(self, article_id: int) -> Article:
        query = "SELECT * FROM articles WHERE article_id=?;"
        result = await self.fetch(query, (article_id,))
        if not result:
            return None
        return self._set_article(result[0])

    async def get_articles(
        self, filter: Filter, page: int = 1, page_size: int = 10
    ) -> list[Article]:
        conditions = []
        params = []

        if filter.source is not None:
            sources = filter.source.split(",")
            placeholders = ", ".join("?" for _ in sources)
            conditions.append(f"source IN ({placeholders})")
            params.extend(sources)

        if filter.category is not None:
            categories = filter.category.split(",")
            placeholders = ", ".join("?" for _ in categories)
            conditions.append(f"category IN ({placeholders})")
            params.extend(categories)

        if filter.startDate is not None:
            conditions.append("date >= ?")
            params.append(filter.startDate)

        if filter.endDate is not None:
            conditions.append("date <= ?")
            params.append(filter.endDate)

        if filter.text is not None:
            conditions.append("title LIKE ? OR body LIKE ?")
            params.extend([f"%{filter.text}%", f"%{filter.text}%"])

        conditions_sql = " AND ".join(conditions)
        sort_order = "RANDOM()" if filter.sortBy == "recent" else "date DESC"
        query = (
            f"SELECT * FROM articles WHERE {conditions_sql} ORDER BY {sort_order} LIMIT ? OFFSET ?;"
            if conditions
            else f"SELECT * FROM articles ORDER BY {sort_order} LIMIT ? OFFSET ?;"
        )

        offset = (page - 1) * page_size
        params.extend([page_size, offset])

        log.info(f"Query: {query}")
        log.info(f"Params: {params}")
        results = await self.fetch(query, params)
        # Filter out non-English articles and articles with empty bodies
        lang = Lang()
        articles = [
            article
            for article in self._set_articles(results)
            if article.body and lang.is_english(article.title)
        ]
        return articles

    async def get_all_articles_cursor(self) -> aiosqlite.Cursor:
        query = "SELECT * FROM articles;"
        return await self.execute_query(query)

    async def get_empty_articles(self, provider: str) -> list[Article]:
        query = "SELECT * FROM articles WHERE (author = '' OR author IS NULL OR body = '' OR body IS NULL OR image_url = '' OR image_url IS NULL) AND source = ?;"
        articles = await self.fetch(query, (provider,))
        empty_articles = self._set_articles(articles)
        log.info(f"Empty articles ({provider}): {len(empty_articles)}")
        return empty_articles

    def _set_articles(self, articles) -> list[Article]:
        return [self._set_article(article) for article in articles]

    def _set_article(self, article) -> Article:
        return Article(
            article_id=article[0],
            date=article[1],
            category=article[2],
            source=article[3],
            title=article[4],
            author=article[5],
            url=article[6],
            body=article[7],
            image_url=article[8],
            read_time=article[9],
        )

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

        query = "UPDATE articles SET author=?, url=?, body=?, image_url=? WHERE article_id=?;"
        params = [
            (
                article.author,
                article.url,
                article.body,
                article.image_url,
                article.article_id,
            )
            for article in articles
        ]
        await self.run_query(query, params, is_many=True)
        log.info(f"Updated {len(articles)} articles ({articles[0].source}).")

    async def get_article_count(self):
        query = "SELECT COUNT(1) FROM articles;"
        result = await self.fetch(query)
        return result[0][0]

    def _get_firestore_db(self):
        cred = credentials.Certificate(os.getenv("FIREBASE_ADMIN_SDK_NAME"))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        return firestore.client()

    def _get_user_history(self, user_id: str) -> list[str]:
        db = self._get_firestore_db()
        history = db.collection("users").document(user_id).collection("history")
        return [doc.id for doc in history.stream()]

    async def get_user_history(self, user_id: str) -> list[str]:
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_user_history, user_id
        )


async def get_db():
    async with AsyncDatabase() as db:
        yield db
