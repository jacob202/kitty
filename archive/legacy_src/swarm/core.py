from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, List

class Archetype(Enum):
    SKEPTIC = "skeptic"        # Tries to break logic, looks for hallucinations
    NOVICE = "novice"          # Distracted, poor terminology, needs hand-holding
    EXPERT = "expert"          # High-level technical questions, expects precision
    CHAOTIC = "chaotic"        # Jumps between domains, emotional, impatient
    OPTIMIZER = "optimizer"    # Focused on efficiency, shortcuts, and speed

@dataclass
class SwarmTester:
    id: str
    name: str
    archetype: Archetype
    technical_competence: float  # 0.0 to 1.0
    personality_traits: List[str]
    target_component: str       # UI, Personality, Hardware, Code, etc.
    initial_query: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SwarmTester:
        return cls(
            id=data["id"],
            name=data["name"],
            archetype=Archetype(data["archetype"]),
            technical_competence=data["technical_competence"],
            personality_traits=data["personality_traits"],
            target_component=data["target_component"],
            initial_query=data["initial_query"]
        )

def load_roster(path: Path) -> List[SwarmTester]:
    if not path.exists():
        return []
    with open(path, "r") as f:
        data = json.load(f)
    return [SwarmTester.from_dict(t) for t in data]
