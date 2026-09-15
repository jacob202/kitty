"""Robust Knowledge Pipeline — orchestrates document ingestion and retrieval.

This is a DEEP module. Callers should only use the high-leverage public interface:
- ingest(): Handle full document lifecycle (extract -> judge -> chunk -> store).
- search(): Unified vector search with context stitching.
- answer_as_expert(): Local-only, collection-scoped answers with citations.
- delete_source(): Prune document chunks.
- get_inventory(): Get source/chunk counts.

Internal pipeline stages (Clerk, Librarian, Archivist) are implementation details.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

from contracts.knowledge_pipeline import (
    EvidenceMetadata,
    EvidencePolicy,
    IngestionResult,
    KnowledgeMetadata,
    LibrarianReport,
)
from gateway import archivist, clerk, librarian
from gateway.paths import DATA_DIR, PROJECT_ROOT

logger = logging.getLogger("kitty.knowledge")

# Configuration moved from implementation details
_CHUNK_PROFILES = librarian._CHUNK_PROFILES

LOCAL_EXPERT_URL = "http://127.0.0.1:8010/v1/chat/completions"
LOCAL_EXPERT_MODEL = "default_model"
EXPERT_PROFILES: dict[str, dict[str, Any]] = {
    "coding_repo": {
        "prompt_path": PROJECT_ROOT / "soul" / "specialists" / "coder.md",
        "collections": ["coding_repo"],
    },
    "automotive": {
        "prompt_path": PROJECT_ROOT / "soul" / "specialists" / "automotive.md",
        "collections": ["automotive_manuals"],
        "proactive_policy": {
            "watch_inbox": True,
            "watch_directories": [
                "~/Library/Mobile Documents/iCloud~net~obdsoftware~obdfusion/Documents/CsvLogs"
            ],
            "learning_enabled": True,
            "poll_interval_hours": 0.5,
            "cooldown_hours": 4.0,
            "suppress_after_dismissals": 3,
        },
    },
    "health": {
        "prompt_path": PROJECT_ROOT / "soul" / "specialists" / "health.md",
        "collections": ["health_records", "supplements"],
        "proactive_policy": {
            "watch_inbox": True,
            "watch_directories": [],
            "learning_enabled": True,
            "poll_interval_hours": 12.0,
            "cooldown_hours": 24.0,
            "suppress_after_dismissals": 3,
        },
    },
    "audio": {
        "prompt_path": PROJECT_ROOT / "soul" / "specialists" / "audio.md",
        "collections": ["audio_equipment", "vintage_manuals"],
        "proactive_policy": {
            "watch_inbox": True,
            "watch_directories": [],
            "learning_enabled": True,
            "poll_interval_hours": 24.0,
            "cooldown_hours": 24.0,
            "suppress_after_dismissals": 3,
        },
    },
}


class KnowledgeSearchError(RuntimeError):
    """Raised when retrieval failed instead of legitimately finding no matches."""


class ExpertAnswerError(RuntimeError):
    """Raised when a local expert cannot produce a supported, cited answer."""


class UnknownExpertError(ExpertAnswerError):
    """Raised when a caller requests a legacy local expert profile that does not exist."""


class CorpusProjectionUnavailableError(KnowledgeSearchError):
    """Raised when a selected corpus expert cannot reach an active evidence projection."""


class UnknownCorpusExpertError(KnowledgeSearchError):
    """Raised when a selected corpus retrieval profile is not active."""


_EXPERT_LABELS = {
    "electronics_audio": "Electronics & Audio",
    "automotive": "Automotive",
    "mechanical_systems": "Mechanical Systems",
    "ai_software": "AI & Software",
    "math_physics": "Math & Physics",
    "mind_learning_communication": "Mind, Learning & Communication",
    "health_biology": "Health & Biology",
    "philosophy_humanities": "Philosophy & Humanities",
    "general_research": "General Research",
}


CORPUS_REQUIRED_PROFILES = tuple(_EXPERT_LABELS)
CORPUS_EVIDENCE_POLICY_VERSION = "evidence-policy-2026-09-15.v1"
CORPUS_RANKING_VERSION = "fts-bm25-logical-diversity-2026-09-15.v1"
CORPUS_CLINICAL_POLICY_VERSION = "clinical-current-guidance-separation-2026-09-15.v1"
CORPUS_MAX_CHUNKS_PER_LOGICAL_UNIT = 1
CORPUS_EXACT_LOOKUP_MAX_CHUNKS_PER_LOGICAL_UNIT = 2
CORPUS_PUBLICATION_BINDING: dict[str, str] = {
    "candidate_id": "6ee6664165953ad95adfbdb6eb9ef622f353630779980e5a55e135bdd1dc46a3",
    "receipt_sha256": "2a5abdffda62533bdc3add0224956152bd3d6510c05c222a385a48a8d556179d",
}

_CORPUS_ARTIFACT_FILENAMES = {
    "source_manifest": "source_manifest.jsonl",
    "collections": "collections.json",
    "ingest_requests": "ingest_requests.jsonl",
    "fts_db": "fts.sqlite",
    "profiles": "profiles.json",
    "benchmark": "benchmark.json",
    "correction_ledger": "correction_ledger.json",
}

_CURRENTNESS_WORDS = {"current", "today", "latest", "recent", "now", "2026"}


def _query_tokens(query: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", query.lower()))


def _has_phrase(text: str, *phrases: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def build_evidence_policy(query: str, expert_profile: str | None = None) -> EvidencePolicy:
    """Infer bounded evidence requirements without creating a persistent expert agent."""
    text = query.lower()
    tokens = _query_tokens(query)
    reasons: list[str] = []
    competencies: list[str] = []

    def add(name: str, reason: str) -> None:
        if name not in competencies:
            competencies.append(name)
            reasons.append(reason)

    health = expert_profile == "health_biology" or bool(tokens & {
        "medical", "clinical", "medicine", "medication", "prescription", "drug",
        "supplement", "herbal", "symptom", "treatment", "pharmacology", "health",
    })
    automotive = bool(tokens & {
        "automotive", "vehicle", "car", "truck", "honda", "ridgeline", "brake",
        "caliper", "engine", "fuel", "vin", "alternator",
    })
    electronics = bool(tokens & {
        "amplifier", "amp", "audio", "circuit", "electronics", "electronic",
        "speaker", "loudspeaker", "diode", "rectifier", "alternator", "sansui",
        "voltage", "bias", "grounding", "oscillate", "oscillation",
        "electromagnetic", "maxwell",
    }) or _has_phrase(text, "power supply", "phase shift")
    mechanical = bool(tokens & {"mechanical", "vibration", "vibrate", "chassis", "shock"})
    ai_software = bool(tokens & {"api", "python", "sdk", "software", "library", "package", "openai"}) or _has_phrase(
        text, "machine learning", "gaussian mixture", "expectation maximization"
    )
    math_physics = bool(tokens & {
        "derive", "derivation", "equation", "maxwell", "electromagnetic", "gaussian",
        "resonance", "acoustic", "acoustics", "wave",
    }) or _has_phrase(
        text, "expectation maximization", "phase shift", "wave equation", "control theory", "room modes"
    )
    mind = bool(tokens & {"learning", "classroom", "student", "students", "cognition"}) or _has_phrase(text, "retrieval practice")
    philosophy = bool(tokens & {"popper", "kuhn", "philosophy"}) or _has_phrase(text, "scientific progress")

    if health:
        add("health_biology", "health_or_clinical_language")
    if automotive:
        add("automotive", "vehicle_specific_language")
    if electronics:
        add("electronics_audio", "electronics_or_audio_language")
    if mechanical:
        add("mechanical_systems", "mechanical_or_vibration_language")
    if ai_software:
        add("ai_software", "software_or_ml_language")
    if math_physics:
        add("math_physics", "mathematical_or_physics_language")
    if mind:
        add("mind_learning_communication", "learning_or_cognition_language")
    if philosophy:
        add("philosophy_humanities", "philosophy_or_intellectual_history_language")

    current_words = bool(tokens & _CURRENTNESS_WORDS)
    legal_current = current_words and bool(tokens & {"rules", "law", "regulation", "regulations", "benefit", "policy"})
    equipment_specific = bool(tokens & {"sansui"}) or bool(re.search(r"\b[a-z]{2,}-?\d{2,}\b", text))
    vehicle_specific = automotive and (
        bool(tokens & {"honda", "ridgeline", "vin"}) or bool(re.search(r"\b(?:19|20)\d{2}\b", text))
    )

    if legal_current:
        competencies = ["general_research"]
        reasons.append("mutable_rules_or_benefit_query")

    exact_signal = bool(tokens & {"exact", "torque", "specification", "spec", "bias"})
    actionable_health_use = (
        bool(tokens & {"dose", "dosage", "dosing"})
        or ("take" in tokens and bool(tokens & {"can", "should", "with", "how", "when", "much"}))
    )
    health_safety = health and (
        bool(tokens & {"safe", "safety", "interaction", "interactions", "combine", "combined"})
        or ("prescription" in tokens and ("supplement" in tokens or "herbal" in tokens))
        or actionable_health_use
    )

    if health_safety:
        task_type = "current_safety"
    elif ai_software and current_words and "api" in tokens:
        task_type = "current_api"
    elif legal_current:
        task_type = "current_lookup"
    elif "derive" in tokens or "derivation" in tokens:
        task_type = "derivation"
    elif "compare" in tokens or "versus" in tokens or "consensus" in tokens:
        task_type = "comparison"
    elif exact_signal or (equipment_specific and bool(tokens & {"voltage", "bias", "procedure"})):
        task_type = "exact_lookup"
    elif "diagnose" in tokens or "diagnostic" in tokens or "troubleshoot" in tokens or mechanical:
        task_type = "diagnostic"
    elif bool(tokens & {"evidence", "paper", "study", "studies"}) or _has_phrase(text, "what evidence"):
        task_type = "evidence_review"
    elif "remove" in tokens or "install" in tokens or "replace" in tokens:
        task_type = "procedure"
    elif "why" in tokens or "explain" in tokens or _has_phrase(text, "how does"):
        task_type = "explanation"
    else:
        task_type = "lookup"

    exactness = "exact" if task_type in {"exact_lookup", "current_api", "current_lookup"} else "normal"
    safety = "high_health" if health else "standard"

    if health_safety:
        freshness = "current_external_required"
    elif task_type in {"current_api", "current_lookup"}:
        freshness = "current_external_required"
    elif health and task_type == "evidence_review":
        freshness = "current_external_preferred"
    else:
        freshness = "corpus_ok"

    if health:
        authority = "current_authoritative_required"
    elif task_type == "exact_lookup" and automotive:
        authority = "primary_preferred"
    elif task_type == "exact_lookup" and equipment_specific:
        authority = "service_manual_preferred"
    elif task_type in {"current_api", "current_lookup"}:
        authority = "primary_preferred"
    elif task_type == "evidence_review" and mind:
        authority = "empirical_preferred"
    elif task_type == "comparison" and philosophy:
        authority = "source_attribution_required"
    else:
        authority = "established_reference_preferred"

    applicability: list[str] = []
    if vehicle_specific:
        applicability.append("vehicle_model_specific")
    if equipment_specific and electronics:
        applicability.append("equipment_model_specific")
    if legal_current:
        applicability.append("jurisdiction_specific")

    if task_type in {"exact_lookup", "current_api", "current_lookup"}:
        diversity = "single_authoritative_ok"
    elif task_type == "comparison":
        diversity = "preserve_disagreement"
    else:
        diversity = "multiple_logical_units"

    if not competencies:
        competencies = ["general_research"]
        reasons.append("no_narrow_competency_signal")

    return EvidencePolicy(
        task_type=task_type,
        competencies=competencies,
        exactness=exactness,
        authority_requirement=authority,
        freshness=freshness,
        safety=safety,
        applicability=applicability,
        diversity=diversity,
        current_verification_required=freshness == "current_external_required",
        reasons=reasons,
    )


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"line {number} is not an object")
            rows.append(row)
    except (OSError, ValueError, TypeError) as exc:
        raise CorpusProjectionUnavailableError(
            f"corpus artifact {path.name} is unreadable: {type(exc).__name__}: {exc}"
        ) from exc
    return rows


def _candidate_artifact_paths(artifacts: dict[str, Any]) -> dict[str, Path]:
    missing = sorted(set(_CORPUS_ARTIFACT_FILENAMES) - set(artifacts))
    if missing:
        raise CorpusProjectionUnavailableError(
            f"corpus candidate is missing required artifacts: {', '.join(missing)}"
        )
    resolved = {key: Path(artifacts[key]).expanduser() for key in _CORPUS_ARTIFACT_FILENAMES}
    absent = [key for key, path in resolved.items() if not path.is_file()]
    if absent:
        raise CorpusProjectionUnavailableError(
            f"corpus candidate artifacts do not exist: {', '.join(sorted(absent))}"
        )
    return resolved


def _manifest_memberships(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    memberships: set[tuple[str, str]] = set()
    for row in rows:
        source_id = str(row.get("source_id") or "")
        for profile in row.get("expert_profiles") or []:
            memberships.add((str(profile), source_id))
        memberships.add(("general_research", source_id))
    return memberships


def validate_corpus_candidate(artifacts: dict[str, Any]) -> dict[str, Any]:
    """Validate one frozen corpus candidate across every runtime representation."""
    paths = _candidate_artifact_paths(artifacts)
    manifest_rows = _load_jsonl(paths["source_manifest"])
    if not manifest_rows:
        raise CorpusProjectionUnavailableError("corpus source manifest is empty")

    source_rows: dict[str, dict[str, Any]] = {}
    logical_by_source: dict[str, str] = {}
    for row in manifest_rows:
        source_id = str(row.get("source_id") or "")
        source_sha = str(row.get("sha256") or row.get("source_sha256") or "")
        logical_unit = str(row.get("logical_unit_id") or "")
        if not source_id or source_id in source_rows:
            raise CorpusProjectionUnavailableError("source manifest contains missing or duplicate source_id")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha):
            raise CorpusProjectionUnavailableError(f"source {source_id} has invalid SHA-256 identity")
        if not logical_unit:
            raise CorpusProjectionUnavailableError(f"source {source_id} has no logical_unit_id")
        profiles = row.get("expert_profiles") or []
        if any(profile not in CORPUS_REQUIRED_PROFILES[:-1] for profile in profiles):
            raise CorpusProjectionUnavailableError(f"source {source_id} has unknown expert profile")
        source_rows[source_id] = row
        logical_by_source[source_id] = logical_unit
        for optional_path in ("local_path", "evidence_path"):
            value = row.get(optional_path)
            if value and not Path(str(value)).expanduser().exists():
                raise CorpusProjectionUnavailableError(
                    f"source {source_id} has unresolved provenance path {optional_path}"
                )

    expected_memberships = _manifest_memberships(manifest_rows)
    expected_profiles = set(CORPUS_REQUIRED_PROFILES)

    try:
        collections = json.loads(paths["collections"].read_text(encoding="utf-8"))
        profiles = json.loads(paths["profiles"].read_text(encoding="utf-8"))
        benchmark = json.loads(paths["benchmark"].read_text(encoding="utf-8"))
        ledger = json.loads(paths["correction_ledger"].read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise CorpusProjectionUnavailableError(
            f"corpus JSON artifact is unreadable: {type(exc).__name__}: {exc}"
        ) from exc

    collection_profiles = collections.get("profiles") or {}
    membership_lists = collections.get("source_memberships") or {}
    if set(collection_profiles) != expected_profiles or set(membership_lists) != expected_profiles:
        raise CorpusProjectionUnavailableError("collections do not define exactly the nine required profiles")
    collection_memberships = {
        (profile, str(source_id))
        for profile, source_ids in membership_lists.items()
        for source_id in source_ids
    }
    if collection_memberships != expected_memberships:
        raise CorpusProjectionUnavailableError("collections membership differs from source manifest truth")

    profile_counts: dict[str, dict[str, int]] = {}
    for profile in CORPUS_REQUIRED_PROFILES:
        source_ids = {source_id for expert, source_id in expected_memberships if expert == profile}
        logical_units = {logical_by_source[source_id] for source_id in source_ids}
        declared = collection_profiles[profile]
        if int(declared.get("ready_source_count", -1)) != len(source_ids):
            raise CorpusProjectionUnavailableError(f"collection source count is stale for {profile}")
        if int(declared.get("ready_logical_unit_count", -1)) != len(logical_units):
            raise CorpusProjectionUnavailableError(f"collection logical-unit count is stale for {profile}")
        profile_counts[profile] = {"sources": len(source_ids), "logical_units": len(logical_units)}

    if set(profiles) != expected_profiles:
        raise CorpusProjectionUnavailableError("retrieval profiles do not define exactly the nine required profiles")
    for profile, declared in profiles.items():
        if "ready_source_count" in declared and int(declared["ready_source_count"]) != profile_counts[profile]["sources"]:
            raise CorpusProjectionUnavailableError(f"retrieval profile source count is stale for {profile}")
        if "ready_logical_unit_count" in declared and int(declared["ready_logical_unit_count"]) != profile_counts[profile]["logical_units"]:
            raise CorpusProjectionUnavailableError(f"retrieval profile logical-unit count is stale for {profile}")

    ingest_rows = _load_jsonl(paths["ingest_requests"])
    ingest_by_source: dict[str, dict[str, Any]] = {}
    for request in ingest_rows:
        evidence = request.get("evidence") or {}
        source_id = str(evidence.get("source_id") or "")
        if not source_id or source_id in ingest_by_source:
            raise CorpusProjectionUnavailableError("ingest requests contain missing or duplicate source identity")
        ingest_by_source[source_id] = request
    if set(ingest_by_source) != set(source_rows):
        raise CorpusProjectionUnavailableError("ingest request source set differs from source manifest truth")

    evidence_fields = {
        "source_sha256": "sha256",
        "logical_unit_id": "logical_unit_id",
        "retrieval_title": "retrieval_title",
        "domains": "domains",
        "subjects": "subjects",
        "expert_profiles": "expert_profiles",
        "publication_year": "publication_year",
        "edition": "edition",
        "clinical_use_policy": "clinical_use_policy",
    }
    for source_id, request in ingest_by_source.items():
        evidence = request.get("evidence") or {}
        source = source_rows[source_id]
        for evidence_key, source_key in evidence_fields.items():
            left = evidence.get(evidence_key)
            right = source.get(source_key)
            if left != right:
                raise CorpusProjectionUnavailableError(
                    f"ingest evidence differs from manifest for {source_id}: {evidence_key}"
                )
        tag_profiles = {
            tag.removeprefix("expert_")
            for tag in request.get("tags") or []
            if isinstance(tag, str) and tag.startswith("expert_")
        }
        if tag_profiles != set(source.get("expert_profiles") or []):
            raise CorpusProjectionUnavailableError(
                f"ingest expert tags differ from manifest for {source_id}"
            )

    try:
        wal_path = paths["fts_db"].with_name(paths["fts_db"].name + "-wal")
        sqlite_uri = f"file:{paths['fts_db']}?mode=ro" if wal_path.exists() else f"file:{paths['fts_db']}?mode=ro&immutable=1"
        with sqlite3.connect(sqlite_uri, uri=True) as conn:
            integrity = conn.execute("PRAGMA quick_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise CorpusProjectionUnavailableError("corpus FTS database failed quick_check")
            db_memberships = {
                (str(profile), str(source_id))
                for profile, source_id in conn.execute("SELECT expert, source_id FROM expert_membership")
            }
            if db_memberships != expected_memberships:
                raise CorpusProjectionUnavailableError("FTS expert membership differs from source manifest truth")
            membership_logicals = {
                (str(source_id), str(logical_unit))
                for source_id, logical_unit in conn.execute(
                    "SELECT source_id, logical_unit_id FROM expert_membership"
                )
            }
            if any(logical_by_source.get(source_id) != logical for source_id, logical in membership_logicals):
                raise CorpusProjectionUnavailableError("FTS membership logical-unit identity is stale")
            chunk_rows = conn.execute(
                "SELECT source_id, logical_unit_id, retrieval_title, work_id, locator_start, locator_end "
                "FROM chunks"
            ).fetchall()
    except sqlite3.Error as exc:
        raise CorpusProjectionUnavailableError(
            f"corpus FTS database is unreadable: {type(exc).__name__}: {exc}"
        ) from exc

    chunk_sources: set[str] = set()
    for source_id, logical_unit, retrieval_title, work_id, locator_start, locator_end in chunk_rows:
        source_id = str(source_id or "")
        if source_id not in source_rows:
            raise CorpusProjectionUnavailableError("FTS chunk references a source absent from manifest")
        source = source_rows[source_id]
        if str(logical_unit or "") != logical_by_source[source_id]:
            raise CorpusProjectionUnavailableError(f"FTS chunk logical-unit identity is stale for {source_id}")
        expected_title = str(source.get("retrieval_title") or source.get("title") or "")
        if str(retrieval_title or "") != expected_title:
            raise CorpusProjectionUnavailableError(f"FTS chunk retrieval title is stale for {source_id}")
        if str(work_id or "") != str(source.get("work_id") or ""):
            raise CorpusProjectionUnavailableError(f"FTS chunk work identity is stale for {source_id}")
        if not str(locator_start or "").strip() or not str(locator_end or "").strip():
            raise CorpusProjectionUnavailableError(f"FTS chunk provenance locator is missing for {source_id}")
        chunk_sources.add(source_id)
    if chunk_sources != set(source_rows):
        raise CorpusProjectionUnavailableError("manifest contains source without resolvable FTS chunks")

    expected_versions = {
        "policy_version": CORPUS_EVIDENCE_POLICY_VERSION,
        "ranking_version": CORPUS_RANKING_VERSION,
        "clinical_policy_version": CORPUS_CLINICAL_POLICY_VERSION,
    }
    for key, value in expected_versions.items():
        if benchmark.get(key) != value:
            raise CorpusProjectionUnavailableError(f"benchmark {key} is not the runtime policy version")
    results = benchmark.get("results") or []
    benchmark_profiles = {str(result.get("profile") or "") for result in results if result.get("pass") is True}
    if benchmark_profiles != expected_profiles:
        raise CorpusProjectionUnavailableError("benchmark does not prove all nine expert profiles")
    if any(result.get("pass") is not True for result in results):
        raise CorpusProjectionUnavailableError("benchmark contains a failed exact-candidate fixture")
    summary = benchmark.get("summary") or {}
    if int(summary.get("cases", -1)) != len(results) or int(summary.get("passed", -1)) != len(results) or int(summary.get("failed", -1)) != 0:
        raise CorpusProjectionUnavailableError("benchmark summary does not match exact candidate results")
    for result in results:
        profile = str(result.get("profile") or "")
        allowed = {source_id for expert, source_id in expected_memberships if expert == profile}
        for hit in result.get("top5") or []:
            source_id = str(hit.get("source_id") or "")
            if source_id not in allowed:
                raise CorpusProjectionUnavailableError(
                    f"benchmark fixture {result.get('id')} contains out-of-profile source {source_id}"
                )

    if ledger.get("schema") != "kitty.corpus-correction-ledger.v1" or not isinstance(ledger.get("changes"), list):
        raise CorpusProjectionUnavailableError("correction ledger is missing its versioned change inventory")

    return {
        "source_count": len(source_rows),
        "logical_unit_count": len(set(logical_by_source.values())),
        "membership_count": len(expected_memberships),
        "chunk_count": len(chunk_rows),
        "profile_counts": profile_counts,
        "benchmark_profiles": benchmark_profiles,
    }


def _candidate_identity(
    artifact_receipts: dict[str, dict[str, Any]], *, publisher_git_commit: str
) -> str:
    basis = {
        "schema": "kitty.corpus-candidate.v1",
        "publisher_git_commit": publisher_git_commit,
        "policy_version": CORPUS_EVIDENCE_POLICY_VERSION,
        "ranking_version": CORPUS_RANKING_VERSION,
        "clinical_policy_version": CORPUS_CLINICAL_POLICY_VERSION,
        "truth_owner": "source_manifest",
        "artifacts": {
            key: {"sha256": value["sha256"], "bytes": value["bytes"]}
            for key, value in sorted(artifact_receipts.items())
        },
    }
    return hashlib.sha256(_canonical_json_bytes(basis)).hexdigest()


def publish_corpus_candidate(
    artifacts: dict[str, Any], publication_root: str | Path, *, publisher_git_commit: str
) -> dict[str, Any]:
    """Freeze a validated corpus as one immutable, content-addressed publication."""
    paths = _candidate_artifact_paths(artifacts)
    root = Path(publication_root).expanduser()
    candidates = root / "candidates"
    candidates.mkdir(parents=True, exist_ok=True)

    # SQLite WAL state is part of the committed database even though it is not
    # present in the main .sqlite bytes. Materialize one self-contained snapshot
    # before validation, hashing, and publication so the receipt certifies the
    # exact rows runtime will read.
    frozen_db = candidates / f".fts-freeze-{uuid.uuid4().hex}.sqlite"
    source_uri = f"file:{paths['fts_db']}?mode=ro"
    try:
        with sqlite3.connect(source_uri, uri=True) as source_conn, sqlite3.connect(frozen_db) as frozen_conn:
            source_conn.backup(frozen_conn)
        frozen_paths = dict(paths)
        frozen_paths["fts_db"] = frozen_db
        validation = validate_corpus_candidate(frozen_paths)
        artifact_receipts = {
            key: {
                "filename": _CORPUS_ARTIFACT_FILENAMES[key],
                "sha256": _sha256_path(path),
                "bytes": path.stat().st_size,
            }
            for key, path in frozen_paths.items()
        }
        candidate_id = _candidate_identity(artifact_receipts, publisher_git_commit=publisher_git_commit)
        destination = candidates / candidate_id
        receipt_data = {
            "schema": "kitty.corpus-publication-receipt.v1",
            "candidate_id": candidate_id,
            "publisher_git_commit": publisher_git_commit,
            "truth_owner": "source_manifest",
            "policy_version": CORPUS_EVIDENCE_POLICY_VERSION,
            "ranking_version": CORPUS_RANKING_VERSION,
            "clinical_policy_version": CORPUS_CLINICAL_POLICY_VERSION,
            "summary": {
                **{key: value for key, value in validation.items() if key != "benchmark_profiles"},
                "benchmark_profiles": sorted(validation["benchmark_profiles"]),
            },
            "artifacts": artifact_receipts,
        }
        receipt_bytes = _canonical_json_bytes(receipt_data)
        expected_receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()

        if not destination.exists():
            staging = candidates / f".{candidate_id}.staging-{uuid.uuid4().hex}"
            staging.mkdir()
            try:
                for key, source in frozen_paths.items():
                    target = staging / _CORPUS_ARTIFACT_FILENAMES[key]
                    shutil.copyfile(source, target)
                    if _sha256_path(target) != artifact_receipts[key]["sha256"]:
                        raise CorpusProjectionUnavailableError(f"published artifact copy changed bytes: {key}")
                    target.chmod(0o444)
                receipt_path = staging / "candidate_receipt.json"
                receipt_path.write_bytes(receipt_bytes)
                receipt_path.chmod(0o444)
                os.replace(staging, destination)
                destination.chmod(0o555)
            except Exception:
                if staging.exists():
                    for child in staging.iterdir():
                        child.chmod(0o644)
                    staging.rmdir() if not any(staging.iterdir()) else shutil.rmtree(staging)
                raise

        receipt_path = destination / "candidate_receipt.json"
        verified = _verify_published_receipt(str(receipt_path), expected_receipt_sha)
        if verified.get("candidate_id") != candidate_id:
            raise CorpusProjectionUnavailableError("published candidate directory contains a different receipt")
        frozen_artifacts = {
            key: receipt_path.parent / descriptor["filename"]
            for key, descriptor in verified["artifacts"].items()
        }
        frozen_validation = validate_corpus_candidate(frozen_artifacts)
        if frozen_validation != validation:
            raise CorpusProjectionUnavailableError("published corpus validation differs from pre-publication snapshot")
        return {
            "candidate_id": candidate_id,
            "receipt_path": receipt_path,
            "receipt_sha256": expected_receipt_sha,
            "validation": validation,
        }
    finally:
        frozen_db.unlink(missing_ok=True)


@functools.lru_cache(maxsize=16)
def _verify_published_receipt(
    receipt_path_value: str | Path, expected_receipt_sha256: str | None = None
) -> dict[str, Any]:
    receipt_path = Path(receipt_path_value).expanduser()
    if not receipt_path.is_file():
        raise CorpusProjectionUnavailableError("published corpus receipt is missing")
    actual_receipt_sha = _sha256_path(receipt_path)
    if expected_receipt_sha256 and actual_receipt_sha != expected_receipt_sha256:
        raise CorpusProjectionUnavailableError("published corpus receipt hash does not match exact binding")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise CorpusProjectionUnavailableError("published corpus receipt is unreadable") from exc
    if receipt.get("schema") != "kitty.corpus-publication-receipt.v1":
        raise CorpusProjectionUnavailableError("published corpus receipt schema is unsupported")
    for key, value in {
        "policy_version": CORPUS_EVIDENCE_POLICY_VERSION,
        "ranking_version": CORPUS_RANKING_VERSION,
        "clinical_policy_version": CORPUS_CLINICAL_POLICY_VERSION,
    }.items():
        if receipt.get(key) != value:
            raise CorpusProjectionUnavailableError(f"published corpus {key} differs from runtime policy")
    artifacts = receipt.get("artifacts") or {}
    if set(artifacts) != set(_CORPUS_ARTIFACT_FILENAMES):
        raise CorpusProjectionUnavailableError("published corpus receipt has incomplete artifact inventory")
    for key, descriptor in artifacts.items():
        artifact_path = receipt_path.parent / str(descriptor.get("filename") or "")
        if not artifact_path.is_file():
            raise CorpusProjectionUnavailableError(f"published corpus artifact is missing: {key}")
        if artifact_path.stat().st_size != int(descriptor.get("bytes", -1)):
            raise CorpusProjectionUnavailableError(f"published corpus artifact hash/size mismatch: {key}")
        if _sha256_path(artifact_path) != descriptor.get("sha256"):
            raise CorpusProjectionUnavailableError(f"published corpus artifact hash mismatch: {key}")
    candidate_id = _candidate_identity(
        artifacts, publisher_git_commit=str(receipt.get("publisher_git_commit") or "")
    )
    if receipt.get("candidate_id") != candidate_id:
        raise CorpusProjectionUnavailableError("published corpus candidate identity does not match receipt")
    return receipt


def _publication_binding_matches(candidate_id: str, receipt_sha256: str) -> bool:
    return (
        CORPUS_PUBLICATION_BINDING.get("candidate_id") == candidate_id
        and CORPUS_PUBLICATION_BINDING.get("receipt_sha256") == receipt_sha256
    )


def _validate_published_projection(projection: dict[str, Any]) -> tuple[dict[str, Any], Path, Path]:
    candidate_id = str(projection.get("candidate_id") or "")
    receipt_sha = str(projection.get("receipt_sha256") or "")
    receipt_path = Path(str(projection.get("receipt") or "")).expanduser()
    if not _publication_binding_matches(candidate_id, receipt_sha):
        raise CorpusProjectionUnavailableError("active corpus candidate does not match tracked publication binding")
    receipt = _verify_published_receipt(str(receipt_path), receipt_sha)
    if receipt.get("candidate_id") != candidate_id:
        raise CorpusProjectionUnavailableError("active corpus candidate does not match published receipt")
    artifacts = receipt["artifacts"]
    db_path = receipt_path.parent / artifacts["fts_db"]["filename"]
    manifest_path = receipt_path.parent / artifacts["source_manifest"]["filename"]
    if Path(str(projection.get("fts_db") or "")).expanduser() != db_path:
        raise CorpusProjectionUnavailableError("active corpus FTS path is not the bound published artifact")
    if Path(str(projection.get("source_manifest") or "")).expanduser() != manifest_path:
        raise CorpusProjectionUnavailableError("active corpus manifest path is not the bound published artifact")
    return receipt, db_path, manifest_path


def activate_published_corpus_candidate(
    receipt_path: str | Path, projection_path: str | Path
) -> dict[str, Any]:
    """Atomically activate only the exact tracked receipt; restore the old pointer on failure."""
    receipt_path = Path(receipt_path).expanduser().resolve()
    receipt_sha = _sha256_path(receipt_path)
    receipt = _verify_published_receipt(str(receipt_path), receipt_sha)
    candidate_id = str(receipt.get("candidate_id") or "")
    if not _publication_binding_matches(candidate_id, receipt_sha):
        raise CorpusProjectionUnavailableError("published corpus receipt does not match tracked binding")

    artifacts = receipt["artifacts"]

    def artifact_path(key: str) -> Path:
        return (receipt_path.parent / artifacts[key]["filename"]).resolve()

    summary = receipt.get("summary") or {}
    projection = {
        "schema": "kitty.runtime-retrieval-projection.v2",
        "status": "active",
        "candidate_id": candidate_id,
        "receipt": str(receipt_path),
        "receipt_sha256": receipt_sha,
        "publisher_git_commit": receipt.get("publisher_git_commit"),
        "policy_version": receipt.get("policy_version"),
        "ranking_version": receipt.get("ranking_version"),
        "clinical_policy_version": receipt.get("clinical_policy_version"),
        "source_manifest": str(artifact_path("source_manifest")),
        "source_manifest_sha256": artifacts["source_manifest"]["sha256"],
        "collections": str(artifact_path("collections")),
        "ingest_requests": str(artifact_path("ingest_requests")),
        "fts_db": str(artifact_path("fts_db")),
        "fts_db_sha256": artifacts["fts_db"]["sha256"],
        "profiles": str(artifact_path("profiles")),
        "benchmark": str(artifact_path("benchmark")),
        "correction_ledger": str(artifact_path("correction_ledger")),
        "sources": summary.get("source_count"),
        "logical_units": summary.get("logical_unit_count"),
        "memberships": summary.get("membership_count"),
        "chunks": summary.get("chunk_count"),
    }
    # Verify the complete pointer before touching the active file.
    _validate_published_projection(projection)

    pointer = Path(projection_path).expanduser()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    previous = pointer.read_bytes() if pointer.exists() else None
    temp = pointer.with_name(f".{pointer.name}.tmp-{uuid.uuid4().hex}")
    try:
        temp.write_bytes(_canonical_json_bytes(projection))
        os.replace(temp, pointer)
        loaded = json.loads(pointer.read_text(encoding="utf-8"))
        _validate_published_projection(loaded)
    except Exception:
        temp.unlink(missing_ok=True)
        if previous is None:
            pointer.unlink(missing_ok=True)
        else:
            rollback = pointer.with_name(f".{pointer.name}.rollback-{uuid.uuid4().hex}")
            rollback.write_bytes(previous)
            os.replace(rollback, pointer)
        raise
    return projection


def _resolve_corpus_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else DATA_DIR / path


def _manifest_evidence(row: dict[str, Any]) -> EvidenceMetadata:
    quality = row.get("quality_dimensions") or {}
    return EvidenceMetadata(
        source_id=str(row["source_id"]),
        source_sha256=str(row.get("sha256") or row.get("source_sha256") or ""),
        logical_unit_id=str(row["logical_unit_id"]),
        work_id=row.get("work_id"),
        series_id=row.get("series_id"),
        series_order=row.get("series_order"),
        retrieval_title=str(row.get("retrieval_title") or row.get("title") or ""),
        publication_year=row.get("publication_year"),
        edition=str(row.get("edition") or ""),
        metadata_basis=str(row.get("metadata_basis") or ""),
        domains=list(row.get("domains") or []),
        subjects=list(row.get("subjects") or []),
        expert_profiles=list(row.get("expert_profiles") or []),
        authority_tier=str(row.get("authority_tier") or quality.get("authority_credibility") or ""),
        authority_status=str(row.get("authority_status") or quality.get("authority_credibility") or ""),
        currency_sensitivity=str(row.get("currency_sensitivity") or quality.get("date_sensitivity") or ""),
        currency_status=str(row.get("currency_status") or quality.get("currency_status") or ""),
        evidence_role=str(row.get("evidence_role") or quality.get("evidence_role") or ""),
        clinical_use_policy=str(row.get("clinical_use_policy") or quality.get("clinical_use_policy") or ""),
        work_relation=str(row.get("work_relation") or ""),
    )


_FTS_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
    "from", "get", "how", "i", "in", "is", "it", "of", "on", "or", "out",
    "the", "this", "to", "what", "when", "where", "which", "why", "with",
}


def _fts_query(query: str) -> str:
    """Build a safe broad-match FTS5 query from untrusted user text."""
    terms = [
        term.lower()
        for term in re.findall(r"[A-Za-z0-9]+", query)
        if term.lower() not in _FTS_STOPWORDS
    ]
    # FTS5 MATCH has its own query language. Quote every token so punctuation
    # from user text cannot become syntax, then use OR so natural-language
    # paraphrases need not contain every filler word to retrieve candidates.
    return " OR ".join(f'"{term}"' for term in dict.fromkeys(terms))


def _active_corpus_projection() -> Optional[tuple[dict[str, Any], Path, Path]]:
    explicit_projection = os.environ.get("KITTY_CORPUS_RETRIEVAL_PROJECTION")
    projection_path = Path(
        explicit_projection
        or str(DATA_DIR / "books_corpus/manifests/runtime_retrieval_projection_active.json")
    ).expanduser()
    if not projection_path.exists():
        return None
    try:
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        if projection.get("status") != "active":
            return None
        if projection.get("schema") == "kitty.runtime-retrieval-projection.v2":
            _, db_path, manifest_path = _validate_published_projection(projection)
        else:
            # A custom projection path is an explicit developer/test override.  The
            # production pointer, once a tracked binding exists, may not downgrade
            # back to an unreceipted v1 projection.
            if CORPUS_PUBLICATION_BINDING and explicit_projection is None:
                raise CorpusProjectionUnavailableError(
                    "active expert corpus projection is unpublished or unbound"
                )
            db_path = _resolve_corpus_path(str(projection["fts_db"]))
            manifest_path = _resolve_corpus_path(str(projection["source_manifest"]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CorpusProjectionUnavailableError(
            f"active expert corpus projection is unreadable: {type(exc).__name__}: {exc}"
        ) from exc
    if not db_path.exists() or not manifest_path.exists():
        raise CorpusProjectionUnavailableError("active expert corpus projection is incomplete")
    return projection, db_path, manifest_path


def _corpus_readonly_db_uri(projection: dict[str, Any], db_path: Path) -> str:
    suffix = "?mode=ro&immutable=1" if projection.get("schema") == "kitty.runtime-retrieval-projection.v2" else "?mode=ro"
    return f"file:{db_path}{suffix}"


def require_active_corpus_expert(expert_profile: str) -> str:
    expert = expert_profile.strip()
    if not expert:
        raise UnknownCorpusExpertError("expert profile must be non-empty")
    active = _active_corpus_projection()
    if active is None:
        raise CorpusProjectionUnavailableError("expert source corpus is not active")
    projection, db_path, _ = active
    if expert == "general_research":
        return expert
    try:
        with sqlite3.connect(_corpus_readonly_db_uri(projection, db_path), uri=True) as conn:
            found = conn.execute(
                "SELECT 1 FROM expert_membership WHERE expert=? LIMIT 1", (expert,)
            ).fetchone()
    except sqlite3.Error as exc:
        raise CorpusProjectionUnavailableError(
            f"active expert membership index is unavailable: {type(exc).__name__}: {exc}"
        ) from exc
    if found is None:
        raise UnknownCorpusExpertError(f"unknown expert profile {expert!r}")
    return expert


def active_corpus_experts() -> dict[str, Any]:
    """Project the active corpus's retrieval profiles for the product UI."""
    active = _active_corpus_projection()
    if active is None:
        return {
            "status": "unavailable",
            "experts": [],
            "message": "Expert source corpus is not active.",
        }
    _, _, manifest_path = active
    try:
        rows = [
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, ValueError, TypeError) as exc:
        raise CorpusProjectionUnavailableError(
            f"active expert source manifest is unreadable: {type(exc).__name__}: {exc}"
        ) from exc

    aggregate: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_id = str(row.get("source_id") or "")
        logical_unit_id = str(row.get("logical_unit_id") or source_id)
        title = str(row.get("retrieval_title") or row.get("title") or "")
        profiles = [
            expert for expert in (row.get("expert_profiles") or [])
            if isinstance(expert, str) and expert
        ]
        if "general_research" not in profiles:
            profiles.append("general_research")
        for expert in profiles:
            info = aggregate.setdefault(
                expert,
                {
                    "source_ids": set(),
                    "logical_units": set(),
                    "subjects": Counter(),
                    "formats": set(),
                    "sample_title": "",
                },
            )
            if source_id:
                info["source_ids"].add(source_id)
            if logical_unit_id:
                info["logical_units"].add(logical_unit_id)
            info["subjects"].update(str(item) for item in row.get("subjects") or [] if item)
            fmt = str(row.get("format") or "")
            if fmt:
                info["formats"].add(fmt)
            if title and not info["sample_title"]:
                info["sample_title"] = title

    experts: list[dict[str, Any]] = []
    for expert, info in aggregate.items():
        tags = sorted(info["subjects"], key=lambda tag: (-info["subjects"][tag], tag))[:5]
        experts.append(
            {
                "id": expert,
                "label": _EXPERT_LABELS.get(expert, expert.replace("_", " ").title()),
                "book_count": len(info["logical_units"]),
                "source_count": len(info["source_ids"]),
                "tags": tags,
                "formats": sorted(info["formats"]),
                "sample_title": info["sample_title"],
            }
        )
    experts.sort(key=lambda item: (-int(item["book_count"]), str(item["label"])))
    return {"status": "active", "experts": experts}


def _corpus_logical_unit_cap(query: str) -> int:
    policy = build_evidence_policy(query)
    if policy.diversity == "single_authoritative_ok":
        return CORPUS_EXACT_LOOKUP_MAX_CHUNKS_PER_LOGICAL_UNIT
    return CORPUS_MAX_CHUNKS_PER_LOGICAL_UNIT


def _search_active_corpus_fts(
    query: str, limit: int, *, expert_profile: str | None = None
) -> Optional[list[dict[str, Any]]]:
    active = _active_corpus_projection()
    if active is None:
        return None
    projection, db_path, manifest_path = active
    source_rows = {
        row["source_id"]: row
        for row in (
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    match_query = _fts_query(query)
    if not match_query:
        return []

    hits: list[dict[str, Any]] = []
    unit_counts: Counter[str] = Counter()
    per_unit_limit = _corpus_logical_unit_cap(query)
    batch_size = max(limit * 8, 64)
    offset = 0
    with sqlite3.connect(_corpus_readonly_db_uri(projection, db_path), uri=True) as conn:
        expert = require_active_corpus_expert(expert_profile) if expert_profile else None
        while len(hits) < limit:
            if expert and expert != "general_research":
                rows = conn.execute(
                    "SELECT chunks.chunk_id,chunks.source_id,chunks.logical_unit_id,chunks.source_title,"
                    "chunks.retrieval_title,chunks.work_id,chunks.work_title,chunks.domains,chunks.subjects,"
                    "chunks.doc_type,chunks.locator_start,chunks.locator_end,chunks.text,bm25(chunks) "
                    "FROM chunks JOIN expert_membership em ON em.source_id=chunks.source_id "
                    "WHERE chunks MATCH ? AND em.expert=? ORDER BY bm25(chunks) LIMIT ? OFFSET ?",
                    (match_query, expert, batch_size, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT chunk_id,source_id,logical_unit_id,source_title,retrieval_title,work_id,work_title,"
                    "domains,subjects,doc_type,locator_start,locator_end,text,bm25(chunks) "
                    "FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks) LIMIT ? OFFSET ?",
                    (match_query, batch_size, offset),
                ).fetchall()
            if not rows:
                break

            for rank, row in enumerate(rows, start=offset + 1):
                (
                    chunk_id, source_id, logical_unit_id, source_title, retrieval_title,
                    work_id, work_title, domains, subjects, doc_type, locator_start,
                    locator_end, text, bm25_score,
                ) = row
                unit_key = logical_unit_id or source_id or chunk_id
                if unit_counts[unit_key] >= per_unit_limit:
                    continue
                unit_counts[unit_key] += 1
                source_row = source_rows.get(source_id)
                if source_row is None:
                    continue
                evidence = _manifest_evidence(source_row)
                metadata = evidence.to_chroma()
                metadata.update({
                    "chunk_id": chunk_id,
                    "locator_start": locator_start,
                    "locator_end": locator_end,
                    "work_title": work_title or "",
                    "source_title": source_title or "",
                })
                hits.append({
                    "text": text,
                    "source": retrieval_title or source_title or evidence.retrieval_title or source_id,
                    "doc_type": doc_type or "general",
                    "score": 1.0 / rank,
                    "fts_score": bm25_score,
                    "ingested_at": 0,
                    "index": 0,
                    "metadata": metadata,
                    "evidence": evidence.model_dump(),
                    "retrieval_method": "fts",
                })
                if len(hits) >= limit:
                    break

            offset += len(rows)
            if len(rows) < batch_size:
                break
    return hits


def _search_hit_identity(hit: dict[str, Any]) -> tuple[Any, ...]:
    evidence = hit.get("evidence") or {}
    logical_unit_id = evidence.get("logical_unit_id")
    if logical_unit_id:
        return ("logical_unit", logical_unit_id)
    metadata = hit.get("metadata") or {}
    return (
        "chunk",
        hit.get("source"),
        metadata.get("content_hash"),
        hit.get("index"),
        str(hit.get("text") or "")[:120],
    )


def _merge_ranked_hits(
    corpus_hits: list[dict[str, Any]],
    vector_hits: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Interleave independent ranked lists while preserving logical-unit diversity."""
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for index in range(max(len(corpus_hits), len(vector_hits))):
        for pool in (corpus_hits, vector_hits):
            if index >= len(pool):
                continue
            hit = pool[index]
            identity = _search_hit_identity(hit)
            if identity in seen:
                continue
            seen.add(identity)
            merged.append(hit)
            if len(merged) >= limit:
                return merged
    return merged


async def ingest(
    file_path: str | Path,
    sensitivity: str = "low",
    source_label: Optional[str] = None,
    doc_type: Optional[str] = None,
    collection: str = "general",
    tags: Optional[list[str]] = None,
    evidence: Optional[EvidenceMetadata] = None,
    force_refresh: bool = False,
) -> IngestionResult:
    """High-leverage entry point for document ingestion."""
    path = Path(file_path)
    if not path.exists():
        return IngestionResult(
            source=str(file_path),
            status="failed",
            content_hash="",
            error_message=f"File not found: {path}",
        )

    # 1. Extraction (Clerk)
    raw_text = clerk._extract_text(path)
    source = source_label or path.name

    # 2. Ingestion Contract (Hashing & Dedup)
    content_hash = (
        archivist._get_content_hash(raw_text)
        if raw_text
        else archivist._get_content_hash(str(path))
    )
    store = archivist._get_collection()

    if not force_refresh:
        existing = store.get(where={"content_hash": content_hash})
        if existing["ids"]:
            logger.info("Content from %s already ingested (hash match), skipping", source)
            return IngestionResult(source=source, status="skipped", content_hash=content_hash)

    # 3. Snapshot existing chunk ids. They remain authoritative until a complete
    # replacement has been embedded and successfully stored.
    existing_source = store.get(where={"source": source})
    existing_ids = list(existing_source.get("ids") or [])

    # 4. Judgment (Librarian)
    resolved_type = doc_type or librarian.detect_doc_type(path, raw_text[:1000] if raw_text else "")
    taste_report: LibrarianReport = await asyncio.to_thread(
        librarian.generate_source_summary, source, raw_text[:4000], resolved_type
    )

    # 5. Pipeline Execution
    chunks, chunk_metadatas = await _run_pipeline(
        path, raw_text, source, resolved_type, taste_report
    )

    if not chunks:
        logger.warning("No high-quality content found to ingest from %s", path)
        return IngestionResult(source=source, status="skipped", content_hash=content_hash)

    # 6. Storage (Archivist)
    embeddings = await asyncio.to_thread(archivist._embed, chunks)
    generation = uuid.uuid4().hex
    ids = [f"{source}__chunk_{i}_{generation}" for i in range(len(chunks))]

    final_metadatas = _prepare_metadatas(
        path,
        source,
        sensitivity,
        resolved_type,
        collection,
        tags or [],
        content_hash,
        taste_report,
        chunk_metadatas,
        evidence,
    )
    # Store the replacement first. Only after the new chunks are durable do we
    # remove the previous source ids. A cleanup failure rolls back the new ids,
    # preferring the old known-good index over a partial/duplicated replacement.
    store.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=final_metadatas)
    if existing_ids:
        try:
            store.delete(ids=existing_ids)
        except Exception:
            try:
                store.delete(ids=ids)
            except Exception as rollback_exc:
                logger.exception(
                    "Replacement cleanup failed for %s and new-chunk rollback also failed: %s",
                    source,
                    rollback_exc,
                )
            raise

    logger.info("Ingested %d chunks from %s (type=%s)", len(chunks), source, resolved_type)
    return IngestionResult(
        source=source,
        status="success",
        chunks_count=len(chunks),
        content_hash=content_hash,
    )


async def search(
    query: str,
    limit: int = 5,
    sensitivity_filter: Optional[str] = None,
    collections: Optional[list[str]] = None,
    sort_by: str = "relevance",
    stitch_context: bool = True,
    expert_profile: str | None = None,
) -> List[Dict[str, Any]]:
    """Unified search across the reconciled corpus and locally ingested knowledge."""
    use_corpus_projection = (
        sort_by == "relevance"
        and sensitivity_filter in (None, "low")
        and (not collections or set(collections) == {"expert_corpus_evidence"})
    )
    if expert_profile and not use_corpus_projection:
        raise KnowledgeSearchError(
            "expert-scoped retrieval requires the active corpus relevance index"
        )

    corpus_hits: Optional[list[dict[str, Any]]] = None
    merge_default_search = use_corpus_projection and not collections and not expert_profile
    if use_corpus_projection:
        corpus_hits = _search_active_corpus_fts(
            query, limit, expert_profile=expert_profile
        )
        if corpus_hits is not None and not merge_default_search:
            return corpus_hits
        if corpus_hits is None and expert_profile:
            raise CorpusProjectionUnavailableError("expert source corpus is not active")

    try:
        query_embedding = list(archivist._embed_cached(query))
        where = _build_search_filter(sensitivity_filter, collections)
        collection = archivist._get_collection()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit * 3, max(1, collection.count())),
            where=where,
        )

        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            dist = results["distances"][0][i] if results["distances"] else 1.0

            chunk_data = {
                "text": doc,
                "source": meta.get("source", "unknown"),
                "doc_type": meta.get("doc_type", "general"),
                "score": 1.0 - dist,
                "ingested_at": meta.get("ingested_at", 0),
                "index": meta.get("chunk_index", 0),
                "metadata": meta,
                "retrieval_method": "vector",
            }
            if meta.get("source_id") and meta.get("logical_unit_id"):
                chunk_data["evidence"] = EvidenceMetadata.from_chroma(meta).model_dump()

            if (
                stitch_context
                and "chunk_index" in meta
                and meta.get("doc_type") not in ("source_summary", "visual_description")
            ):
                chunk_data["text"] = _stitch_neighbor_context(collection, meta, doc)
                chunk_data["stitched"] = True

            chunks.append(chunk_data)

        chunks.sort(
            key=lambda x: x["ingested_at" if sort_by == "recency" else "score"],
            reverse=True,
        )
        if corpus_hits is not None:
            return _merge_ranked_hits(corpus_hits, chunks, limit)
        return chunks[:limit]
    except Exception as exc:
        logger.exception("Knowledge search failed for query=%r", query)
        raise KnowledgeSearchError(
            f"knowledge search failed for query={query!r}: {type(exc).__name__}: {exc}"
        ) from exc


def _build_search_filter(
    sensitivity_filter: Optional[str],
    collections: Optional[list[str]],
) -> Optional[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    if sensitivity_filter:
        filters.append({"sensitivity": sensitivity_filter})
    if collections:
        filters.append({"collection": {"$in": sorted(set(collections))}})
    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


async def answer_as_expert(
    query: str,
    expert: str = "coding_repo",
    limit: int = 5,
    answerer: Optional[Callable[[str], str]] = None,
) -> dict[str, Any]:
    """Answer from an expert's allowed uploaded collections, entirely locally."""
    profile = EXPERT_PROFILES.get(expert)
    if profile is None:
        raise UnknownExpertError(
            f"unknown knowledge expert {expert!r}; available experts: {sorted(EXPERT_PROFILES)}"
        )

    collections = list(profile["collections"])
    chunks = await search(
        query,
        limit=limit,
        collections=collections,
        stitch_context=False,
    )
    if not chunks:
        collection_names = ", ".join(collections)
        return {
            "expert": expert,
            "supported": False,
            "answer": (
                f"Uploaded sources in collection '{collection_names}' do not support this answer."
            ),
            "citations": [],
            "privacy": "local",
        }

    citations = [_citation_from_chunk(index, chunk) for index, chunk in enumerate(chunks, start=1)]
    prompt = _build_expert_prompt(query, profile, chunks, citations)
    answer_fn = answerer or _call_local_expert_model
    try:
        answer = await asyncio.to_thread(answer_fn, prompt)
    except ExpertAnswerError:
        raise
    except Exception as exc:
        raise ExpertAnswerError(
            f"local expert answerer failed: {type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(answer, str) or not answer.strip():
        raise ExpertAnswerError("local expert answerer returned an empty response")
    answer = answer.strip()
    if not any(f"[{citation['id']}]" in answer for citation in citations):
        raise ExpertAnswerError("local expert answer did not include a retrieved-source citation")

    return {
        "expert": expert,
        "supported": True,
        "answer": answer,
        "citations": citations,
        "privacy": "local",
    }


def _citation_from_chunk(
    citation_id: int,
    chunk: dict[str, Any],
) -> dict[str, Any]:
    source = str(chunk.get("source") or "").strip()
    text = str(chunk.get("text") or "").strip()
    if not source or not text:
        raise ExpertAnswerError(f"retrieved chunk {citation_id} is missing source or text")

    metadata = chunk.get("metadata") or {}
    page_num = metadata.get("page_num")
    chunk_index = metadata.get("chunk_index", chunk.get("index"))
    if page_num is not None:
        label = f"{source}, page {page_num}"
    elif chunk_index is not None:
        label = f"{source}, chunk {chunk_index}"
    else:
        label = source
    return {
        "id": citation_id,
        "source": source,
        "page_num": page_num,
        "chunk_index": chunk_index,
        "label": label,
    }


def _build_expert_prompt(
    query: str,
    profile: dict[str, Any],
    chunks: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    prompt_path = Path(profile["prompt_path"])
    try:
        specialist_prompt = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExpertAnswerError(f"could not read expert prompt {prompt_path}: {exc}") from exc

    excerpts: list[str] = []
    for chunk, citation in zip(chunks, citations):
        excerpts.append(f"[{citation['id']}] {citation['label']}\n{str(chunk['text']).strip()}")

    return (
        f"{specialist_prompt}\n\n"
        "## RETRIEVAL CONTRACT\n"
        "Use only the uploaded source excerpts below. "
        "Cite every supported claim with [n]. "
        "If the excerpts do not support the answer, say so plainly.\n\n"
        f"Question: {query.strip()}\n\n"
        "Uploaded source excerpts:\n" + "\n\n".join(excerpts)
    )


def _call_local_expert_model(prompt: str) -> str:
    """Call the loopback-only MLX server; this path never contacts cloud models."""
    payload = {
        "model": LOCAL_EXPERT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,
        "temperature": 0.1,
    }
    response: httpx.Response | None = None
    for attempt in range(2):
        try:
            response = httpx.post(
                LOCAL_EXPERT_URL,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            break
        except httpx.HTTPError as exc:
            if attempt == 0:
                logger.warning(
                    "Local MLX expert request failed; retrying once: url=%s model=%s error=%s",
                    LOCAL_EXPERT_URL,
                    LOCAL_EXPERT_MODEL,
                    exc,
                )
                continue
            failed_response = getattr(exc, "response", None)
            status = getattr(failed_response, "status_code", "unavailable")
            body = str(getattr(failed_response, "text", "") or "<no response body>")
            raise ExpertAnswerError(
                "local MLX expert request failed after 2 attempts: "
                f"url={LOCAL_EXPERT_URL} model={LOCAL_EXPERT_MODEL} "
                f"status={status} response={body[:500]!r} error={exc}"
            ) from exc

    if response is None:
        raise ExpertAnswerError("local MLX expert request produced no response")
    try:
        data = response.json()
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ExpertAnswerError(
            "local MLX expert returned an invalid response: "
            f"status={response.status_code} response={response.text[:500]!r}"
        ) from exc
    if not isinstance(answer, str) or not answer.strip():
        raise ExpertAnswerError("local MLX expert returned empty message content")
    return answer.strip()


def delete_source(source_name: str) -> bool:
    """Prune all chunks belonging to a source."""
    return archivist.delete_source_chunks(source_name)


def get_inventory() -> Dict[str, int]:
    """Get source/chunk counts for status reporting."""
    try:
        collection = archivist._get_collection()
        count = collection.count()
        if count == 0:
            return {}

        metas = collection.get(include=["metadatas"])["metadatas"]
        inventory: dict[str, int] = {}
        for m in metas:
            name = m.get("source", "unknown")
            inventory[name] = inventory.get(name, 0) + 1
        return inventory
    except Exception as e:
        logger.error("Failed to get knowledge inventory: %s", e)
        return {}


# --- Private Implementation Details ---


async def _run_pipeline(
    path: Path, raw_text: str, source: str, doc_type: str, taste: LibrarianReport
) -> tuple[list[str], list[dict]]:
    """Private orchestration of the pipeline stages."""
    profile = _CHUNK_PROFILES.get(doc_type, _CHUNK_PROFILES["general"])
    chunks: list[str] = []
    chunk_metadatas: list[dict] = []

    # A. Source Brief
    chunks.append(f"SOURCE BRIEF: {taste.summary}")
    chunk_metadatas.append({"chunk_index": -1, "doc_type": "source_summary", "is_visual": False})

    # B. Content Extraction & Chunking
    if path.suffix.lower() == ".pdf":
        pages = clerk._extract_pdf_pages(path)
        for page_num, page_text in pages:
            clean = clerk.preprocess_text(page_text)
            if not clean:
                continue
            for chunk in archivist._chunk_text(clean, profile["size"], profile["overlap"]):
                if archivist.is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append(
                        {
                            "chunk_index": len(chunks),
                            "is_visual": False,
                            "page_num": page_num,
                        }
                    )
    else:
        clean = clerk.preprocess_text(raw_text)
        if clean:
            for i, chunk in enumerate(
                archivist._chunk_text(clean, profile["size"], profile["overlap"])
            ):
                if archivist.is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append({"chunk_index": i, "is_visual": False})

    # C. Vision Enrichment
    if taste.needs_vision or doc_type == "service_manual":
        visual_info = await asyncio.to_thread(clerk._extract_visual_descriptions, path)
        for info in visual_info:
            chunks.append(info.text)
            chunk_metadatas.append(
                {
                    "chunk_index": len(chunks) + 1000,
                    "is_visual": True,
                    "page_num": info.page_num,
                    "analysis_type": info.analysis_type,
                }
            )

    return chunks, chunk_metadatas


def _prepare_metadatas(
    path: Path,
    source: str,
    sensitivity: str,
    doc_type: str,
    collection: str,
    tags: list[str],
    content_hash: str,
    taste: LibrarianReport,
    chunk_metadatas: list[dict],
    evidence: Optional[EvidenceMetadata] = None,
) -> list[dict]:
    """Standardize metadata for all chunks using KnowledgeMetadata contract."""
    try:
        stat = path.stat()
        mtime, ctime = int(stat.st_mtime), int(stat.st_ctime)
    except Exception:
        mtime = ctime = int(time.time())

    final = []
    for meta in chunk_metadatas:
        km = KnowledgeMetadata(
            source=source,
            file_path=str(path),
            collection=collection,
            tags_json=json.dumps(tags, separators=(",", ":")),
            sensitivity=sensitivity,
            doc_type=meta.get("doc_type", doc_type),
            content_hash=content_hash,
            modified_at=mtime,
            created_at=ctime,
            ingested_at=int(time.time()),
            authority_score=taste.authority_score,
            relevance_period=taste.relevance_period,
            primary_topic=taste.primary_topic,
            chunk_index=meta["chunk_index"],
            is_visual=meta.get("is_visual", False),
            page_num=meta.get("page_num"),
            analysis_type=meta.get("analysis_type"),
            pollution_warning=taste.pollution_warning,
        )
        prepared = km.to_chroma()
        if evidence is not None:
            prepared.update(evidence.to_chroma())
        final.append(prepared)
    return final


def _stitch_neighbor_context(collection: Any, meta: dict, doc: str) -> str:
    """Fetch and join neighboring chunks (+/- 1) for better context."""
    source = meta["source"]
    idx = meta["chunk_index"]
    neighbor_results = collection.get(
        where={"$and": [{"source": source}, {"chunk_index": {"$in": [idx - 1, idx + 1]}}]}
    )

    if neighbor_results["ids"]:
        neighbors = {
            n_meta["chunk_index"]: n_doc
            for n_idx, (n_meta, n_doc) in enumerate(
                zip(neighbor_results["metadatas"], neighbor_results["documents"])
            )
        }
        parts = []
        if idx - 1 in neighbors:
            parts.append(neighbors[idx - 1])
        parts.append(doc)
        if idx + 1 in neighbors:
            parts.append(neighbors[idx + 1])
        return "\n[...]\n".join(parts)
    return doc


# Backward compatibility aliases
async def ingest_file(*args, **kwargs):
    return await ingest(*args, **kwargs)


async def search_knowledge(*args, **kwargs):
    return await search(*args, **kwargs)


# Backwards-compat re-exports so existing tests can import/patch these names directly
# on the knowledge module rather than on the sub-modules.
from gateway.archivist import _chunk_text, _embed, _get_collection  # noqa: E402, F401
from gateway.clerk import (  # noqa: E402, F401
    _extract_chatgpt_json,
    _extract_jsonl_session,
    _extract_sqlite_journal,
    _extract_text,
)
from gateway.librarian import detect_doc_type  # noqa: E402, F401


def get_knowledge_block(query: str, limit: int = 5) -> str:
    """Format a knowledge context block for **synchronous** callers (scripts, tests).

    **Do not** call this from inside an async request handler or running event loop:
    use ``await knowledge.search(...)`` or ``await context_assembler.get_system_prompt(...)``
    instead. Inside a loop, this function returns an empty string to avoid nest-async bugs.

    For new code, prefer ``await search()`` and assemble prompts in ``context_assembler``.
    """
    import asyncio

    try:
        chunks = asyncio.run(search(query, limit=limit))
    except RuntimeError:
        return ""

    if not chunks:
        return ""
    lines = ["## Relevant knowledge from Kitty's knowledge base:"]
    for chunk in chunks:
        src = chunk.get("source", "unknown")
        dtype = chunk.get("doc_type", "general")
        text = (chunk.get("text") or "")[:400]
        label = f"[Source: {src} | type: {dtype}]"
        lines.append(f"\n{label}\n{text}")
    return "\n".join(lines)
