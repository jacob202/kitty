"""Knowledge pipeline contracts — shared Pydantic shapes for ingestion and retrieval."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class LibrarianReport(BaseModel):
    """Quality judgment for a document source."""
    summary: str = ""
    authority_score: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance_period: str = "persistent"  # persistent, seasonal, ephemeral
    primary_topic: str = ""
    needs_vision: bool = False
    pollution_warning: Optional[str] = None


class KnowledgeMetadata(BaseModel):
    """Metadata for a single knowledge chunk."""
    source: str
    file_path: str
    sensitivity: str = "low"
    doc_type: str = "general"
    content_hash: str = ""
    modified_at: int = 0
    created_at: int = 0
    ingested_at: int = 0
    authority_score: float = 0.5
    relevance_period: str = "persistent"
    primary_topic: str = ""
    chunk_index: int = 0
    is_visual: bool = False
    page_num: Optional[int] = None
    analysis_type: Optional[str] = None
    pollution_warning: Optional[str] = None

    def to_chroma(self) -> dict:
        """Export as flat dict for ChromaDB metadata storage, filtering out None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class IngestionResult(BaseModel):
    """Result of ingesting a single document."""
    source: str
    status: str  # success, skipped, failed
    content_hash: str = ""
    chunks_count: int = 0
    error_message: Optional[str] = None


class VisualExtraction(BaseModel):
    """Visual analysis result from a document page."""
    text: str = ""
    page_num: int = 0
    analysis_type: str = "general"
