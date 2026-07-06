"""Knowledge library endpoints — ingest, inventory, and search.

Productizes the existing ``gateway.knowledge`` and ``gateway.pdf_pipeline``
seams. No silent success: every ingest response carries an explicit
``status`` (success | skipped | failed | pending) and a ``reason`` string.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gateway.paths import KNOWLEDGE_DIR

logger = logging.getLogger("kitty.routes.knowledge")

router = APIRouter(tags=["knowledge"])

# Status set — anything else is a bug in the route, not a valid response.
ALLOWED_STATUSES = {"success", "skipped", "failed", "pending"}

# Bound URL downloads so a hostile or runaway response cannot fill the disk
# or hang the request worker. 200 MB covers all realistic PDFs and books
# without giving an attacker a free disk-fill primitive.
URL_DOWNLOAD_TIMEOUT_SECONDS = 30
URL_DOWNLOAD_MAX_BYTES = 200 * 1024 * 1024
URL_DOWNLOAD_DIR = KNOWLEDGE_DIR / "inbox"
URL_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --- Request/Response Schemas ---


class IngestRequest(BaseModel):
    """Body for POST /knowledge/ingest. Exactly one of path/url must be set."""

    path: Optional[str] = None
    url: Optional[str] = None
    source_label: Optional[str] = None
    sensitivity: str = Field(default="low", pattern=r"^(low|medium|high)$")
    doc_type: Optional[str] = None
    collection: str = Field(default="general", pattern=r"^[a-z][a-z0-9_]{0,63}$")
    tags: list[str] = Field(default_factory=list, max_length=20)
    force_refresh: bool = False

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "IngestRequest":
        if not self.path and not self.url:
            raise ValueError("either 'path' or 'url' is required")
        if self.path and self.url:
            raise ValueError("provide only one of 'path' or 'url', not both")
        return self

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, tags: list[str]) -> list[str]:
        normalized: set[str] = set()
        for tag in tags:
            value = re.sub(r"[^a-z0-9_]+", "_", tag.strip().lower()).strip("_")
            if not value:
                raise ValueError("tags must contain at least one letter or number")
            if len(value) > 64:
                raise ValueError(f"tag is longer than 64 characters: {tag!r}")
            normalized.add(value)
        return sorted(normalized)


class IngestResponse(BaseModel):
    status: str
    source_id: str
    reason: str


class ExpertRequest(BaseModel):
    """A strictly local expert retrieval request."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    expert: str = Field(default="coding_repo", pattern=r"^[a-z][a-z0-9_]{0,63}$")
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def _non_empty_query(cls, query: str) -> str:
        value = query.strip()
        if not value:
            raise ValueError("query must contain non-whitespace characters")
        return value


# --- Routes ---


@router.post("/knowledge/ingest", response_model=IngestResponse)
async def post_ingest(body: IngestRequest) -> IngestResponse:
    """Ingest a local file or a URL into the knowledge base.

    Returns an explicit status (success | skipped | failed | pending) and a
    reason. Status is never implied from HTTP code alone.
    """
    target_path, downloaded, download_reason = _resolve_target(body)

    if target_path is None:
        return IngestResponse(
            status="failed",
            source_id=body.url or body.path or "",
            reason=download_reason or "could not resolve source",
        )

    source_id = body.source_label or target_path.name

    try:
        from gateway import knowledge

        result = await knowledge.ingest(
            file_path=target_path,
            sensitivity=body.sensitivity,
            source_label=body.source_label,
            doc_type=body.doc_type,
            collection=body.collection,
            tags=body.tags,
            force_refresh=body.force_refresh,
        )
    except Exception as exc:  # noqa: BLE001 — surface real failure, not a default
        logger.exception("ingest failed for %s", source_id)
        return IngestResponse(
            status="failed",
            source_id=source_id,
            reason=f"ingest raised {type(exc).__name__}: {exc}",
        )
    finally:
        if downloaded and target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                logger.warning("could not remove temp download %s", target_path)

    status = result.status if result.status in ALLOWED_STATUSES else "failed"
    reason = result.error_message or _status_reason(result.status)
    return IngestResponse(status=status, source_id=result.source, reason=reason)


@router.get("/knowledge/sources")
async def get_sources() -> dict:
    """List every ingested source with chunk counts and metadata."""
    from gateway import archivist

    try:
        collection = archivist._get_collection()
        total = collection.count()
    except Exception as exc:  # noqa: BLE001
        logger.exception("could not read knowledge collection")
        raise HTTPException(status_code=503, detail=f"knowledge store unavailable: {exc}") from exc

    if total == 0:
        return {"sources": [], "total_sources": 0, "total_chunks": 0}

    try:
        payload = collection.get(include=["metadatas"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"could not read metadatas: {exc}") from exc

    sources = _aggregate_sources(payload.get("metadatas") or [])
    return {
        "sources": sources,
        "total_sources": len(sources),
        "total_chunks": total,
    }


@router.get("/knowledge/search")
async def get_search(q: str = "", limit: int = 5) -> dict:
    """Search the knowledge base. Returns references per chunk.

    An empty result set returns an explicit message — the client should
    never have to interpret "results: []" as success or failure.
    """
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    if not q.strip():
        return {
            "query": q,
            "results": [],
            "message": "empty query — provide a non-empty ?q= parameter",
        }

    from gateway import knowledge

    try:
        raw = await knowledge.search(q.strip(), limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.exception("knowledge search failed for q=%r", q)
        raise HTTPException(status_code=500, detail=f"search failed: {exc}") from exc

    results = [_format_chunk(c) for c in raw]

    if not results:
        return {
            "query": q,
            "results": [],
            "message": "no relevant chunks found in the knowledge base",
        }

    return {"query": q, "results": results, "count": len(results)}


@router.post("/knowledge/expert")
async def post_expert(body: ExpertRequest) -> dict:
    """Answer from uploaded sources through the loopback-only MLX model."""
    from gateway import knowledge

    try:
        return await knowledge.answer_as_expert(
            body.query,
            expert=body.expert,
            limit=body.limit,
        )
    except knowledge.UnknownExpertError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except knowledge.ExpertAnswerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# --- Helpers ---


def _resolve_target(
    body: IngestRequest,
) -> tuple[Optional[Path], bool, Optional[str]]:
    """Return (path_to_ingest, was_downloaded, failure_reason)."""
    if body.path:
        p = Path(body.path).expanduser()
        if not p.exists():
            return None, False, f"file not found: {p}"
        if not p.is_file():
            return None, False, f"not a regular file: {p}"
        return p, False, None

    assert body.url is not None  # validated by IngestRequest
    parsed = urlparse(body.url)
    if parsed.scheme not in ("http", "https"):
        return None, False, f"unsupported url scheme: {parsed.scheme!r}"

    return _download_url(body.url)


def _download_url(url: str) -> tuple[Optional[Path], bool, Optional[str]]:
    """Stream a URL into KNOWLEDGE_DIR/inbox and return the temp path."""
    try:
        with requests.get(
            url, timeout=URL_DOWNLOAD_TIMEOUT_SECONDS, stream=True, allow_redirects=True
        ) as resp:
            resp.raise_for_status()
            filename = _safe_filename(url, resp)
            target = URL_DOWNLOAD_DIR / filename
            written = 0
            with target.open("wb") as out:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > URL_DOWNLOAD_MAX_BYTES:
                        out.close()
                        target.unlink(missing_ok=True)
                        return None, False, (f"download exceeded {URL_DOWNLOAD_MAX_BYTES} bytes")
                    out.write(chunk)
        return target, True, None
    except requests.RequestException as exc:
        return None, False, f"download failed: {exc}"
    except OSError as exc:
        return None, False, f"could not write download: {exc}"


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(url: str, resp: requests.Response) -> str:
    """Pick a filesystem-safe filename for a downloaded URL."""
    parsed = urlparse(url)
    name = Path(parsed.path).name or "download"
    name = _SAFE_NAME_RE.sub("_", name).strip("._") or "download"
    ext = Path(name).suffix.lower() or _guess_ext(resp)
    stem = Path(name).stem or "download"
    return f"{int(time.time())}_{stem}{ext}"


def _guess_ext(resp: requests.Response) -> str:
    ctype = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    return {
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "application/json": ".json",
        "text/html": ".html",
    }.get(ctype, "")


def _status_reason(status: str) -> str:
    return {
        "success": "ingested and indexed",
        "skipped": "content already present (deduped by hash) or empty",
        "failed": "ingest failed",
        "pending": "queued for async ingestion",
    }.get(status, f"unknown status: {status}")


def _aggregate_sources(metadatas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group chunk metadatas by source name and summarize per source."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for m in metadatas:
        name = m.get("source", "unknown")
        grouped.setdefault(name, []).append(m)

    out: list[dict[str, Any]] = []
    for name, items in sorted(grouped.items()):
        brief = next(
            (m for m in items if m.get("doc_type") == "source_summary"),
            None,
        )
        collections = sorted({m.get("collection", "general") for m in items})
        if len(collections) != 1:
            raise RuntimeError(f"source {name!r} has inconsistent collections: {collections}")
        tags: set[str] = set()
        for metadata in items:
            raw_tags = metadata.get("tags_json", "[]")
            try:
                decoded_tags = json.loads(raw_tags)
            except (TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"source {name!r} has invalid tags_json: {raw_tags!r}") from exc
            if not isinstance(decoded_tags, list) or not all(
                isinstance(tag, str) for tag in decoded_tags
            ):
                raise RuntimeError(f"source {name!r} tags_json must encode a list of strings")
            tags.update(decoded_tags)
        ingested_at = max((m.get("ingested_at") or 0) for m in items)
        modified_at = max((m.get("modified_at") or 0) for m in items)
        created_at = max((m.get("created_at") or 0) for m in items)
        sensitivities = sorted({m.get("sensitivity", "low") for m in items})
        doc_types = sorted({m.get("doc_type", "general") for m in items})
        out.append(
            {
                "name": name,
                "chunks": len(items),
                "collection": collections[0],
                "tags": sorted(tags),
                "doc_types": doc_types,
                "sensitivities": sensitivities,
                "authority_score": (brief or {}).get("authority_score"),
                "primary_topic": (brief or {}).get("primary_topic"),
                "content_hash": (brief or {}).get("content_hash") or items[0].get("content_hash"),
                "file_path": items[0].get("file_path"),
                "ingested_at": ingested_at or None,
                "modified_at": modified_at or None,
                "created_at": created_at or None,
            }
        )
    return out


def _format_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """Project a knowledge.search() chunk into the public response shape."""
    meta = chunk.get("metadata") or {}
    return {
        "text": chunk.get("text", ""),
        "source": chunk.get("source", "unknown"),
        "doc_type": chunk.get("doc_type", meta.get("doc_type", "general")),
        "score": chunk.get("score"),
        "reference": {
            "source": chunk.get("source", "unknown"),
            "chunk_index": meta.get("chunk_index"),
            "page_num": meta.get("page_num"),
            "is_visual": bool(meta.get("is_visual", False)),
            "analysis_type": meta.get("analysis_type"),
        },
        "metadata": {
            k: v
            for k, v in meta.items()
            if k
            in {
                "sensitivity",
                "content_hash",
                "primary_topic",
                "authority_score",
                "relevance_period",
                "ingested_at",
            }
        },
    }
