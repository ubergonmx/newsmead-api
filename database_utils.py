import sqlite3, os

# Configuration
db_name = "newsmead.sqlite"
db_tbl_articles = "articles"
db_insert_query = f"""
    INSERT INTO {db_tbl_articles}
    (date, category, source, title, author, url, body, image_url, read_time)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """


def db_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, db_name)


def run_query(conn, query):
    conn.cursor().execute(query)
    conn.commit()


def get_articles(conn):
    return conn.execute(f"SELECT * FROM {db_tbl_articles}").fetchall()


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


# Fix this
def db_exists(db_name):
    return os.path.exists(db_path())
