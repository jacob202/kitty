#!/usr/bin/env python3
"""
API Rate Limiting for Kitty
Prevents abuse and manages resource usage
"""

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RateLimit:
    """Rate limit configuration"""

    requests: int
    window: int  # seconds


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self):
        self.buckets: dict[str, dict] = defaultdict(
            lambda: {"tokens": 0, "last_update": time.time(), "requests": []}
        )
        self.limits: dict[str, RateLimit] = {
            "default": RateLimit(100, 60),  # 100 requests per minute
            "api": RateLimit(1000, 60),  # 1000 requests per minute
            "webhook": RateLimit(60, 60),  # 60 webhooks per minute
        }

    def is_allowed(self, key: str, limit_name: str = "default") -> bool:
        """Check if request is allowed"""
        limit = self.limits.get(limit_name, self.limits["default"])
        bucket = self.buckets[key]
        now = time.time()

        # Clean old requests
        bucket["requests"] = [req for req in bucket["requests"] if now - req < limit.window]

        # Check limit
        if len(bucket["requests"]) >= limit.requests:
            return False

        # Record request
        bucket["requests"].append(now)
        return True

    def get_remaining(self, key: str, limit_name: str = "default") -> int:
        """Get remaining requests"""
        limit = self.limits.get(limit_name, self.limits["default"])
        bucket = self.buckets[key]
        now = time.time()

        # Clean old requests
        bucket["requests"] = [req for req in bucket["requests"] if now - req < limit.window]

        return max(0, limit.requests - len(bucket["requests"]))

    def get_reset_time(self, key: str, limit_name: str = "default") -> float:
        """Get time until rate limit resets"""
        limit = self.limits.get(limit_name, self.limits["default"])
        bucket = self.buckets[key]

        if not bucket["requests"]:
            return 0

        oldest = min(bucket["requests"])
        return max(0, (oldest + limit.window) - time.time())


# Global instance
_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter"""
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter


def rate_limit(limit_name: str = "default"):
    """Decorator to rate limit a function"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Use function name as key
            key = func.__name__
            limiter = get_rate_limiter()

            if not limiter.is_allowed(key, limit_name):
                raise Exception(
                    f"Rate limit exceeded. Try again in {limiter.get_reset_time(key, limit_name):.0f}s"
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


# CLI
def main():
    """Rate limiter CLI"""
    import typer

    app = typer.Typer(help="Rate Limiting")

    @app.command("check")
    def check(
        key: str = typer.Argument(..., help="API key or identifier"),
        limit: str = typer.Option("default", "--limit", "-l"),
    ):
        """Check rate limit status"""
        limiter = get_rate_limiter()
        remaining = limiter.get_remaining(key, limit)
        reset_time = limiter.get_reset_time(key, limit)

        typer.echo(f"Key: {key}")
        typer.echo(f"Remaining: {remaining}")
        typer.echo(f"Reset in: {reset_time:.0f}s")

    app()


if __name__ == "__main__":
    main()
