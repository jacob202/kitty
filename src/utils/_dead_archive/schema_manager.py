import json
import os

from pydantic import ValidationError

from src.schemas.hardware import BaseEntity, Edge


class SchemaManager:
    def __init__(self, log_path: str = "canonical_log.jsonl"):
        self.log_path = log_path

    def validate_log(self):
        """Validate every entry in the log against current schemas."""
        if not os.path.exists(self.log_path):
            return {"status": "ok", "message": "No log file found."}

        stats = {"BaseEntity": 0, "Edge": 0, "errors": 0}
        valid_lines = []

        with open(self.log_path) as f:
            for i, line in enumerate(f):
                try:
                    data = json.loads(line)
                    schema = data.get("_schema")

                    if schema == "BaseEntity":
                        BaseEntity(**data)
                        stats["BaseEntity"] += 1
                    elif schema == "Edge":
                        Edge(**data)
                        stats["Edge"] += 1
                    else:
                        print(f"[Schema] Unknown schema at line {i}: {schema}")
                        stats["errors"] += 1
                        continue

                    valid_lines.append(line)
                except ValidationError as e:
                    print(f"[Schema] Validation error at line {i}: {e}")
                    stats["errors"] += 1
                except Exception as e:
                    print(f"[Schema] General error at line {i}: {e}")
                    stats["errors"] += 1

        return stats

    def migrate_log(self, target_version: int = 1):
        """Migrate the log to a target schema version by injecting missing default fields."""
        if not os.path.exists(self.log_path):
            return 0

        temp_log = self.log_path + ".tmp"
        migrated_count = 0

        with open(self.log_path) as f_in, open(temp_log, "w") as f_out:
            for line in f_in:
                try:
                    data = json.loads(line)
                    # Example: Hardware Schema v1 -> v2 migration
                    # Add default 'confidence' if missing in properties
                    if data.get("_schema") == "BaseEntity" and "confidence" not in data.get("properties", {}):
                        data["properties"]["confidence"] = 1.0
                        migrated_count += 1

                    # Add schema version if missing
                    if "_v" not in data:
                        data["_v"] = target_version

                    f_out.write(json.dumps(data) + "\n")
                except Exception:
                    f_out.write(line)

        os.replace(temp_log, self.log_path)
        print(f"[Schema] Migrated {migrated_count} entries to version {target_version}")
        return migrated_count

if __name__ == "__main__":
    sm = SchemaManager()
    print(f"Schema Validation Results: {sm.validate_log()}")
