#!/usr/bin/env python3
"""
Long-term Memory Pattern for Kitty
Learns from past sessions and improves over time
"""

import json
from datetime import datetime
from pathlib import Path


class LongTermMemory:
    """Persistent memory that learns from sessions"""

    def __init__(self, memory_dir: str = "data/longterm"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_file = self.memory_dir / "patterns.json"
        self.learnings_file = self.memory_dir / "learnings.json"
        self.patterns = self._load_patterns()
        self.learnings = self._load_learnings()

    def _load_patterns(self) -> dict:
        """Load learned patterns"""
        if self.patterns_file.exists():
            with open(self.patterns_file) as f:
                return json.load(f)
        return {"success_patterns": [], "failure_patterns": []}

    def _load_learnings(self) -> dict:
        """Load past learnings"""
        if self.learnings_file.exists():
            with open(self.learnings_file) as f:
                return json.load(f)
        return {"sessions": [], "improvements": []}

    def _save_patterns(self):
        """Save patterns"""
        with open(self.patterns_file, "w") as f:
            json.dump(self.patterns, f, indent=2)

    def _save_learnings(self):
        """Save learnings"""
        with open(self.learnings_file, "w") as f:
            json.dump(self.learnings, f, indent=2)

    def record_outcome(
        self, session_id: str, task: str, success: bool, details: dict | None = None
    ):
        """Record task outcome for learning"""
        outcome = {
            "session_id": session_id,
            "task": task,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }

        if success:
            self.patterns["success_patterns"].append(outcome)
        else:
            self.patterns["failure_patterns"].append(outcome)

        # Keep only last 100 patterns
        for key in ["success_patterns", "failure_patterns"]:
            self.patterns[key] = self.patterns[key][-100:]

        self._save_patterns()

        # Also update learnings
        self.learnings["sessions"].append(outcome)
        self.learnings["sessions"] = self.learnings["sessions"][-500:]
        self._save_learnings()

    def get_successful_strategies(self, task_type: str) -> list[dict]:
        """Get strategies that worked for similar tasks"""
        strategies = []
        for p in self.patterns["success_patterns"]:
            if task_type.lower() in p.get("task", "").lower():
                strategies.append(p)
        return strategies[-10:]  # Last 10

    def get_failure_warnings(self, task_type: str) -> list[dict]:
        """Get common failure patterns"""
        failures = []
        for p in self.patterns["failure_patterns"]:
            if task_type.lower() in p.get("task", "").lower():
                failures.append(p)
        return failures[-10:]

    def get_improvement_suggestions(self, task: str) -> list[str]:
        """Suggest improvements based on past"""
        suggestions = []

        # Check for similar successful tasks
        success_strategies = self.get_successful_strategies(task)
        if success_strategies:
            suggestions.append(f"Similar task succeeded {len(success_strategies)} times before")

        # Check for failure warnings
        failures = self.get_failure_warnings(task)
        if failures:
            suggestions.append(f"Similar task failed {len(failures)} times - be careful")

        return suggestions

    def generate_summary(self) -> dict:
        """Generate memory summary"""
        return {
            "total_successes": len(self.patterns["success_patterns"]),
            "total_failures": len(self.patterns["failure_patterns"]),
            "success_rate": (
                len(self.patterns["success_patterns"])
                / max(
                    1,
                    len(self.patterns["success_patterns"]) + len(self.patterns["failure_patterns"]),
                )
            ),
            "last_updated": datetime.now().isoformat(),
        }


# Global instance
_longterm_memory = None


def get_longterm_memory() -> LongTermMemory:
    """Get global long-term memory"""
    global _longterm_memory
    if _longterm_memory is None:
        _longterm_memory = LongTermMemory()
    return _longterm_memory


def record_success(session_id: str, task: str, details: dict | None = None):
    """Record a successful task"""
    memory = get_longterm_memory()
    memory.record_outcome(session_id, task, True, details)


def record_failure(session_id: str, task: str, details: dict | None = None):
    """Record a failed task"""
    memory = get_longterm_memory()
    memory.record_outcome(session_id, task, False, details)


def get_suggestions(task: str) -> list[str]:
    """Get improvement suggestions"""
    memory = get_longterm_memory()
    return memory.get_improvement_suggestions(task)


# CLI for long-term memory
def main():
    """Long-term memory CLI"""
    import typer

    app = typer.Typer(help="Long-term Memory")

    @app.command("summary")
    def show_summary():
        """Show memory summary"""
        memory = get_longterm_memory()
        summary = memory.generate_summary()

        typer.echo(f"Successes: {summary['total_successes']}")
        typer.echo(f"Failures: {summary['total_failures']}")
        typer.echo(f"Success rate: {summary['success_rate']:.1%}")

    @app.command("suggest")
    def suggest(
        task: str = typer.Argument(..., help="Task description"),
    ):
        """Get suggestions for a task"""
        memory = get_longterm_memory()
        suggestions = memory.get_improvement_suggestions(task)

        if suggestions:
            for s in suggestions:
                typer.echo(f"  - {s}")
        else:
            typer.echo("No suggestions available")

    @app.command("successes")
    def show_successes(
        task_type: str = typer.Argument("", help="Filter by task type"),
    ):
        """Show successful strategies"""
        memory = get_longterm_memory()

        if task_type:
            strategies = memory.get_successful_strategies(task_type)
        else:
            strategies = memory.patterns["success_patterns"][-10:]

        for s in strategies:
            typer.echo(f"  - {s.get('task', 'N/A')}")

    app()


if __name__ == "__main__":
    main()
