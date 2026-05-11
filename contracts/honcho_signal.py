from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, Dict, Any

class HonchoSignal(BaseModel):
    """A behavioral or psychological signal extracted from a conversation."""
    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_session_id: str
    signal_type: str = Field(..., description="e.g., 'avoidance', 'hyperfocus', 'overwhelm', 'recovery_win'")
    intensity: float = Field(0.0, ge=0.0, le=1.0)
    observation: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    human_confirmed: bool = False
