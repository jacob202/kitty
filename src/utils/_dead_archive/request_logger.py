#!/usr/bin/env python3
"""
Request Logging for Kitty
Logs all API requests and responses
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class LogEntry:
    """A log entry"""

    timestamp: str
    method: str
    path: str
    status: int
    duration_ms: float
    request_size: int
    response_size: int
    user_agent: str = ""
    error: str | None = None


class RequestLogger:
    """Log all requests"""

    def __init__(self, log_dir: str = "data/logs/requests"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_file = self._get_log_file()

    def _get_log_file(self) -> Path:
        """Get current log file"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"requests_{date_str}.jsonl"

    def log(
        self,
        method: str,
        path: str,
        status: int = 200,
        duration_ms: float = 0,
        request_size: int = 0,
        response_size: int = 0,
        user_agent: str = "",
        error: str | None = None,
    ):
        """Log a request"""
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            method=method,
            path=path,
            status=status,
            duration_ms=duration_ms,
            request_size=request_size,
            response_size=response_size,
            user_agent=user_agent,
            error=error,
        )

        # Check if we need a new file
        log_file = self._get_log_file()

        with open(log_file, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def get_stats(self, days: int = 1) -> dict:
        """Get logging statistics"""
        total_requests = 0
        error_count = 0
        total_duration = 0

        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            log_file = self.log_dir / f"requests_{date.strftime('%Y-%m-%d')}.jsonl"

            if log_file.exists():
                with open(log_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            total_requests += 1
                            total_duration += entry.get("duration_ms", 0)
                            if entry.get("status", 200) >= 400:
                                error_count += 1
                        except Exception:
                            pass

        return {
            "total_requests": total_requests,
            "error_count": error_count,
            "error_rate": error_count / max(1, total_requests),
            "avg_duration_ms": total_duration / max(1, total_requests),
        }


# Global instance
_logger = None


def get_logger() -> RequestLogger:
    """Get global logger"""
    global _logger
    if _logger is None:
        _logger = RequestLogger()
    return _logger


# CLI
def main():
    """Logger CLI"""
    import typer

    app = typer.Typer(help="Request Logging")

    @app.command("stats")
    def stats(
        days: int = typer.Option(1, "--days", "-d", help="Number of days"),
    ):
        """Show request statistics"""
        logger = get_logger()
        s = logger.get_stats(days)

        typer.echo(f"Total requests: {s['total_requests']}")
        typer.echo(f"Errors: {s['error_count']}")
        typer.echo(f"Error rate: {s['error_rate']:.1%}")
        typer.echo(f"Avg duration: {s['avg_duration_ms']:.2f}ms")

    app()


if __name__ == "__main__":
    main()
