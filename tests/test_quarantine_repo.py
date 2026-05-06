# tests/test_quarantine_repo.py
import sqlite3
import pytest
from src.memory.quarantine_repo import init_quarantine_db, add_quarantine_item, get_pending_items, update_item_status
from pathlib import Path

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_kitty.db"
    conn = sqlite3.connect(db_path)
    init_quarantine_db(conn)
    yield conn
    conn.close()

def test_quarantine_lifecycle(temp_db):
    item_id = add_quarantine_item(
        conn=temp_db,
        candidate_data="Prefers Go over Python",
        source_message="Let's use Go",
        confidence_score=0.65,
        item_type="memory"
    )
    
    pending = get_pending_items(conn=temp_db)
    assert len(pending) == 1
    assert pending[0]["id"] == item_id
    assert pending[0]["status"] == "pending"
    
    update_item_status(conn=temp_db, item_id=item_id, status="approved")
    
    pending_after = get_pending_items(conn=temp_db)
    assert len(pending_after) == 0
