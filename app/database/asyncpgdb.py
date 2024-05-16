from typing import Any, Optional
from app.models.article import Article, Filter
from app.utils.nlp.lang import Lang
import asyncpg
import asyncio
import os
import logging
import json

# Configure logging
log = logging.getLogger(__name__)


class AsyncPGDatabase:
    def __init__(self, db_url=None):
        self.db_url = db_url or os.getenv("DATABASE_URL")

    async def __aenter__(self):
        self.conn = await asyncpg.connect(self.db_url)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.conn.close()

    async def create_article_table(self):
        query = """
            CREATE TABLE IF NOT EXISTS articles (
                article_id SERIAL PRIMARY KEY,
                date TEXT,
                category TEXT,
                source TEXT,
                title TEXT,
                author TEXT,
                url TEXT UNIQUE,
                body TEXT,
                image_url TEXT,
                read_time TEXT,
                tsv tsvector
            );
            CREATE INDEX IF NOT EXISTS tsv_idx ON articles USING gin(tsv);
            CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
            ON articles FOR EACH ROW EXECUTE FUNCTION
            tsvector_update_trigger(tsv, 'pg_catalog.english', title, body);
        """
        await self.run_query(query)

    async def create_behavior_table(self):
        query = """
            CREATE TABLE IF NOT EXISTS behaviors (
                behavior_id SERIAL PRIMARY KEY,
                user_id TEXT,
                time TEXT,
                history TEXT,
                impression_news TEXT,
                score JSONB
            );
        """
        await self.run_query(query)

    async def run_query(self, query, params=None, is_many=False):
        async with self.conn.transaction():
            try:
                if is_many:
                    await self.conn.executemany(query, params)
                else:
                    await self.conn.execute(query, *params)
            except Exception as e:
                raise e

    async def fetch(self, query, params=None):
        async with self.conn.transaction():
            return await self.conn.fetch(query, *params)

    async def table_exists(self, table_name):
        query = f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}');"
        result = await self.fetch(query)
        return result[0]["exists"]

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
        placeholders = ", ".join(f"${i+1}" for i in range(len(data[0])))
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) ON CONFLICT (url) DO NOTHING;"
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

    async def insert_behavior(
        self, user_id: str, time: str, history: str, impression_news: str, score: dict
    ):
        if not await self.table_exists("behaviors"):
            await self.create_behavior_table()

        await self.insert_data(
            [
                {
                    "user_id": user_id,
                    "time": time,
                    "history": history,
                    "impression_news": impression_news,
                    "score": json.dumps(score),
                }
            ],
            "behaviors",
        )

        log.info(f"Inserted behavior for user {user_id}.")

    async def get_article_by_id(self, article_id: int) -> Optional[Article]:
        query = "SELECT * FROM articles WHERE article_id=$1;"
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
            placeholders = ", ".join(
                f"${i+1}" for i in range(len(params), len(params) + len(sources))
            )
            conditions.append(f"source IN ({placeholders})")
            params.extend(sources)

        if filter.category is not None:
            categories = filter.category.split(",")
            placeholders = ", ".join(
                f"${i+1}" for i in range(len(params), len(params) + len(categories))
            )
            conditions.append(f"category IN ({placeholders})")
            params.extend(categories)

        if filter.startDate is not None:
            conditions.append(f"date >= ${len(params)+1}")
            params.append(filter.startDate)

        if filter.endDate is not None:
            conditions.append(f"date <= ${len(params)+1}")
            params.append(filter.endDate)

        if filter.text is not None:
            conditions.append(f"tsv @@ to_tsquery('english', ${len(params)+1})")
            params.append(filter.text.replace(" ", " & "))

        conditions_sql = " AND ".join(conditions)
        sort_order = (
            "date DESC"
            if filter.sortBy is None or filter.sortBy == "recent"
            else "RANDOM()"
        )
        query = (
            f"SELECT * FROM articles WHERE {conditions_sql} ORDER BY {sort_order} LIMIT ${len(params)+1} OFFSET ${len(params)+2};"
            if conditions
            else f"SELECT * FROM articles ORDER BY {sort_order} LIMIT ${len(params)+1} OFFSET ${len(params)+2};"
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

    async def get_all_articles_cursor(self) -> asyncpg.Cursor:
        query = "SELECT * FROM articles;"
        return await self.conn.cursor(query)

    async def get_empty_articles(self, provider: str) -> list[Article]:
        query = "SELECT * FROM articles WHERE (author = '' OR author IS NULL OR body = '' OR body IS NULL OR image_url = '' OR image_url IS NULL) AND source = $1;"
        articles = await self.fetch(query, (provider,))
        empty_articles = self._set_articles(articles)
        log.info(f"Empty articles ({provider}): {len(empty_articles)}")
        return empty_articles

    def _set_articles(self, articles) -> list[Article]:
        return [self._set_article(article) for article in articles]

    def _set_article(self, article) -> Article:
        return Article(
            article_id=article["article_id"],
            date=article["date"],
            category=article["category"],
            source=article["source"],
            title=article["title"],
            author=article["author"],
            url=article["url"],
            body=article["body"],
            image_url=article["image_url"],
            read_time=article["read_time"],
        )

    async def delete_duplicates(self):
        query = """
            DELETE FROM articles
            WHERE ctid NOT IN (
                SELECT min(ctid)
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

        existing_urls = await self.get_existing_urls(category=category)
        tasks = [self.filter_url(article, existing_urls) for article in articles]
        filtered_articles = await asyncio.gather(*tasks)

        return [article for article in filtered_articles if article is not None]

    async def get_existing_urls(self, category: str = None) -> set:
        if not await self.table_exists("articles"):
            return set()
        query = "SELECT url FROM articles"
        query += " WHERE category=$1" if category else ""
        params = (category,) if category else None
        result = await self.fetch(query, params)
        return set(url["url"] for url in result)

    async def filter_url(
        self, article: Article, existing_urls: set
    ) -> Optional[Article]:
        if article.url not in existing_urls:
            return article
        return None

    async def url_exists(self, url):
        query = "SELECT 1 FROM articles WHERE url=$1;"
        result = await self.fetch(query, (url,))
        return bool(result)

    async def update_empty_articles(self, articles: list[Article]):
        if not articles:
            return

        if not await self.table_exists("articles"):
            return

        query = "UPDATE articles SET author=$1, url=$2, body=$3, image_url=$4 WHERE article_id=$5;"
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
        return result[0]["count"]

    def _get_firestore_db(self):
        cred = credentials.Certificate(os.getenv("FIREBASE_ADMIN_SDK_NAME"))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        return firestore.client()

    def _get_user_history(self, user_id: str) -> list[str]:
        db = self._get_firestore_db()
        user_ref = db.collection("users").document(user_id)
        if not user_ref.get().exists:
            return ["-1"]
        history = user_ref.collection("history")
        return [doc.id for doc in history.stream()]

    def _get_user_preferences(self, user_id: str) -> list[str]:
        db = self._get_firestore_db()
        user_ref = db.collection("users").document(user_id)
        if not user_ref.get().exists:
            return ["-1"]
        categories = user_ref.collection("preferences").document("categories")
        return categories.get().to_dict().get("categories", [])

    async def get_user_history(self, user_id: str) -> list[str]:
        history = await asyncio.get_event_loop().run_in_executor(
            None, self._get_user_history, user_id
        )
        if history and history[0] == "-1":
            raise ValueError(f"User {user_id} does not exist.")
        return history

    async def get_user_preferences(self, user_id: str) -> list[str]:
        preferences = await asyncio.get_event_loop().run_in_executor(
            None, self._get_user_preferences, user_id
        )
        if preferences and preferences[0] == "-1":
            raise ValueError(f"User {user_id} does not exist.")
        return preferences


async def get_db():
    async with AsyncPGDatabase() as db:
        yield db
