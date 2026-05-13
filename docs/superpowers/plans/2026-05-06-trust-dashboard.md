# Trust Dashboard & Quarantine Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the Trust Dashboard (Control Room) UI and the SQLite-backed Quarantine Queue for reviewing memory candidates, contradictions, and autonomous actions based on hybrid confidence scores.

**Architecture:** We will create a `quarantine_repo.py` to persist quarantine items in `kitty.db`, matching the pattern in `task_repo.py`. We will create REST endpoints in `src/api/quarantine_routes.py` to expose this queue to the frontend. On the frontend, we will build a `TrustDashboard` React component within `kitty-chat` and hook it into the main `page.tsx` navigation.

**Tech Stack:** SQLite, Python (Flask), React, Tailwind CSS.

---

### Task 1: SQLite Persistence for Quarantine Queue

**Files:**
- Create: `src/memory/quarantine_repo.py`
- Test: `tests/test_quarantine_repo.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_quarantine_repo.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal implementation**

```python
# src/memory/quarantine_repo.py
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "kitty.db")

def _get_conn():
    return sqlite3.connect(DB_PATH)

def init_quarantine_db(conn=None):
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quarantine_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_data TEXT NOT NULL,
            source_message TEXT,
            confidence_score REAL DEFAULT 0.0,
            item_type TEXT CHECK(item_type IN ('memory','contradiction','action')) NOT NULL DEFAULT 'memory',
            status TEXT CHECK(status IN ('pending','approved','rejected')) NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    if close:
        conn.close()

def add_quarantine_item(candidate_data: str, source_message: Optional[str] = None, 
                        confidence_score: float = 0.0, item_type: str = 'memory', conn=None) -> int:
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    cur = conn.execute(
        "INSERT INTO quarantine_queue (candidate_data, source_message, confidence_score, item_type, created_at) VALUES (?, ?, ?, ?, ?)",
        (candidate_data, source_message, confidence_score, item_type, datetime.now().isoformat())
    )
    conn.commit()
    tid = cur.lastrowid
    if close:
        conn.close()
    return tid

def get_pending_items(conn=None) -> List[Dict]:
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    rows = conn.execute("SELECT id, candidate_data, source_message, confidence_score, item_type, status, created_at FROM quarantine_queue WHERE status = 'pending' ORDER BY id DESC").fetchall()
    result = [{"id": r[0], "candidate_data": r[1], "source_message": r[2], 
               "confidence_score": r[3], "item_type": r[4], "status": r[5], "created_at": r[6]} for r in rows]
    if close:
        conn.close()
    return result

def update_item_status(item_id: int, status: str, conn=None) -> bool:
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    conn.execute("UPDATE quarantine_queue SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()
    if close:
        conn.close()
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_quarantine_repo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_quarantine_repo.py src/memory/quarantine_repo.py
git commit -m "feat: add SQLite persistence for quarantine queue"
```

### Task 2: Backend API Routes for Quarantine

**Files:**
- Create: `src/api/quarantine_routes.py`
- Modify: `src/api/__init__.py`
- Modify: `web.py`
- Test: `tests/test_quarantine_routes.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_quarantine_routes.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/api/quarantine_routes.py
from flask import Blueprint, jsonify, request
from src.memory.quarantine_repo import get_pending_items, update_item_status

quarantine_bp = Blueprint('quarantine', __name__, url_prefix='/api/quarantine')

@quarantine_bp.route('', methods=['GET'])
def list_quarantine():
    items = get_pending_items()
    return jsonify(items)

@quarantine_bp.route('/<int:item_id>', methods=['POST'])
def update_quarantine(item_id):
    data = request.get_json() or {}
    status = data.get("status")
    if status not in ['approved', 'rejected']:
        return jsonify({"error": "Invalid status"}), 400
    
    success = update_item_status(item_id, status)
    return jsonify({"success": success})
```

```python
# In src/api/__init__.py, add to exports:
from .quarantine_routes import quarantine_bp
# Ensure quarantine_bp is in the __all__ list or available for import
```

```python
# In web.py, import and register blueprint
# Find: from src.api import ( ... )
# Add: quarantine_bp
# Find: blueprints = [ ... ]
# Add: quarantine_bp
# (Modify web.py directly using sed or a python script, or manual edit instructions for the agent)
```
*(Agent note: Use the `replace` tool to add `quarantine_bp` to `src/api/__init__.py` and `web.py` imports and blueprint lists.)*

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_quarantine_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_quarantine_routes.py src/api/quarantine_routes.py src/api/__init__.py web.py
git commit -m "feat: add quarantine API routes"
```

### Task 3: Trust Dashboard Frontend Component

**Files:**
- Create: `kitty-chat/app/components/TrustDashboard.tsx`

- [ ] **Step 1: Write component implementation**

```tsx
// kitty-chat/app/components/TrustDashboard.tsx
import React, { useEffect, useState } from 'react';

interface QuarantineItem {
  id: number;
  candidate_data: string;
  source_message: string;
  confidence_score: number;
  item_type: string;
  status: string;
  created_at: string;
}

export default function TrustDashboard() {
  const [items, setItems] = useState<QuarantineItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchItems = async () => {
    try {
      const res = await fetch(`http://${window.location.hostname}:5001/api/quarantine`);
      if (res.ok) setItems(await res.json());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, []);

  const handleUpdate = async (id: number, status: string) => {
    try {
      await fetch(`http://${window.location.hostname}:5001/api/quarantine/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      });
      fetchItems();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-6 h-full overflow-y-auto bg-[var(--panel-bg)]">
      <h2 className="text-xl font-bold mb-2">Trust & Autonomy Dashboard</h2>
      <p className="text-[var(--dim-text)] text-sm mb-6">Review quarantined memory and blocked autonomous actions.</p>
      
      {loading ? <p>Loading...</p> : items.length === 0 ? <p>Queue is empty.</p> : (
        <div className="space-y-4">
          {items.map(item => (
            <div key={item.id} className="border border-[var(--border-color)] rounded-lg p-4 bg-black/20">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold px-2 py-1 rounded bg-[var(--accent-color)] text-white">
                  {item.item_type.toUpperCase()}
                </span>
                <span className="text-sm font-mono text-yellow-500">
                  Confidence: {item.confidence_score}
                </span>
              </div>
              <p className="font-medium mb-1">{item.candidate_data}</p>
              <p className="text-xs text-[var(--dim-text)] mb-4 font-mono whitespace-pre-wrap">Source: {item.source_message}</p>
              <div className="flex gap-2">
                <button onClick={() => handleUpdate(item.id, 'approved')} className="px-3 py-1 bg-green-600/80 text-white rounded text-sm hover:bg-green-600">Approve</button>
                <button onClick={() => handleUpdate(item.id, 'rejected')} className="px-3 py-1 bg-red-600/80 text-white rounded text-sm hover:bg-red-600">Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add kitty-chat/app/components/TrustDashboard.tsx
git commit -m "feat: add TrustDashboard React component"
```

### Task 4: Integrate Trust Dashboard into Garage UI

**Files:**
- Modify: `kitty-chat/app/page.tsx`

- [ ] **Step 1: Update page.tsx navigation and view**

*(Agent note: Use the `replace` tool carefully to inject TrustDashboard into `page.tsx`)*

Add import:
```tsx
import TrustDashboard from './components/TrustDashboard';
```

Update the `activeView` type state:
```tsx
const [activeView, setActiveView] = useState<'chat' | 'journal' | 'evals' | 'trust'>('chat');
```

Add the Trust button in the header nav (next to Evals):
```tsx
<button
  onClick={() => setActiveView('trust')}
  className="px-4 py-1.5 rounded-xl text-xs font-semibold transition-all"
  style={activeView === 'trust'
    ? { background: 'var(--accent-color)', color: '#fff' }
    : { color: 'var(--dim-text)' }}
>
  Trust
</button>
```

Add the view container in the main workspace section:
```tsx
<div className={`flex-1 ${activeView === 'trust' ? 'block' : 'hidden'}`}>
  <TrustDashboard />
</div>
```

- [ ] **Step 2: Commit**

```bash
git add kitty-chat/app/page.tsx
git commit -m "feat: integrate Trust Dashboard into main navigation"
```
