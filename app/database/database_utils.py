import sqlite3
import os
import logging
import dotenv

dotenv.load_dotenv()

# Configure logging
log = logging.getLogger(__name__)

# Configuration
db_name = os.getenv("DB_NAME", "newsmead.sqlite")
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


# Get DB helper function
def get_db():
    return sqlite3.connect(db_name)


def db_path():
    project_dir_name = os.getenv("PROJECT_DIR_NAME")
    current_file_path = os.path.abspath(__file__)
    path_components = current_file_path.split(os.sep)
    project_root_index = path_components.index(project_dir_name)
    project_root = os.sep.join(path_components[: project_root_index + 1])
    return os.path.join(project_root, db_name)


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
                "image_url": article[8],
                "readTime": article[9],
            }
        )

    return cleaned_articles


def get_articles_by_provider(conn, provider, empty_body=False):
    conn = get_db() if conn is None else conn
    articles = conn.execute(
        f"SELECT * FROM {db_tbl_articles} WHERE source = '{provider}' AND body {'IS' if empty_body else 'IS NOT'} ''"
    ).fetchall()
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
                "image_url": article[8],
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
    run_query(conn, db_create_article_table_query)


def drop_table(conn, table_name):
    delete = f"DROP TABLE {table_name}"
    run_query(conn, delete)


def show_table(conn, table_name):
    return conn.execute(f"SELECT * FROM {table_name}").fetchall()
