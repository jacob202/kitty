CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    active_form TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    created_at REAL,
    updated_at REAL
);
