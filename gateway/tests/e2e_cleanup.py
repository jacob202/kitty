import sys
from gateway import project_store, signal_store, db
from gateway.paths import KITTY_DB_FILE, SIGNALS_DB_FILE

def cleanup_project(project_id: int):
    project_store.delete(project_id)
    # also remove any signals with payload containing project_id
    db.migrate(SIGNALS_DB_FILE)
    with db.connect(SIGNALS_DB_FILE) as conn:
        conn.execute("DELETE FROM signals WHERE json_extract(payload, '$.project_id') = ?", (project_id,))
        conn.commit()
    print(f"Cleaned up project {project_id} and related signals.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cleanup_project(int(sys.argv[1]))
