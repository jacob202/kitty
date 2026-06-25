"""Team Protocol — Claim, discover, challenge protocol for multi-agent coordination.

This module implements the Claude Code Agent Teams style protocol where agents
claim tasks, share discoveries, and challenge each other's findings.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.team_protocol")

KITTY_DIR = DATA_DIR


class TeamProtocol:
    """Claim, discover, challenge protocol — Claude Code Agent Teams style."""

    def __init__(self, task_list=None):
        self.task_list = task_list
        self.discoveries_file = KITTY_DIR / "team_discoveries.jsonl"
        self.challenges_dir = KITTY_DIR / "challenges"
        self.challenges_dir.mkdir(exist_ok=True)

    def claim_task(self, agent_name: str) -> Optional[str]:
        """Agent claims the next pending task."""
        if not self.task_list:
            logger.warning("No task list available for claiming")
            return None

        # Find next pending task
        pending = None
        for task in self.task_list.list_all():
            if task.get("status") == "pending":
                pending = task
                break

        if pending:
            task_id = pending.get("id")
            self.task_list.update(task_id, claimed_by=agent_name, status="claimed")
            logger.info(f"Agent '{agent_name}' claimed task: {task_id}")
            return task_id

        return None

    def share_discovery(self, agent_name: str, discovery: str, tags: List[str] = None):
        """Agent shares a finding that may help others."""
        entry = {
            "agent": agent_name,
            "discovery": discovery,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat(),
        }
        with open(self.discoveries_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(f"Discovery shared by {agent_name}: {discovery[:50]}...")

    def get_discoveries(self, agent_filter: str = None, tags: List[str] = None) -> List[dict]:
        """Get all shared discoveries, optionally filtered."""
        if not self.discoveries_file.exists():
            return []

        discoveries = []
        with open(self.discoveries_file) as f:
            for line in f:
                entry = json.loads(line.strip())
                if agent_filter and entry.get("agent") != agent_filter:
                    continue
                if tags and not any(tag in entry.get("tags", []) for tag in tags):
                    continue
                discoveries.append(entry)

        return discoveries

    def challenge(self, agent_name: str, target_agent: str, challenge_text: str, artifact_path: str = None):
        """One agent challenges another's finding — peer review protocol."""
        entry = {
            "challenger": agent_name,
            "target": target_agent,
            "challenge": challenge_text,
            "artifact": artifact_path,
            "timestamp": datetime.now().isoformat(),
            "status": "open",
        }

        challenge_file = self.challenges_dir / f"challenge_{target_agent}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        challenge_file.write_text(json.dumps(entry, indent=2))
        logger.info(f"Challenge issued: {agent_name} → {target_agent}")

    def get_challenges(self, target_agent: str) -> List[dict]:
        """Get all challenges for a specific agent."""
        challenges = []
        for challenge_file in self.challenges_dir.glob(f"challenge_{target_agent}_*.json"):
            try:
                data = json.loads(challenge_file.read_text())
                challenges.append(data)
            except Exception as e:
                logger.warning(f"Could not read challenge {challenge_file}: {e}")
        return challenges

    def resolve_challenge(self, challenge_file: Path, resolution: str, success: bool = True):
        """Resolve a challenge."""
        try:
            data = json.loads(challenge_file.read_text())
            data["resolution"] = resolution
            data["resolved"] = success
            data["resolved_at"] = datetime.now().isoformat()
            data["status"] = "resolved" if success else "rejected"
            challenge_file.write_text(json.dumps(data, indent=2))
            logger.info(f"Challenge resolved: {challenge_file.name}")
        except Exception as e:
            logger.error(f"Could not resolve challenge: {e}")

    def get_active_challenges(self) -> List[dict]:
        """Get all open challenges across all agents."""
        challenges = []
        for challenge_file in self.challenges_dir.glob("challenge_*.json"):
            try:
                data = json.loads(challenge_file.read_text())
                if data.get("status") == "open":
                    challenges.append(data)
            except Exception:
                pass
        return challenges


# Global instance - requires task_list to be injected
_team_protocol: Optional[TeamProtocol] = None

def get_team_protocol(task_list=None) -> TeamProtocol:
    """Get or create the global TeamProtocol instance."""
    global _team_protocol
    if _team_protocol is None:
        _team_protocol = TeamProtocol(task_list)
    return _team_protocol
