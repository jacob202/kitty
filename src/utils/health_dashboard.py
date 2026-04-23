#!/usr/bin/env python3
"""
Health Monitoring Dashboard for Kitty
Rich terminal dashboard showing system health
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import psutil
import requests


class HealthMonitor:
    """Monitor system health"""

    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.chromadb_path = Path("data/chromadb")

    def check_ollama(self) -> dict:
        """Check Ollama status"""
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if r.status_code == 200:
                models = r.json().get("models", [])
                return {
                    "status": "ok",
                    "models": len(models),
                    "model_names": [m["name"] for m in models[:5]],
                }
            return {"status": "error", "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"status": "offline", "error": str(e)[:50]}

    def check_chromadb(self) -> dict:
        """Check ChromaDB status"""
        try:
            # Check if data directory exists and has files
            if self.chromadb_path.exists():
                files = list(self.chromadb_path.rglob("*"))
                return {
                    "status": "ok",
                    "files": len(files),
                    "size_mb": sum(f.stat().st_size for f in files if f.is_file()) / (1024 * 1024),
                }
            return {"status": "empty", "files": 0}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def check_memory(self) -> dict:
        """Check system memory"""
        try:
            mem = psutil.virtual_memory()
            return {
                "total_gb": mem.total / (1024**3),
                "used_gb": mem.used / (1024**3),
                "percent": mem.percent,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def check_disk(self) -> dict:
        """Check disk usage"""
        try:
            disk = psutil.disk_usage("/")
            return {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_gb": disk.free / (1024**3),
                "percent": disk.percent,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def check_cpu(self) -> dict:
        """Check CPU usage"""
        try:
            return {
                "percent": psutil.cpu_percent(interval=0.1),
                "count": psutil.cpu_count(),
                "count_logical": psutil.cpu_count(logical=True),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def check_jobs(self) -> dict:
        """Check job queue status"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from src.orchestrator.job_queue import list_jobs

            jobs = list_jobs(limit=100)
            return {
                "status": "ok",
                "pending": sum(1 for j in jobs if j.get("status") == "pending"),
                "running": sum(1 for j in jobs if j.get("status") == "running"),
                "completed": sum(1 for j in jobs if j.get("status") == "completed"),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_all(self) -> dict:
        """Get all health data"""
        return {
            "timestamp": datetime.now().isoformat(),
            "ollama": self.check_ollama(),
            "chromadb": self.check_chromadb(),
            "memory": self.check_memory(),
            "disk": self.check_disk(),
            "cpu": self.check_cpu(),
            "jobs": self.check_jobs(),
        }


def format_health_dashboard() -> str:
    """Format health dashboard with rich"""
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console()
        monitor = HealthMonitor()
        health = monitor.get_all()

        # Title
        console.print("\n[bold cyan]🐱 KITTY HEALTH DASHBOARD[/bold cyan]")
        console.print(f"[dim]{health['timestamp']}[/dim]\n")

        # System table
        system_table = Table(title="System Resources", box=box.ROUNDED)
        system_table.add_column("Resource", style="cyan")
        system_table.add_column("Status", style="green")
        system_table.add_column("Details")

        # Memory
        mem = health.get("memory", {})
        if "error" not in mem:
            system_table.add_row(
                "Memory",
                "✓",
                f"{mem.get('used_gb', 0):.1f}GB / {mem.get('total_gb', 0):.1f}GB ({mem.get('percent', 0):.0f}%)",
            )

        # CPU
        cpu = health.get("cpu", {})
        if "error" not in cpu:
            system_table.add_row(
                "CPU", "✓", f"{cpu.get('percent', 0):.0f}% ({cpu.get('count', 0)} cores)"
            )

        # Disk
        disk = health.get("disk", {})
        if "error" not in disk:
            system_table.add_row(
                "Disk",
                "✓",
                f"{disk.get('used_gb', 0):.1f}GB / {disk.get('total_gb', 0):.1f}GB ({disk.get('percent', 0):.0f}%)",
            )

        console.print(system_table)

        # Services table
        services_table = Table(title="Services", box=box.ROUNDED)
        services_table.add_column("Service", style="cyan")
        services_table.add_column("Status", style="green")
        services_table.add_column("Details")

        # Ollama
        ollama = health.get("ollama", {})
        status = "✓" if ollama.get("status") == "ok" else "✗"
        details = ollama.get("error", f"{ollama.get('models', 0)} models")
        services_table.add_row("Ollama", status, details)

        # ChromaDB
        chroma = health.get("chromadb", {})
        status = "✓" if chroma.get("status") in ("ok", "empty") else "✗"
        details = f"{chroma.get('files', 0)} files"
        services_table.add_row("ChromaDB", status, details)

        # Jobs
        jobs = health.get("jobs", {})
        if "error" not in jobs:
            pending = jobs.get("pending", 0)
            running = jobs.get("running", 0)
            completed = jobs.get("completed", 0)
            services_table.add_row(
                "Job Queue", "✓", f"Pending: {pending}, Running: {running}, Done: {completed}"
            )

        console.print(services_table)

    except ImportError:
        # Fallback to simple print
        monitor = HealthMonitor()
        health = monitor.get_all()
        print("\n🐱 KITTY HEALTH DASHBOARD")
        print(f"Timestamp: {health['timestamp']}")

        print("\nSystem:")
        mem = health.get("memory", {})
        print(
            f"  Memory: {mem.get('used_gb', 0):.1f}/{mem.get('total_gb', 0):.1f}GB ({mem.get('percent', 0):.0f}%)"
        )

        cpu = health.get("cpu", {})
        print(f"  CPU: {cpu.get('percent', 0):.0f}%")

        print("\nServices:")
        ollama = health.get("ollama", {})
        print(f"  Ollama: {ollama.get('status', 'unknown')}")

        chroma = health.get("chromadb", {})
        print(f"  ChromaDB: {chroma.get('status', 'unknown')}")


# CLI
def main():
    """Health dashboard CLI"""
    import typer

    app = typer.Typer(help="Health Monitoring")

    @app.command("dashboard")
    def dashboard():
        """Show health dashboard"""
        format_health_dashboard()

    @app.command("check")
    def check():
        """Check all services"""
        monitor = HealthMonitor()
        health = monitor.get_all()

        typer.echo("Ollama:", health.get("ollama", {}).get("status", "unknown"))
        typer.echo("ChromaDB:", health.get("chromadb", {}).get("status", "unknown"))
        typer.echo("Memory:", health.get("memory", {}).get("percent", 0), "%")
        typer.echo("CPU:", health.get("cpu", {}).get("percent", 0), "%")

    @app.command("watch")
    def watch(seconds: int = typer.Option(5, "--seconds", "-s", help="Watch interval")):
        """Watch health in real-time"""
        import os

        try:
            while True:
                os.system("clear" if os.name == "posix" else "cls")
                format_health_dashboard()
                time.sleep(seconds)
        except KeyboardInterrupt:
            typer.echo("\nStopped")

    app()


if __name__ == "__main__":
    main()
