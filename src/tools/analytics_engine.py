import os
from typing import Any

import duckdb


class AnalyticsEngine:
    def __init__(self, log_path: str = "canonical_log.jsonl", sqlite_path: str = "orange_lab_pka.db"):
        self.log_path = log_path
        self.sqlite_path = sqlite_path
        self.con = duckdb.connect(database=':memory:')

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Run a SQL query against the JSONL log and optional SQLite database."""
        # 1. Register the JSONL log as a view
        if os.path.exists(self.log_path):
            self.con.execute(f"CREATE OR REPLACE VIEW log AS SELECT * FROM read_json_auto('{self.log_path}')")

        # 2. Attach SQLite database if it exists
        if os.path.exists(self.sqlite_path):
            self.con.execute(f"ATTACH '{self.sqlite_path}' AS pka (TYPE SQLITE)")

        try:
            # 3. Execute Query
            result = self.con.execute(sql).fetch_df()
            return result.to_dict('records')
        except Exception as e:
            print(f"[Analytics] Query failed: {e}")
            return [{"error": str(e)}]

    def get_entity_summary(self) -> list[dict[str, Any]]:
        """Utility to get counts of all entities in the log."""
        sql = "SELECT type, count(*) as count FROM log GROUP BY type"
        return self.query(sql)

if __name__ == "__main__":
    ae = AnalyticsEngine()
    # Example: ae.query("SELECT * FROM log WHERE type = 'Component'")
