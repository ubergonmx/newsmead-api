import sqlite3
import os
import json
import logging
from database_utils import (
    run_query,
    table_exists,
    show_table,
    drop_table,
    create_article_table,
    db_name,
)

# Configure logging
log = logging.getLogger(__name__)


# db_name = input("Enter database name: ") + ".sqlite"
# if not db_exists(db_name):
#     if input(f"Database does not exist. Create? (y/n): ") == "n":
#         exit()

# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Join the script directory with the database name
db_path = os.path.join(script_dir, db_name)

# Connect to the SQLite database
conn = sqlite3.connect(db_path)

table_name = input("Enter table name: ")

# [ ] TODO: Refactor table creation - involve database_utils.py
if not (table_exists(conn, table_name)):
    if input(f'Table "{table_name}" does not exist. Create? (y/n): ') == "y":
        create_article_table(conn, table_name)
    else:
        conn.close()
        quit()

while True:
    ans = input(
        "\n\nWhat do you want to do?\n 1) Show table \n 2) Reset table (DISABLED) \n 3) Enter SQL query \n q) Exit \n\n >"
    )

    if ans == "1":
        table = show_table(conn, table_name)
        if table == None:
            print(f'Table "{table_name}" is empty.')
            continue
        print(json.dumps(table, indent=2))
    elif ans == "2":
        # [ ] TODO: Add backup functionality before dropping table. Discuss with team.
        # if input("This process is NOT reversible. Are you sure (y/n): ") == "y":
        #     drop_table(conn, table_name)
        #     create_article_table(conn, table_name)

        # print(f'Reset "{table_name}".')
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
