"""Skill Engine — auto-creates and caches reusable skills from successful interactions."""

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
SKILLS_DIR = Path("data/skills")


class SkillEngine:
    def __init__(self, skills_dir: str | None = None):
        self.skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.skills_dir / "manifest.json"
        self._manifest: dict = self._load_manifest()

    def _load_manifest(self) -> dict:
        if self._manifest_path.exists():
            return json.loads(self._manifest_path.read_text())
        return {}

    def _save_manifest(self):
        self._manifest_path.write_text(json.dumps(self._manifest, indent=2))

    def _fingerprint(self, query: str) -> str:
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

    def find_skill(self, query: str) -> dict | None:
        """Check if a matching skill exists before calling LLM."""
        fp = self._fingerprint(query)
        if fp in self._manifest:
            skill_path = self.skills_dir / f"{fp}.json"
            if skill_path.exists():
                skill = json.loads(skill_path.read_text())
                skill["success_count"] = skill.get("success_count", 0) + 1
                skill_path.write_text(json.dumps(skill, indent=2))
                return skill
        return None

    def extract_skill(self, query: str, result: str, confidence: float = 1.0) -> bool:
        """Extract a skill from a successful interaction if confidence >= 0.8."""
        if confidence < 0.8:
            return False
        fp = self._fingerprint(query)
        skill = {
            "name": fp,
            "trigger_query": query,
            "result_template": result[:500],
            "success_count": 1,
            "confidence": confidence,
        }
        path = self.skills_dir / f"{fp}.json"
        path.write_text(json.dumps(skill, indent=2))
        self._manifest[fp] = {"query": query[:80], "confidence": confidence}
        self._save_manifest()
        logger.info(f"Skill extracted: {fp}")
        return True

    def list_skills(self) -> list[dict]:
        return [{"id": k, **v} for k, v in self._manifest.items()]
