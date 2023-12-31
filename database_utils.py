import sqlite3
import os
import logging


# Logging
logger = logging.getLogger(__name__)

# Configuration
db_name = "newsmead.sqlite"
db_tbl_articles = "articles"
db_insert_query = f"""
    INSERT INTO {db_tbl_articles}
    (date, category, source, title, author, url, body, image_url, read_time)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """


# Get DB helper funciton
def get_db():
    return sqlite3.connect(db_name)


def db_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, db_name)


def run_query(conn, query):
    conn.cursor().execute(query)
    conn.commit()


def get_articles(conn):
    conn = get_db() if conn is None else conn
    articles = conn.execute(f"SELECT * FROM {db_tbl_articles}").fetchall()
    cleaned_articles = []

    # date, category, source, title, author, url, body, image_url, read_time

    for article in articles:
        cleaned_articles.append(
            {
                "date": article[1],
                "category": article[2],
                "source": article[3],
                "title": article[4],
                "author": article[5],
                "url": article[6],
                "body": article[7],
                "imageUrl": article[8],
                "readTime": article[9],
            }
        )

    return cleaned_articles


def table_exists(conn, table_name):
    return (
        conn.cursor()
        .execute(
            f"""SELECT name FROM sqlite_master WHERE type='table'
  AND name='{table_name}'; """
        )
        .fetchall()
        != []
    )


def create_article_table(conn, table_name):
    # Create the table with the following columns
    # article_id, date, category, source, title, author, url, body, image_url, read_time
    create = f"""
        CREATE TABLE {table_name}
        (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            category TEXT,
            source TEXT,
            title TEXT,
            author TEXT,
            url TEXT,
            body TEXT,
            image_url TEXT,
            read_time TEXT
        );
        """
    run_query(conn, create)


def drop_table(conn, table_name):
    delete = f"DROP TABLE {table_name}"
    run_query(conn, delete)


def show_table(conn, table_name):
    return conn.execute(f"SELECT * FROM {table_name}").fetchall()


def insert_data(conn, data, insert_query=db_insert_query):
    # Create the table if it does not exist
    if not table_exists(conn, db_tbl_articles):
        create_article_table(conn, db_tbl_articles)

    conn.cursor().executemany(insert_query, data)
    conn.commit()


def insert_articles(conn, articles):
    conn = get_db() if conn is None else conn
    data = []
    for article in articles:
        # Check if article is dict or not None
        if not isinstance(article, dict) or article is None:
            logger.warning(f"Article is not a dict or is None: {article}")
            continue

        logger.info(f"Inserting article: {article['title']}")
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
    insert_data(conn=conn, data=data)


# Fix this
def db_exists(db_name):
    return os.path.exists(db_path())
