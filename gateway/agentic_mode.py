"""Three-Phase Agentic Mode — PLANNING → EXECUTION → VERIFICATION.

This module implements structured mode switching for agents, similar to
Antigravity's agentic loop with distinct phases.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.agentic_mode")

KITTY_DIR = DATA_DIR


class AgenticMode:
    """Three-phase agentic mode: PLANNING → EXECUTION → VERIFICATION."""

    MODES = ("PLANNING", "EXECUTION", "VERIFICATION")

    def __init__(self, goal: str):
        self.goal = goal
        self.current_mode = "PLANNING"
        self.artifacts: Dict[str, dict] = {}
        self.state_file = KITTY_DIR / f"agentic_state_{hashlib.md5(goal.encode()).hexdigest()[:8]}.json"
        self._load()

    def _load(self):
        """Load state from disk if exists."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                self.current_mode = data.get("mode", "PLANNING")
                self.artifacts = data.get("artifacts", {})
                logger.info(f"Loaded agentic mode state: {self.current_mode}")

    def save(self):
        """Save current state to disk."""
        with open(self.state_file, "w") as f:
            json.dump({
                "mode": self.current_mode,
                "artifacts": self.artifacts,
                "goal": self.goal,
            }, f, indent=2)

    def transition(self, new_mode: str):
        """Transition to a new mode."""
        if new_mode not in self.MODES:
            raise ValueError(f"Invalid mode: {new_mode}. Valid: {self.MODES}")
        
        old = self.current_mode
        self.current_mode = new_mode
        self.save()
        logger.info(f"Mode transition: {old} → {new_mode}")

    def add_artifact(self, name: str, artifact_type: str, content: str) -> str:
        """Register an artifact produced during a phase."""
        art_dir = KITTY_DIR / "artifacts"
        art_dir.mkdir(exist_ok=True)
        
        filename = f"{artifact_type}_{name.replace(' ', '_')}.md"
        filepath = art_dir / filename
        filepath.write_text(content)
        
        self.artifacts[name] = {
            "type": artifact_type,
            "path": str(filepath),
            "mode": self.current_mode,
            "created_at": datetime.now().isoformat(),
        }
        self.save()
        logger.info(f"Artifact created: {name} ({artifact_type})")
        return str(filepath)

    def get_mode_prompt(self) -> str:
        """Get the mode-specific system prompt addition."""
        prompts = {
            "PLANNING": """You are in PLANNING mode. Your job:
- Research and design the solution
- Produce implementation_plan.md as your primary artifact
- Do NOT write any production code yet
- Ask for user approval before transitioning to EXECUTION""",
            
            "EXECUTION": """You are in EXECUTION mode. Your job:
- Write production code according to the implementation plan
- Use tools to create and modify files
- Do NOT redesign — follow the plan
- Produce walkthrough.md showing what you changed""",
            
            "VERIFICATION": """You are in VERIFICATION mode. Your job:
- Test all changes thoroughly
- Use the browser to verify visual output
- Produce a verification_report.md
- If bugs found, transition back to EXECUTION""",
        }
        return prompts.get(self.current_mode, "")

    def get_artifact(self, name: str) -> Optional[dict]:
        """Get artifact details by name."""
        return self.artifacts.get(name)

    def list_artifacts(self) -> list:
        """List all artifacts produced in this session."""
        return list(self.artifacts.values())


# Helper to create mode from goal
def create_mode(goal: str) -> AgenticMode:
    """Create a new AgenticMode instance for a goal."""
    return AgenticMode(goal)
