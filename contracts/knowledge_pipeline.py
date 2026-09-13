"""Knowledge pipeline contracts — shared Pydantic shapes for ingestion and retrieval."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field


class LibrarianReport(BaseModel):
    """Quality judgment for a document source."""

    summary: str = ""
    authority_score: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance_period: str = "persistent"  # persistent, seasonal, ephemeral
    primary_topic: str = ""
    needs_vision: bool = False
    pollution_warning: Optional[str] = None


class EvidenceMetadata(BaseModel):
    """Provenance and safety metadata that must survive evidence retrieval."""

    source_id: str
    source_sha256: str = ""
    logical_unit_id: str
    work_id: Optional[str] = None
    series_id: Optional[str] = None
    series_order: Optional[int] = None
    retrieval_title: str = ""
    publication_year: Optional[int] = None
    edition: str = ""
    metadata_basis: str = ""
    domains: list[str] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)
    expert_profiles: list[str] = Field(default_factory=list)
    authority_tier: str = ""
    authority_status: str = ""
    currency_sensitivity: str = ""
    currency_status: str = ""
    evidence_role: str = ""
    clinical_use_policy: str = ""
    work_relation: str = ""

    def to_chroma(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        for key in ("domains", "subjects", "expert_profiles"):
            data[f"{key}_json"] = json.dumps(data.pop(key), separators=(",", ":"))
        return {key: value for key, value in data.items() if value != ""}

    @classmethod
    def from_chroma(cls, metadata: dict[str, Any]) -> "EvidenceMetadata":
        data: dict[str, Any] = {}
        for field in cls.model_fields:
            if field in {"domains", "subjects", "expert_profiles"}:
                raw = metadata.get(f"{field}_json", "[]")
                try:
                    data[field] = json.loads(raw) if isinstance(raw, str) else list(raw or [])
                except (TypeError, json.JSONDecodeError):
                    data[field] = []
            elif field in metadata:
                data[field] = metadata[field]
        return cls.model_validate(data)


class KnowledgeMetadata(BaseModel):
    """Metadata for a single knowledge chunk."""

    source: str
    file_path: str
    collection: str = "general"
    tags_json: str = "[]"
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
