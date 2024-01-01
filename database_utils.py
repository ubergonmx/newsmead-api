import sqlite3
import os
import logging

# Logging
logger = logging.getLogger(__name__)

# [ ] TODO: Add to env
# Configuration
db_name = "newsmead.sqlite"
db_tbl_articles = "articles"

# [ ] TODO: Refactor queries
db_create_article_table_query = f"""
    CREATE TABLE IF NOT EXISTS {db_tbl_articles}
    (
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
db_insert_query = f"""
    INSERT OR IGNORE INTO {db_tbl_articles}
    (date, category, source, title, author, url, body, image_url, read_time)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
db_delete_duplicates_query = f"""
    DELETE FROM {db_tbl_articles}
    WHERE rowid NOT IN (
        SELECT MIN(rowid)
        FROM {db_tbl_articles}
        GROUP BY url
    )"""


# [ ] TODO: Add try-except blocks to all functions


# [ ] TODO: Properly implement get_db() function and close connection after use
# Get DB helper funciton
def get_db():
    return sqlite3.connect(db_name)


def db_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, db_name)


def run_query(conn, query):
    conn.cursor().execute(query)
    conn.commit()


# [ ] TODO: Add optional table_name parameter and refactor
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
    run_query(conn, db_create_article_table_query)


def drop_table(conn, table_name):
    delete = f"DROP TABLE {table_name}"
    run_query(conn, delete)


def show_table(conn, table_name):
    return conn.execute(f"SELECT * FROM {table_name}").fetchall()


# [ ] TODO: Refactor insert functions and add optional table_name parameter
def insert_data(conn, data, insert_query=db_insert_query):
    # Create the table if it does not exist
    if not table_exists(conn, db_tbl_articles):
        create_article_table(conn, db_tbl_articles)

    conn.cursor().executemany(insert_query, data)
    conn.commit()


# [ ] TODO: Discuss with team if bulk insert or insert one by one
def insert_articles(conn, articles):
    conn = get_db() if conn is None else conn
    new_articles = []
    existing_urls = set(
        url[0] for url in conn.execute("SELECT url FROM articles").fetchall()
    )
    invalid_count = 0
    existing_count = 0
    for article in articles:
        # Check if article is dict or not None
        if not isinstance(article, dict) or article is None:
            logger.warning(f"Article is not a dict or is None")
            invalid_count += 1
            continue

        # Check if article already exists in the database
        if article["url"] in existing_urls:
            logger.info(f"Article already exists: {article['title']}")
            existing_count += 1
            continue

        # Convert the article to a tuple and add it to the data list
        # (date, category, source, title, author, url, body, image_url, read_time)
        new_articles.append(
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
    insert_data(conn=conn, data=new_articles)
    logger.info(
        f"Inserted {len(new_articles)}/{len(articles)} (dup: {existing_count}, inv: {invalid_count}) articles."
    )


def delete_duplicates(conn):
    conn = get_db() if conn is None else conn
    run_query(conn, db_delete_duplicates_query)


# [ ] TODO: Fix this or remove
def db_exists(db_name):
    return os.path.exists(db_path())
