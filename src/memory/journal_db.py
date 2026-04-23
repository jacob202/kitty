import random
import sqlite3
import struct
import threading
import time
from pathlib import Path

import requests

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DB_PATH = _PROJECT_ROOT / "data" / "db" / "orange_lab_pka.db"

class PKAMemoryDB:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = _DB_PATH
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._write_lock = threading.RLock()
        self._setup()

    def _setup(self):
        """Initializes the hybrid SQLite + Vector schema."""
        with self._write_lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA cache_size=-8192")

            # Standard relational table for hard metadata
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    type TEXT,
                    content TEXT,
                    mood TEXT,
                    energy INTEGER
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_timestamp ON entries(timestamp)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(type)")

            # Intelligent Profiling Tables
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source_context TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_category ON user_profiles(category)")

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_llm TEXT,
                    import_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    raw_content TEXT,
                    processed BOOLEAN DEFAULT 0
                )
            """)

            # Vector Table for semantic search
            try:
                self.conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS vec_entries USING vec0(embedding float[768])")
            except sqlite3.OperationalError:
                self.conn.execute("CREATE TABLE IF NOT EXISTS vec_entries (rowid INTEGER PRIMARY KEY, embedding BLOB)")


    EMBEDDING_DIM = 768

    _EMBEDDING_CACHE_MAX = 500

    def _get_embedding(self, text: str) -> list[float]:
        """Calls local Ollama (nomic-embed-text) to generate a 768-d vector.

        Falls back to sentence-transformers if Ollama is unreachable.
        If that also fails, uses a random unit-normalised vector.
        """
        if not hasattr(self, '_emb_cache'):
            self._emb_cache = {}

        if text in self._emb_cache:
            return self._emb_cache[text]

        # Evict oldest entries if cache is too large
        if len(self._emb_cache) > _EMBEDDING_CACHE_MAX:
            oldest_keys = list(self._emb_cache.keys())[:_EMBEDDING_CACHE_MAX // 2]
            for k in oldest_keys:
                del self._emb_cache[k]

        url = "http://localhost:11434/api/embeddings"
        payload = {"model": "nomic-embed-text", "prompt": text}
        try:
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            embedding = response.json().get("embedding", [])
            if embedding and len(embedding) == self.EMBEDDING_DIM:
                self._emb_cache[text] = embedding
                return embedding
        except Exception as e:
            print(f"[WARN] Ollama unavailable ({e}). Attempting sentence-transformers fallback...")

        # Fallback 1: sentence-transformers (pad 384-d to 768-d if necessary)
        try:
            from sentence_transformers import SentenceTransformer
            if not hasattr(self, '_fallback_model'):
                print("[DB] Loading fallback embedding model (paraphrase-MiniLM-L3-v2)...")
                self._fallback_model = SentenceTransformer('paraphrase-MiniLM-L3-v2')

            # all-MiniLM-L6-v2 returns 384-d, we need 768-d to match schema
            embedding_384 = self._fallback_model.encode(text).tolist()
            # Pad with zeros to match 768-d
            embedding_768 = embedding_384 + [0.0] * (self.EMBEDDING_DIM - len(embedding_384))
            self._emb_cache[text] = embedding_768
            return embedding_768
        except Exception as fallback_e:
            print(f"[ERROR] Sentence-transformers fallback failed ({fallback_e}). Using random vector.")

        # Fallback 2: random vector so inserts always succeed
        vec = [random.gauss(0, 1) for _ in range(self.EMBEDDING_DIM)]
        magnitude = sum(x * x for x in vec) ** 0.5
        embedding = [x / magnitude for x in vec] if magnitude > 0 else vec

        self._emb_cache[text] = embedding

        return embedding

    def _serialize_vector(self, vector: list[float]) -> bytes:
        """Packs the Python float list into a binary blob for sqlite-vec."""
        return struct.pack(f"{len(vector)}f", *vector)

    def add_entry(self, content: str, entry_type: str = "journal", mood: str = None, energy: int = None):
        """Stores the text and its semantic meaning simultaneously."""
        print(f"[DB] Generating embedding for new {entry_type} entry...")
        vector = self._get_embedding(content)
        if not vector:
            print("[DB] Aborting insert: No embedding generated.")
            return None

        vector_blob = self._serialize_vector(vector)
        with self._write_lock:
            with self.conn:
                # 1. Insert structural data
                cursor = self.conn.execute(
                    "INSERT INTO entries (type, content, mood, energy) VALUES (?, ?, ?, ?)",
                    (entry_type, content, mood, energy)
                )
                row_id = cursor.lastrowid

                # 2. Insert vector data bound to the same rowid
                self.conn.execute(
                    "INSERT INTO vec_entries (rowid, embedding) VALUES (?, ?)",
                    (row_id, vector_blob)
                )
                print(f"[DB] Successfully stored entry #{row_id} with semantic embedding.")
                return row_id
    def hybrid_search(self, query: str, limit: int = 5, filter_type: str = None,
                     min_similarity: float = 0.3) -> list[dict]:
        """
        Enhanced hybrid search with caching and longer TTL.
        """
        cache_key = f"{query}_{limit}_{filter_type}"
        if hasattr(self, '_search_cache'):
            if cache_key in self._search_cache:
                cached_time, results = self._search_cache[cache_key]
                if time.time() - cached_time < 1800:  # 30 minute cache (up from 5 min)
                    return results

        query_vector = self._get_embedding(query)
        if not query_vector:
            return []

        query_blob = self._serialize_vector(query_vector)

        # Check if vec_entries is a virtual table or a real one
        cursor = self.conn.execute("SELECT sql FROM sqlite_master WHERE name='vec_entries'")
        schema = cursor.fetchone()[0]
        is_virtual = "VIRTUAL" in schema.upper()

        if is_virtual:
            sql = """
                SELECT e.id, e.timestamp, e.type, e.content, e.mood, e.energy, v.distance
                FROM vec_entries v
                JOIN entries e ON v.rowid = e.id
                WHERE v.embedding MATCH ? AND k = ? AND v.distance < ?
            """
            max_distance = 1.0 - min_similarity
            params = [query_blob, limit * 2, max_distance]
        else:
            # Fallback for standard table (non-vector search)
            # This is a basic content fallback since we can't do vector math in pure SQL without the extension
            sql = """
                SELECT id, timestamp, type, content, mood, energy, 0.5 as distance
                FROM entries
                WHERE content LIKE ? OR content LIKE ?
            """
            # Extract a few words for broader match if the query is long
            first_word = query.split()[0] if query.split() else query
            params = [f"%{query}%", f"%{first_word}%"]

        # Inject standard SQL filters dynamically
        if filter_type:
            # Add filter to correctly handle both cases
            if "WHERE" in sql:
                sql += " AND type = ?"
            else:
                sql += " WHERE type = ?"
            params.append(filter_type)

        if is_virtual:
            sql += " ORDER BY v.distance ASC"
        else:
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(sql, params)
        raw_results = [dict(row) for row in cursor.fetchall()]

        # Apply additional filtering and limit
        results = []
        for result in raw_results:
            similarity = 1.0 - result['distance']
            if similarity >= min_similarity:
                result['similarity'] = similarity
                results.append(result)
            if len(results) >= limit:
                break

        # Cache results
        if not hasattr(self, '_search_cache'):
            self._search_cache = {}
        self._search_cache[cache_key] = (time.time(), results)

        # Clean old cache entries
        self._clean_search_cache()

        return results

    def _clean_search_cache(self):
        """Remove cache entries older than 10 minutes."""
        if not hasattr(self, '_search_cache'):
            return

        current_time = time.time()
        keys_to_remove = []
        for key, (cached_time, _) in self._search_cache.items():
            if current_time - cached_time > 600:  # 10 minutes
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._search_cache[key]

    def get_entries(self):
        """Returns all entries from the metadata table."""
        with self._write_lock:
            rows = self.conn.execute("SELECT * FROM entries ORDER BY timestamp DESC").fetchall()
            return [dict(row) for row in rows]

# Alias for compatibility with existing web.py references
JournalDB = PKAMemoryDB

# ==========================================
# TEST EXECUTION
# ==========================================
if __name__ == "__main__":
    db = PKAMemoryDB("test_pka.db")
    # 1. Add some test data
    # Note: Requires Ollama to be running with nomic-embed-text
    db.add_entry("Feeling great today, crushed a 10k run.", mood="High", energy=9)
    db.add_entry("Struggling with a nasty Python memory leak in the orchestrator.", mood="Frustrated", energy=3)
    db.add_entry("Paco mentioned we need to update the UI variables.", entry_type="contact")

    # 2. Test the hybrid search
    print("\n--- Semantic Search Test: 'coding problems' ---")
    results = db.hybrid_search("coding problems", limit=1)
    for r in results:
        print(f"Match: {r['content']} (Distance: {r['distance']:.3f})")
