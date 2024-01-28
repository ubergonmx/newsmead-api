from datetime import datetime
import sqlite3
import json
from database_utils import (
    run_query,
    table_exists,
    show_table,
    create_article_table,
    db_path,
)

# Connect to the SQLite database
conn = sqlite3.connect(db_path())

# table_name = input("Enter table name: ")

# if not (table_exists(conn, table_name)):
#     if input(f'Table "{table_name}" does not exist. Create? (y/n): ') == "y":
#         create_article_table(conn, table_name)
#     else:
#         conn.close()
#         quit()

table_name = "articles"

while True:
    ans = input(
        "\n\nWhat do you want to do?\n 1) Show table \n 2) Custom script \n 3) Enter SQL query \n q) Exit \n\n >"
    )

    if ans == "1":
        table = show_table(conn, table_name)
        if table == None:
            print(f'Table "{table_name}" is empty.')
            continue
        print(json.dumps(table, indent=2))
    elif ans == "2":
        # This block is for custom scripts
        c = conn.cursor()

        # Select all rows from the articles table
        c.execute("SELECT article_id, date FROM articles")
        rows = c.fetchall()

        # For each row
        for row in rows:
            id, date = row

            # Try to parse the date and convert it to the desired format
            try:
                new_date = datetime.strptime(date, "%b %d, %Y-%I:%M %p").strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                try:
                    new_date = datetime.strptime(date, "%b %d, %Y").strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    print(f"Could not parse date: {date}")
                    continue

            # Update the date in the database
            c.execute(
                "UPDATE articles SET date = ? WHERE article_id = ?", (new_date, id)
            )

        # Commit the changes and close the connection
        conn.commit()

        # End of custom scripts
        conn.close()
        exit()

    elif ans == "3":
        sql = input("Enter SQL query: ")
        try:
            run_query(conn, sql)
        except Exception as e:
            print(f"Error: {str(e)}")

    elif ans == "q":
        conn.close()
        quit()
