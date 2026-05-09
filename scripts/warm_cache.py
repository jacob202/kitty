#!/usr/bin/env python3
"""
Pre-populate SemanticCache with common prompt patterns.
Run this once to warm the cache for faster agent startup.
"""

import hashlib
import sqlite3
import time
from pathlib import Path

CACHE_DB = Path("data/cache/semantic_cache.db")

COMMON_PATTERNS = [
    {
        "provider": "openrouter",
        "model": "qwen/qwen3-coder:free",
        "system": "You are a coding assistant.",
        "user": "What files are in src/?",
        "response": "Use glob or ls tool to list files in the src/ directory.",
    },
    {
        "provider": "openrouter",
        "model": "qwen/qwen3-coder:free",
        "system": "You are a coding assistant.",
        "user": "Count lines in this file",
        "response": "Use wc -l  to count lines.",
    },
    {
        "provider": "openrouter",
        "model": "qwen/qwen3-coder:free",
        "system": "You are a coding assistant.",
        "user": "Is the server running?",
        "response": "Check with curl -s http://localhost:5001/api/brief",
    },
    {
        "provider": "openrouter",
        "model": "deepseek/deepseek-v4-flash",
        "system": "You are Kitty, a coding assistant.",
        "user": "Run tests",
        "response": "pytest tests/ -q --tb=short",
    },
]

def _compute_key(provider: str, model: str, system_prompt: str, user_prompt: str) -> str:
    system_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]
    user_hash = hashlib.sha256(user_prompt.encode()).hexdigest()[:16]
    return f"{provider}:{model}:{system_hash}:{user_hash}"

def main():
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                cache_key TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                system_prompt_hash TEXT NOT NULL,
                user_prompt_hash TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL,
                access_count INTEGER DEFAULT 1
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache_entries(last_accessed)")
        
        now = time.time()
        added = 0
        
        for pattern in COMMON_PATTERNS:
            cache_key = _compute_key(
                pattern["provider"],
                pattern["model"],
                pattern["system"],
                pattern["user"]
            )
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO cache_entries 
                    (cache_key, provider, model, system_prompt_hash, user_prompt_hash, 
                     response, created_at, last_accessed, access_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    cache_key,
                    pattern["provider"],
                    pattern["model"],
                    hashlib.sha256(pattern["system"].encode()).hexdigest()[:16],
                    hashlib.sha256(pattern["user"].encode()).hexdigest()[:16],
                    pattern["response"],
                    now,
                    now,
                ))
                added += 1
            except Exception as e:
                print(f"Skipped {pattern['model']}: {e}")
        
    print(f"✓ Pre-populated {added} cache entries → {CACHE_DB}")

if __name__ == "__main__":
    main()