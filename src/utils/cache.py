#!/usr/bin/env python3
"""
Kitty Cache - API response caching layer
Caches Ollama and other API responses for faster performance
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class KittyCache:
    """Cache for API responses"""

    def __init__(self, cache_dir: str = "data/cache", ttl: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl  # Time to live in seconds
        self.memory_cache: dict[str, tuple[Any, float]] = {}

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key"""
        data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(data.encode()).hexdigest()

    def _get_file_path(self, key: str) -> Path:
        """Get file path for cache key"""
        return self.cache_dir / f"{key}.json"

    def get(self, prefix: str, *args, **kwargs) -> Any | None:
        """Get cached value"""
        key = self._make_key(prefix, *args, **kwargs)

        # Check memory cache first
        if key in self.memory_cache:
            value, timestamp = self.memory_cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.memory_cache[key]

        # Check disk cache
        file_path = self._get_file_path(key)
        if file_path.exists():
            try:
                with open(file_path) as f:
                    data = json.load(f)
                if time.time() - data.get("timestamp", 0) < self.ttl:
                    self.memory_cache[key] = (data["value"], data["timestamp"])
                    return data["value"]
                else:
                    file_path.unlink()
            except Exception:
                pass

        return None

    def set(self, prefix: str, value: Any, *args, **kwargs):
        """Set cached value"""
        key = self._make_key(prefix, *args, **kwargs)
        timestamp = time.time()

        # Save to memory
        self.memory_cache[key] = (value, timestamp)

        # Save to disk
        file_path = self._get_file_path(key)
        data = {"value": value, "timestamp": timestamp, "key": key}
        with open(file_path, "w") as f:
            json.dump(data, f)

    def invalidate(self, prefix: str = None):
        """Invalidate cache"""
        if prefix:
            key_prefix = self._make_key(prefix)[:8]
            for f in self.cache_dir.glob("*.json"):
                if f.stem.startswith(key_prefix):
                    f.unlink()
        else:
            for f in self.cache_dir.glob("*.json"):
                f.unlink()
        self.memory_cache.clear()

    def cleanup(self):
        """Remove expired cache entries"""
        now = time.time()
        for f in self.cache_dir.glob("*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                if now - data.get("timestamp", 0) > self.ttl:
                    f.unlink()
            except Exception:
                pass

    def get_stats(self) -> dict:
        """Get cache statistics"""
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)

        return {
            "entries": len(files),
            "memory_entries": len(self.memory_cache),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
        }


# Global instance
_cache = None


def get_cache() -> KittyCache:
    """Get global cache instance"""
    global _cache
    if _cache is None:
        _cache = KittyCache()
    return _cache


# Decorator for caching function results
def cached(ttl: int = 3600):
    """Decorator to cache function results"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()
            key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"

            result = cache.get(key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        return wrapper

    return decorator


# CLI
def main():
    """Cache CLI"""
    import typer

    app = typer.Typer(help="Kitty Cache")

    @app.command("stats")
    def show_stats():
        """Show cache statistics"""
        cache = get_cache()
        stats = cache.get_stats()

        typer.echo(f"Disk entries: {stats['entries']}")
        typer.echo(f"Memory entries: {stats['memory_entries']}")
        typer.echo(f"Total size: {stats['total_size_mb']:.2f} MB")

    @app.command("clear")
    def clear_cache():
        """Clear all cache"""
        cache = get_cache()
        cache.invalidate()
        typer.echo("Cache cleared")

    @app.command("cleanup")
    def cleanup():
        """Remove expired cache"""
        cache = get_cache()
        cache.cleanup()
        typer.echo("Expired cache removed")

    app()


if __name__ == "__main__":
    main()
