"""Shared ChromaDB connection manager to avoid multiple client instances."""

from threading import Lock
import chromadb
from chromadb.config import Settings


class ChromaDBManager:
    """Singleton-style manager for ChromaDB client instances."""
    _instances = {}
    _lock = Lock()

    @classmethod
    def get_client(cls, persist_dir: str, settings: Settings = None) -> chromadb.Client:
        """Get or create a ChromaDB client for the given persist directory."""
        key = (persist_dir, str(settings)) if settings else persist_dir
        with cls._lock:
            if key not in cls._instances:
                if settings:
                    cls._instances[key] = chromadb.PersistentClient(path=persist_dir, settings=settings)
                else:
                    cls._instances[key] = chromadb.PersistentClient(path=persist_dir)
            return cls._instances[key]

    @classmethod
    def get_collection(cls, persist_dir: str, collection_name: str, settings: Settings = None):
        """Get or create a collection using a shared client."""
        client = cls.get_client(persist_dir, settings)
        return client.get_or_create_collection(name=collection_name)
