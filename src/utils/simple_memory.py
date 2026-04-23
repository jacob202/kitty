"""
Simple memory module for supervisor.
"""
import json
import os


class SimpleMemory:
    def __init__(self, path="./data/vector_store/memory.json"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.data = {}
        if os.path.exists(path):
            with open(path) as f:
                self.data = json.load(f)

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def remember(self, key, value):
        self.data[key] = value
        self._save()

    # ── User-defined persistent facts ──────────────────────────────────────────
    def remember_fact(self, key: str, value: str):
        self.data.setdefault("_facts", {})[key] = value
        self._save()

    def forget_fact(self, key: str):
        self.data.get("_facts", {}).pop(key, None)
        self._save()

    def get_facts(self) -> dict:
        return self.data.get("_facts", {})

    def recall_facts(self) -> str:
        facts = self.get_facts()
        return "\n".join(f"{k}: {v}" for k, v in facts.items()) if facts else ""

    def recall_all(self) -> str:
        parts = []
        facts_str = self.recall_facts()
        if facts_str:
            parts.append(f"User facts:\n{facts_str}")
        session = {k: v for k, v in self.data.items() if not k.startswith("_")}
        if session:
            recent = "\n".join(f"{k}: {str(v)[:200]}" for k, v in list(session.items())[-3:])
            parts.append(f"Recent context:\n{recent}")
        return "\n\n".join(parts)
