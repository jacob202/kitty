"""
Health Checker — Enterprise-grade health monitoring for Kitty AI.
Verifies all critical services and system resources.
"""

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
import requests

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
API_TIMEOUT = 5


@dataclass
class HealthCheck:
    """Result of a single health check."""

    name: str
    status: str  # "ok", "warning", "error"
    message: str
    details: dict[str, Any]
    timestamp: str
    response_time_ms: float


@dataclass
class SystemStatus:
    """Complete system status report."""

    timestamp: str
    overall_status: str  # "healthy", "degraded", "critical"
    version: str
    checks: list[HealthCheck]
    summary: dict[str, int]  # counts by status


class HealthChecker:
    """
    Enterprise health checker for Kitty AI deployment.
    Monitors Ollama, databases, API keys, disk, memory, and services.
    """

    def __init__(self):
        self.checks: list[HealthCheck] = []
        self.version = "0.1.0"
        self._db_client = None

    def _get_db_client(self):
        """Lazy load DuckDB client."""
        if self._db_client is None:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from src.utils.duckdb_client import DuckDBClient

            self._db_client = DuckDBClient()
        return self._db_client

    def check_ollama(self) -> HealthCheck:
        """Verify Ollama running on localhost:11434."""
        start_time = time.time()
        try:
            response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=API_TIMEOUT)
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return HealthCheck(
                    name="ollama",
                    status="ok",
                    message=f"Running with {len(models)} models",
                    details={
                        "url": OLLAMA_URL,
                        "model_count": len(models),
                        "models": [m.get("name", "unknown") for m in models[:5]],
                    },
                    timestamp=datetime.now().isoformat(),
                    response_time_ms=round(response_time, 2),
                )
            else:
                return HealthCheck(
                    name="ollama",
                    status="error",
                    message=f"HTTP {response.status_code}",
                    details={"url": OLLAMA_URL, "status_code": response.status_code},
                    timestamp=datetime.now().isoformat(),
                    response_time_ms=round(response_time, 2),
                )
        except requests.exceptions.ConnectionError as e:
            return HealthCheck(
                name="ollama",
                status="error",
                message=f"Connection refused: {e}",
                details={"url": OLLAMA_URL, "error_type": "connection_refused"},
                timestamp=datetime.now().isoformat(),
                response_time_ms=round((time.time() - start_time) * 1000, 2),
            )
        except requests.exceptions.Timeout:
            return HealthCheck(
                name="ollama",
                status="warning",
                message="Connection timeout",
                details={"url": OLLAMA_URL, "timeout_seconds": API_TIMEOUT},
                timestamp=datetime.now().isoformat(),
                response_time_ms=round((time.time() - start_time) * 1000, 2),
            )
        except Exception as e:
            return HealthCheck(
                name="ollama",
                status="error",
                message=str(e),
                details={"url": OLLAMA_URL, "error": str(e)},
                timestamp=datetime.now().isoformat(),
                response_time_ms=round((time.time() - start_time) * 1000, 2),
            )

    def check_database(self) -> HealthCheck:
        """Verify DuckDB accessible and tables exist."""
        start_time = time.time()
        try:
            db = self._get_db_client()

            # Check connection by executing a simple query
            db.execute("SELECT 1").fetchone()

            # Get table information
            tables_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
            """
            tables_result = db.execute(tables_query).fetchall()
            tables = [row[0] for row in tables_result]

            # Check critical tables exist
            critical_tables = [
                "bom_components",
                "hardware_entities",
                "datasheet_specs",
                "component_datasheets",
                "cross_references",
            ]
            missing_tables = [t for t in critical_tables if t not in tables]

            response_time = (time.time() - start_time) * 1000

            if missing_tables:
                return HealthCheck(
                    name="database",
                    status="warning",
                    message=f"Missing tables: {', '.join(missing_tables)}",
                    details={
                        "db_path": db.db_path,
                        "tables_found": len(tables),
                        "tables": tables,
                        "missing_tables": missing_tables,
                    },
                    timestamp=datetime.now().isoformat(),
                    response_time_ms=round(response_time, 2),
                )

            return HealthCheck(
                name="database",
                status="ok",
                message=f"Connected, {len(tables)} tables",
                details={
                    "db_path": db.db_path,
                    "table_count": len(tables),
                    "tables": tables[:10],  # Limit output
                },
                timestamp=datetime.now().isoformat(),
                response_time_ms=round(response_time, 2),
            )
        except Exception as e:
            return HealthCheck(
                name="database",
                status="error",
                message=str(e),
                details={"error": str(e), "error_type": type(e).__name__},
                timestamp=datetime.now().isoformat(),
                response_time_ms=round((time.time() - start_time) * 1000, 2),
            )

    def check_api_keys(self) -> HealthCheck:
        """Verify OpenAI, Anthropic, Gemini keys are configured."""
        start_time = time.time()

        api_keys = {
            "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY")),
            "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
            "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
            "GROQ_API_KEY": bool(os.getenv("GROQ_API_KEY")),
            "DEEPSEEK_API_KEY": bool(os.getenv("DEEPSEEK_API_KEY")),
        }

        configured_count = sum(api_keys.values())
        total_count = len(api_keys)

        # Don't expose actual keys, just show presence
        key_status = {k: "configured" if v else "missing" for k, v in api_keys.items()}

        response_time = (time.time() - start_time) * 1000

        if configured_count == 0:
            return HealthCheck(
                name="api_keys",
                status="warning",
                message="No API keys configured",
                details={
                    "keys": key_status,
                    "configured": configured_count,
                    "total": total_count,
                },
                timestamp=datetime.now().isoformat(),
                response_time_ms=round(response_time, 2),
            )
        elif configured_count < 2:
            return HealthCheck(
                name="api_keys",
                status="warning",
                message=f"Only {configured_count} API key configured",
                details={
                    "keys": key_status,
                    "configured": configured_count,
                    "total": total_count,
                },
                timestamp=datetime.now().isoformat(),
                response_time_ms=round(response_time, 2),
            )

        return HealthCheck(
            name="api_keys",
            status="ok",
            message=f"{configured_count}/{total_count} API keys configured",
            details={
                "keys": key_status,
                "configured": configured_count,
                "total": total_count,
            },
            timestamp=datetime.now().isoformat(),
            response_time_ms=round(response_time, 2),
        )

    def check_disk_space(self) -> HealthCheck:
        """Alert if < 10% free disk space."""
        start_time = time.time()
        try:
            disk = psutil.disk_usage("/")
            total_gb = disk.total / (1024**3)
            free_gb = disk.free / (1024**3)
            used_percent = disk.percent
            free_percent = 100 - used_percent

            response_time = (time.time() - start_time) * 1000

            if free_percent < 5:
                status = "error"
                message = f"Critical: {free_percent:.1f}% free ({free_gb:.1f}GB)"
            elif free_percent < 10:
                status = "warning"
                message = f"Low: {free_percent:.1f}% free ({free_gb:.1f}GB)"
            else:
                status = "ok"
                message = f"{free_percent:.1f}% free ({free_gb:.1f}GB / {total_gb:.1f}GB)"

            return HealthCheck(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "total_gb": round(total_gb, 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(free_gb, 2),
                    "used_percent": used_percent,
                    "free_percent": free_percent,
                },
                timestamp=datetime.now().isoformat(),
                response_time_ms=round(response_time, 2),
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status="error",
                message=str(e),
                details={"error": str(e)},
                timestamp=datetime.now().isoformat(),
                response_time_ms=round((time.time() - start_time) * 1000, 2),
            )

    def check_memory(self) -> HealthCheck:
        """Alert if RAM > 90% usage."""
        start_time = time.time()
        try:
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024**3)
            used_gb = mem.used / (1024**3)
            available_gb = mem.available / (1024**3)

            response_time = (time.time() - start_time) * 1000

            if mem.percent > 95:
                status = "error"
                message = f"Critical: {mem.percent}% used"
            elif mem.percent > 90:
                status = "warning"
                message = f"High: {mem.percent}% used"
            elif mem.percent > 80:
                status = "warning"
                message = f"Elevated: {mem.percent}% used"
            else:
                status = "ok"
                message = f"{mem.percent}% used"

            return HealthCheck(
                name="memory",
                status=status,
                message=message,
                details={
                    "total_gb": round(total_gb, 2),
                    "used_gb": round(used_gb, 2),
                    "available_gb": round(available_gb, 2),
                    "percent": mem.percent,
                    "available_percent": 100 - mem.percent,
                },
                timestamp=datetime.now().isoformat(),
                response_time_ms=round(response_time, 2),
            )
        except Exception as e:
            return HealthCheck(
                name="memory",
                status="error",
                message=str(e),
                details={"error": str(e)},
                timestamp=datetime.now().isoformat(),
                response_time_ms=round((time.time() - start_time) * 1000, 2),
            )

    def check_services(self) -> HealthCheck:
        """Check all microservices responding."""
        start_time = time.time()

        services = {
            "kitty_web": {"url": "http://localhost:5000/api/health", "timeout": 3},
            "kitty_socketio": {"url": "http://localhost:5000", "timeout": 3},
        }

        service_status = {}
        any_error = False
        any_warning = False

        for name, config in services.items():
            try:
                response = requests.get(config["url"], timeout=config["timeout"])
                if response.status_code == 200:
                    service_status[name] = "ok"
                else:
                    service_status[name] = f"http_{response.status_code}"
                    any_warning = True
            except requests.exceptions.ConnectionError:
                service_status[name] = "offline"
                any_error = True
            except requests.exceptions.Timeout:
                service_status[name] = "timeout"
                any_warning = True
            except Exception as e:
                service_status[name] = f"error: {str(e)[:30]}"
                any_error = True

        response_time = (time.time() - start_time) * 1000

        if any_error:
            status = "warning"
            message = "Some services offline"
        elif any_warning:
            status = "warning"
            message = "Some services degraded"
        else:
            status = "ok"
            message = f"All {len(services)} services responding"

        return HealthCheck(
            name="services",
            status=status,
            message=message,
            details={
                "services": service_status,
                "count": len(services),
                "responding": sum(1 for s in service_status.values() if s == "ok"),
            },
            timestamp=datetime.now().isoformat(),
            response_time_ms=round(response_time, 2),
        )

    def check_cpu(self) -> HealthCheck:
        """Check CPU usage."""
        start_time = time.time()
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            load_avg = os.getloadavg() if hasattr(os, "getloadavg") else None

            response_time = (time.time() - start_time) * 1000

            if cpu_percent > 95:
                status = "error"
                message = f"Critical: {cpu_percent}%"
            elif cpu_percent > 85:
                status = "warning"
                message = f"High: {cpu_percent}%"
            else:
                status = "ok"
                message = f"{cpu_percent}%"

            return HealthCheck(
                name="cpu",
                status=status,
                message=message,
                details={
                    "percent": cpu_percent,
                    "cores": cpu_count,
                    "load_avg": load_avg,
                },
                timestamp=datetime.now().isoformat(),
                response_time_ms=round(response_time, 2),
            )
        except Exception as e:
            return HealthCheck(
                name="cpu",
                status="error",
                message=str(e),
                details={"error": str(e)},
                timestamp=datetime.now().isoformat(),
                response_time_ms=round((time.time() - start_time) * 1000, 2),
            )

    def check_chromadb(self) -> HealthCheck:
        """Check ChromaDB status."""
        start_time = time.time()
        try:
            chroma_path = Path("data/vector_store/chroma_db")

            if not chroma_path.exists():
                return HealthCheck(
                    name="chromadb",
                    status="warning",
                    message="Directory not found",
                    details={"path": str(chroma_path)},
                    timestamp=datetime.now().isoformat(),
                    response_time_ms=round((time.time() - start_time) * 1000, 2),
                )

            files = list(chroma_path.rglob("*"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())

            response_time = (time.time() - start_time) * 1000

            return HealthCheck(
                name="chromadb",
                status="ok",
                message=f"{len(files)} files",
                details={
                    "path": str(chroma_path),
                    "file_count": len(files),
                    "size_mb": round(total_size / (1024 * 1024), 2),
                },
                timestamp=datetime.now().isoformat(),
                response_time_ms=round(response_time, 2),
            )
        except Exception as e:
            return HealthCheck(
                name="chromadb",
                status="error",
                message=str(e),
                details={"error": str(e)},
                timestamp=datetime.now().isoformat(),
                response_time_ms=round((time.time() - start_time) * 1000, 2),
            )

    def run_all_checks(self) -> SystemStatus:
        """Run all health checks and return comprehensive status."""
        self.checks = []

        check_methods = [
            self.check_ollama,
            self.check_database,
            self.check_api_keys,
            self.check_disk_space,
            self.check_memory,
            self.check_cpu,
            self.check_services,
            self.check_chromadb,
        ]

        for check_method in check_methods:
            try:
                result = check_method()
                self.checks.append(result)
            except Exception as e:
                logger.error(f"Health check {check_method.__name__} failed: {e}")
                self.checks.append(
                    HealthCheck(
                        name=check_method.__name__.replace("check_", ""),
                        status="error",
                        message=f"Check failed: {e}",
                        details={"error": str(e)},
                        timestamp=datetime.now().isoformat(),
                        response_time_ms=0.0,
                    )
                )

        # Calculate overall status
        error_count = sum(1 for c in self.checks if c.status == "error")
        warning_count = sum(1 for c in self.checks if c.status == "warning")

        if error_count > 0:
            overall_status = "critical"
        elif warning_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        summary = {
            "ok": sum(1 for c in self.checks if c.status == "ok"),
            "warning": warning_count,
            "error": error_count,
            "total": len(self.checks),
        }

        return SystemStatus(
            timestamp=datetime.now().isoformat(),
            overall_status=overall_status,
            version=self.version,
            checks=self.checks,
            summary=summary,
        )

    def get_system_status(self) -> dict[str, Any]:
        """Get dashboard metrics for system status."""
        status = self.run_all_checks()

        # Calculate additional metrics
        total_response_time = sum(c.response_time_ms for c in status.checks)
        avg_response_time = total_response_time / len(status.checks) if status.checks else 0

        # Get uptime if available
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            uptime_hours = uptime_seconds / 3600
        except Exception:
            uptime_hours = None

        return {
            "timestamp": status.timestamp,
            "status": status.overall_status,
            "version": status.version,
            "summary": status.summary,
            "metrics": {
                "avg_response_time_ms": round(avg_response_time, 2),
                "total_response_time_ms": round(total_response_time, 2),
                "uptime_hours": round(uptime_hours, 2) if uptime_hours else None,
            },
            "checks": [asdict(check) for check in status.checks],
        }

    def to_json(self) -> str:
        """Export health status as JSON string."""
        status = self.run_all_checks()
        return json.dumps(
            {
                "timestamp": status.timestamp,
                "status": status.overall_status,
                "version": status.version,
                "summary": status.summary,
                "checks": [asdict(check) for check in status.checks],
            },
            indent=2,
        )


def health_check() -> dict[str, str]:
    """Legacy compatibility function."""
    checker = HealthChecker()
    status = checker.run_all_checks()
    return {check.name: check.status for check in status.checks}


# CLI for testing
if __name__ == "__main__":
    import typer
    from rich import box
    from rich.console import Console
    from rich.table import Table

    app = typer.Typer(help="Health Checker CLI")
    console = Console()

    @app.command()
    def check():
        """Run all health checks."""
        checker = HealthChecker()
        status = checker.run_all_checks()

        console.print("\n[bold cyan]Kitty AI Health Check[/bold cyan]")
        console.print(
            f"Status: [{_status_color(status.overall_status)}]{status.overall_status}[/{_status_color(status.overall_status)}]"
        )
        console.print(f"Time: {status.timestamp}\n")

        table = Table(box=box.ROUNDED)
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Message")
        table.add_column("Response", justify="right")

        for check in status.checks:
            color = _status_color(check.status)
            table.add_row(
                check.name,
                f"[{color}]{check.status}[/{color}]",
                check.message,
                f"{check.response_time_ms}ms",
            )

        console.print(table)

        # Summary
        console.print(f"\n[dim]Total: {status.summary['total']} | ", end="")
        console.print(f"[green]OK: {status.summary['ok']}[/green] | ", end="")
        console.print(f"[yellow]Warnings: {status.summary['warning']}[/yellow] | ", end="")
        console.print(f"[red]Errors: {status.summary['error']}[/red][/dim]")

    @app.command()
    def json_export():
        """Export health status as JSON."""
        checker = HealthChecker()
        print(checker.to_json())

    @app.command()
    def status():
        """Show system status dashboard."""
        checker = HealthChecker()
        dashboard = checker.get_system_status()
        print(json.dumps(dashboard, indent=2))

    def _status_color(status: str) -> str:
        return {"ok": "green", "warning": "yellow", "error": "red"}.get(status, "white")

    app()
