
import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/curation_status.db")
MANIFEST_PATH = Path("data/canonical_library_manifest.json")

def init_status_db():
    """Initializes the database to track the curation progress of the 901 canonical books."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create the status table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS curation_status (
            id TEXT PRIMARY KEY,
            original_path TEXT,
            priority INTEGER,
            size INTEGER,
            status TEXT DEFAULT 'pending',
            extraction_done BOOLEAN DEFAULT 0,
            synthesis_done BOOLEAN DEFAULT 0,
            assembly_done BOOLEAN DEFAULT 0,
            error_message TEXT,
            processed_at DATETIME
        )
    """)
    
    # Load manifest
    if not MANIFEST_PATH.exists():
        print(f"Error: Manifest not found at {MANIFEST_PATH}")
        return

    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    # Populate table
    print(f"Populating database with {len(manifest)} canonical books...")
    for norm_name, data in manifest.items():
        cursor.execute("""
            INSERT OR IGNORE INTO curation_status (id, original_path, priority, size)
            VALUES (?, ?, ?, ?)
        """, (norm_name, data['path'], data['priority'], data['size']))
    
    conn.commit()
    conn.close()
    print(f"✅ Status database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_status_db()
