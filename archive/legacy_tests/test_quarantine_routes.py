# tests/test_quarantine_routes.py
import pytest
from flask import Flask
from src.api.quarantine_routes import quarantine_bp
from src.memory.quarantine_repo import init_quarantine_db, add_quarantine_item
import sqlite3

@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(quarantine_bp)
    
    # Use temporary DB for tests
    db_path = tmp_path / "test_kitty.db"
    conn = sqlite3.connect(db_path)
    init_quarantine_db(conn)
    
    # Inject connection getter for tests
    import src.memory.quarantine_repo as q_repo
    q_repo._get_conn = lambda: sqlite3.connect(db_path)
    
    add_quarantine_item("Test action", "user prompt", 0.4, "action", conn)
    conn.close()
    
    with app.test_client() as client:
        yield client

def test_get_quarantine_items(client):
    response = client.get('/api/quarantine')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["item_type"] == "action"

def test_update_quarantine_item(client):
    response = client.post('/api/quarantine/1', json={"status": "approved"})
    assert response.status_code == 200
    
    resp_get = client.get('/api/quarantine')
    assert len(resp_get.get_json()) == 0
