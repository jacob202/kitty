
import sqlite3
from pathlib import Path

def inspect_db_schema(db_path):
    """
    Connects to an SQLite database and prints its schema.
    """
    if not db_path.exists():
        print(f"Database file not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get a list of all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    # For each table, print its schema
    for table_name in tables:
        table_name = table_name[0]
        print(f"--- Table: {table_name} ---")
        cursor.execute(f'PRAGMA table_info("{table_name}");')
        columns = cursor.fetchall()
        for column in columns:
            print(column)
        print()

    conn.close()

if __name__ == "__main__":
    DEFAULT_DB = Path.home() / "kitty-services/open-webui-data/webui.db"
    inspect_db_schema(DEFAULT_DB)
