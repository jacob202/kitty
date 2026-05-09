"""Schema for every model routing decision Kitty makes."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class ModelTier(str, Enum):
    DEFAULT = "default"   # DeepSeek Flash — cheap, fast
    AGENT = "agent"       # Hermes 4 — structured output, tool calls
    SMART = "smart"       # Claude Sonnet — complex reasoning
    PRIVATE = "private"   # MLX local — sensitive data, never leaves Mac


class RoutingDecision(BaseModel):
    correlation_id: str = Field(description="Unique ID tying together one full request/response cycle")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    domain: str = Field(description="Classified domain: soul|repair|health|research|code")
    sensitivity: str = Field(description="low|medium|high|medical|financial")
    model_tier: ModelTier
    model_name: str = Field(description="Exact model string sent to LiteLLM")
    reasoning: str = Field(description="One sentence: why this model was chosen")
    estimated_cost_usd: float = Field(default=0.0)
