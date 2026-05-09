"""Schema for a knowledge chunk stored in ChromaDB."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class KnowledgeChunk(BaseModel):
    chunk_id: str
    text: str
    source: str = Field(description="Filename or document title")
    file_path: str
    sensitivity: str = Field(default="low", description="low|medium|high|medical|financial")
    chunk_index: int
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    allowed_models: list[str] = Field(default_factory=lambda: ["cloud_ok"])
