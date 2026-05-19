
import sqlite3
import json
from pathlib import Path

def council_audit(db_path):
    """
    A deep audit of the OpenWebUI database from the perspectives of:
    - Database/Architecture Engineer (Data Integrity)
    - AI App Developer (Meta-data usage)
    - AI Researcher (Processing Status)
    """
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Database Engineer: Check for malformed or missing metadata
    print("--- Database Engineer Audit ---")
    cursor.execute("SELECT id, filename, meta FROM file LIMIT 5")
    for fid, name, meta in cursor.fetchall():
        try:
            m_data = json.loads(meta) if meta else {}
            print(f"File: {name} | Meta Keys: {list(m_data.keys())}")
        except:
            print(f"File: {name} | Error: Malformed JSON in meta column")

    # 2. AI Researcher: Audit processing status and content availability
    print("\n--- AI Researcher Audit ---")
    cursor.execute("SELECT id, filename, data FROM file")
    status_counts = {"success": 0, "error": 0, "unknown": 0}
    errors = []
    
    for fid, name, data_raw in cursor.fetchall():
        try:
            d = json.loads(data_raw) if data_raw else {}
            status = d.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            if status == "error":
                errors.append(f"{name}: {d.get('message', 'No error message')}")
        except:
            status_counts["unknown"] += 1

    print(f"Status Summary: {status_counts}")
    if errors:
        print(f"Sample Errors (First 3): {errors[:3]}")

    # 3. AI App Developer: Check for "meta" tags in the knowledge base
    print("\n--- AI App Developer Audit ---")
    cursor.execute("SELECT name, meta FROM knowledge")
    for name, meta in cursor.fetchall():
        m = json.loads(meta) if meta else {}
        print(f"KB: {name} | Meta: {m}")

    conn.close()

if __name__ == "__main__":
    DB_PATH = Path.home() / "kitty-services/open-webui-data/webui.db"
    council_audit(DB_PATH)
