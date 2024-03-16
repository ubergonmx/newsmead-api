import sqlite3


def merge_databases(main_db_path, second_db_path):
    # Connect to the main database
    conn = sqlite3.connect(main_db_path)
    print(f"Connected to main database: {main_db_path}")

    # Attach the second database
    conn.execute(f"ATTACH DATABASE '{second_db_path}' AS second_db")
    print(f"Attached second database: {second_db_path}")

    # Copy articles from the second database to the main one
    conn.execute(
        """
        INSERT INTO articles (date, category, source, title, author, url, body, image_url, read_time)
        SELECT date, category, source, title, author, url, body, image_url, read_time
        FROM second_db.articles
        WHERE url NOT IN (SELECT url FROM articles)
    """
    )
    print("Merged articles from second database to main database")

    # Commit changes
    conn.commit()
    print("Committed changes")

    # Detach the second database
    conn.execute("DETACH DATABASE second_db")
    print("Detached second database")

    conn.close()
    print("Closed connection")


if __name__ == "__main__":
    import sys

    # Get the database paths from the command line arguments
    main_db_path = sys.argv[1] if len(sys.argv) > 1 else "newsmead.sqlite"
    second_db_path = sys.argv[2] if len(sys.argv) > 2 else "1.sqlite"

    merge_databases(main_db_path, second_db_path)
