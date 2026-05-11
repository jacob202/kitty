"""Schema for memory write events."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class MemoryNamespace(str, Enum):
    FACTS = "facts"       # Jacob stated directly — confidence 1.0
    PATTERNS = "patterns" # Honcho inferred — confidence 0.5-0.8


class MemorySensitivity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MEDICAL = "medical"
    FINANCIAL = "financial"


class MemoryEvent(BaseModel):
    text: str = Field(description="The memory content to store")
    namespace: MemoryNamespace = MemoryNamespace.FACTS
    sensitivity: MemorySensitivity = MemorySensitivity.LOW
    source: str = Field(description="Where this came from: jacob_statement | honcho_inferred | document")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    human_confirmed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    allowed_models: list[str] = Field(default_factory=lambda: ["cloud_ok"])
