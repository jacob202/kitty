#!/usr/bin/env python3
"""
Swarm Orchestrator Integration
Connects Kitty to the npm swarm-orchestrator package
"""

import json
import subprocess
from typing import Any


class SwarmOrchestrator:
    """Bridge to npm swarm-orchestrator"""

    def __init__(self):
        self.package_name = "@moonrunner/swarm-orchestrator"
        self.available = self._check_available()

    def _check_available(self) -> bool:
        """Check if swarm-orchestrator is available"""
        try:
            result = subprocess.run(
                ["npm", "list", self.package_name], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_command(self, args: list[str]) -> dict:
        """Run a swarm-orchestrator command"""
        try:
            result = subprocess.run(
                ["npx", "swarm-orchestrator"] + args, capture_output=True, text=True, timeout=30
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def init_swarm(self, name: str, topology: str = "hierarchical") -> dict:
        """Initialize a new swarm"""
        return self._run_command(["init", "--name", name, "--topology", topology])

    def spawn_agent(self, agent_type: str, name: str) -> dict:
        """Spawn an agent"""
        return self._run_command(["spawn", "--type", agent_type, "--name", name])

    def execute_task(self, task: str, mode: str = "parallel") -> dict:
        """Execute a task"""
        return self._run_command(["execute", "--task", task, "--mode", mode])

    def get_status(self) -> dict:
        """Get swarm status"""
        return self._run_command(["status"])

    def list_agents(self) -> list[str]:
        """List running agents"""
        result = self._run_command(["list"])
        if result.get("success"):
            try:
                return json.loads(result.get("output", "[]"))
            except Exception:
                return result.get("output", "").strip().split("\n")
        return []


# Python-native swarm (fallback if npm not available)
class PythonSwarm:
    """Pure Python swarm implementation"""

    def __init__(self, name: str = "default"):
        self.name = name
        self.agents: dict[str, Any] = {}
        self.tasks: list[dict] = []

    def add_agent(self, name: str, role: str = "worker"):
        """Add an agent to the swarm"""
        self.agents[name] = {"name": name, "role": role, "status": "idle", "tasks_completed": 0}

    def remove_agent(self, name: str):
        """Remove an agent"""
        if name in self.agents:
            del self.agents[name]

    def add_task(self, task: str, priority: int = 5):
        """Add a task to the swarm"""
        self.tasks.append(
            {"task": task, "priority": priority, "status": "pending", "assigned_to": None}
        )
        self.tasks.sort(key=lambda x: x["priority"], reverse=True)

    def assign_task(self, agent_name: str) -> dict | None:
        """Assign next task to agent"""
        if agent_name not in self.agents:
            return None

        for task in self.tasks:
            if task["status"] == "pending":
                task["status"] = "assigned"
                task["assigned_to"] = agent_name
                self.agents[agent_name]["status"] = "busy"
                return task

        return None

    def complete_task(self, task: dict):
        """Mark task as complete"""
        for t in self.tasks:
            if t == task:
                t["status"] = "completed"
                if t.get("assigned_to"):
                    self.agents[t["assigned_to"]]["tasks_completed"] += 1
                    self.agents[t["assigned_to"]]["status"] = "idle"
                break

    def get_status(self) -> dict:
        """Get swarm status"""
        return {
            "name": self.name,
            "agents": len(self.agents),
            "idle_agents": sum(1 for a in self.agents.values() if a["status"] == "idle"),
            "pending_tasks": sum(1 for t in self.tasks if t["status"] == "pending"),
            "completed_tasks": sum(1 for t in self.tasks if t["status"] == "completed"),
        }


# Global instances
_swarm_orchestrator = None
_python_swarm = None


def get_swarm() -> PythonSwarm:
    """Get Python swarm instance"""
    global _python_swarm
    if _python_swarm is None:
        _python_swarm = PythonSwarm()
    return _python_swarm


def main():
    """Swarm CLI"""
    import typer

    app = typer.Typer(help="Swarm Orchestrator")

    @app.command("init")
    def init(
        name: str = typer.Option("default", "--name", "-n", help="Swarm name"),
    ):
        """Initialize a new swarm"""
        swarm = get_swarm()
        swarm.name = name
        typer.echo(f"Initialized swarm: {name}")

    @app.command("add")
    def add_agent(
        name: str = typer.Argument(..., help="Agent name"),
        role: str = typer.Option("worker", "--role", "-r", help="Agent role"),
    ):
        """Add an agent to the swarm"""
        swarm = get_swarm()
        swarm.add_agent(name, role)
        typer.echo(f"Added agent: {name} ({role})")

    @app.command("task")
    def add_task(
        task: str = typer.Argument(..., help="Task description"),
        priority: int = typer.Option(5, "--priority", "-p", help="Priority 1-10"),
    ):
        """Add a task to the swarm"""
        swarm = get_swarm()
        swarm.add_task(task, priority)
        typer.echo(f"Added task: {task[:50]}...")

    @app.command("status")
    def show_status():
        """Show swarm status"""
        swarm = get_swarm()
        status = swarm.get_status()

        typer.echo(f"Swarm: {status['name']}")
        typer.echo(f"  Agents: {status['agents']} (idle: {status['idle_agents']})")
        typer.echo(f"  Tasks: pending {status['pending_tasks']}, done {status['completed_tasks']}")

    @app.command("list")
    def list_agents():
        """List agents"""
        swarm = get_swarm()

        for name, agent in swarm.agents.items():
            typer.echo(f"  {name}: {agent['role']} - {agent['status']}")

    app()


if __name__ == "__main__":
    main()
