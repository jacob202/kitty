"""Schema for a single parsed page extracted from a PDF."""
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class PdfChunk(BaseModel):
    page_num: int = Field(description="0-indexed page number")
    text: str = Field(description="Extracted text from this page")
    image_descriptions: list[str] = Field(
        default_factory=list,
        description="Vision-generated descriptions for images on this page",
    )
    source: str = Field(description="Original PDF filename")
    parse_method: str = Field(
        default="pymupdf",
        description="llamaparse|pymupdf|pdfplumber",
    )
    has_images: bool = Field(default=False)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def combined_text(self) -> str:
        """Merge page text with image descriptions for ChromaDB ingestion."""
        parts = [self.text]
        for i, desc in enumerate(self.image_descriptions, 1):
            parts.append(f"[Image {i} description]: {desc}")
        return "\n\n".join(p for p in parts if p.strip())
