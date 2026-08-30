import sys

from gateway import db, project_store
from gateway.signal_store import SIGNALS_DB_FILE


def cleanup_project(project_id: int):
    # Product hard-delete is intentionally disabled. E2E cleanup archives its
    # synthetic project instead of bypassing the same integrity boundary.
    try:
        project_store.update_fields(project_id, status="archived")
    except project_store.ProjectNotFound:
        # Cleanup is intentionally idempotent: the synthetic project may have
        # already been removed by an earlier cleanup/recovery pass.
        pass
    # also remove any signals with payload containing project_id
    db.migrate(SIGNALS_DB_FILE)
    with db.connect(SIGNALS_DB_FILE) as conn:
        conn.execute("DELETE FROM signals WHERE json_extract(payload, '$.project_id') = ?", (project_id,))
        conn.commit()
    print(f"Cleaned up project {project_id} and related signals.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cleanup_project(int(sys.argv[1]))
