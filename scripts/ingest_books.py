#!/usr/bin/env python3
"""Book ingestion — 5-expert structure for wicked-fast retrieval.

Scans source folders, deduplicates, routes each book to the right expert domain,
and ingests through knowledge.ingest() with rich metadata.

Experts:
    builder  — code, systems, engineering, math, physics, electronics, automotive
    body     — health, nutrition, anatomy, physical therapy, exercise
    mind     — psychology, habits, cognition, learning, influence, memory
    wisdom   — philosophy, ethics, meaning, systems thinking, meditation
    voice    — communication, conversation, leadership, negotiation

Usage:
    python3.12 scripts/ingest_books.py                      # dry run
    python3.12 scripts/ingest_books.py --execute             # actually ingest
    python3.12 scripts/ingest_books.py --execute --expert builder  # one expert only
    python3.12 scripts/ingest_books.py --execute --limit 10        # first 10 books
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

# ── Sources ──────────────────────────────────────────────────────────────────

SOURCES = [
    Path("/Volumes/DATA/books_canonical_v2"),
    Path("/Volumes/DATA/Books/ingestion_curated_deep_ocr"),
    Path("/Volumes/DATA/Books/ingestion_curated_deep"),
]

INGESTIBLE_EXTENSIONS = {".pdf", ".epub", ".mobi", ".azw3", ".md", ".txt", ".rst", ".docx"}
MIN_FILE_SIZE_BYTES = 5_000

JUNK_PATTERNS = [
    "jacob brizinski cv", "jacob brizinski resume", "empty template",
    "document_cover_image", "cover image", "file id.diz", "metadata.opf",
    "frontmatter.pdf", "glossary.pdf", "google search scraper",
]
JUNK_DIRS = {"FromDocuments", "Empty template", "_archive", ".DS_Store"}

FORMAT_PRIORITY = {".md": 1, ".txt": 1, ".rst": 1, ".epub": 2, ".pdf": 3, ".docx": 3, ".mobi": 4, ".azw3": 4}

# ── Expert Definitions ───────────────────────────────────────────────────────
#
# Each expert: name, description, collection, tags, routing rules.
# Routing is by filename keywords + path-based category override.
# Order matters: first match wins.

EXPERTS = [
    {
        "name": "builder",
        "description": "Code, systems, engineering, math, physics, electronics, automotive, MLOps",
        "collection": "expert_builder",
        "tags": ["technical", "engineering"],
        "keywords": [
            # AI/ML/Software
            "machine learning", "deep learning", "neural network", "llm", "rag",
            "mlops", "pragmatic programmer", "refactoring", "python cookbook",
            "software", "programming", "architecture", "design patterns",
            "data-intensive", "distributed", "microservices", "devops",
            "ai engineering", "foundation model", "transformer", "gpt", "bert",
            "scikit", "keras", "tensorflow", "pytorch", "huggingface",
            "pattern recognition", "probabilistic", "bayesian", "mcmc",
            "data science", "data engineering", "database", "sql", "nosql",
            "kafka", "spark", "hadoop", "etl", "pipeline",
            "computer scientist", "biograph",  # biographies of scientists
            # Math
            "calculus", "linear algebra", "differential equation", "statistics",
            "probability", "fourier", "laplace", "eigenvalue", "matrix",
            "geometry", "euclidean", "topology", "algebra", "number theory",
            "mathematical", "mathematics", "math ", "proof",
            "complex variable", "demystified",
            # Physics
            "electromagnet", "quantum", "thermodynamic", "mechanic",
            "vibration", "shock", "wave propagation", "relativity",
            "physics", "physicist", "field analysis", "static electromagnetic",
            "matter", "energy", "direct current", "alternating current",
            # Electronics & Electrical
            "circuit", "amplifier", "oscillator", "filter design", "rf power",
            "microelectronics", "digital signal", "analog", "capacitor", "resistor",
            "power supply", "rectifier", "impedance", "schematic",
            "microwave", "radar", "synchro", "servo", "gyro",
            "test equipment", "transmission line", "antenna",
            "switching", "grounding", "dielectric", "inductor",
            "electroplat", "plating metal", "forge", "heat treatment", "steel",
            "power electronic", "power generation", "industrial power",
            # Engineering
            "handbook", "manual", "schematic", "wiring", "torque",
            "automotive", "honda", "ridgeline", "service manual", "repair",
            "restoration", "heathkit", "audio repair",
            "strain-gage", "strain gage", "instrumentation",
            "vibration transducer", "vibration pickup", "calibration",
            "isolator", "isolation system", "structural dynamic",
            "earthquake", "ground motion",
            "security project", "information security", "cybersecurity",
            # General technical
            "speaker", "audio", "stereo", "amplifier", "fm ",
            "electronics", "engineering", "technical",
            "cookbook", "bible", "complete guide", "comprehensive",
        ],
        "path_match": [
            "AI & Software", "Engineering", "Physics",
        ],
    },
    {
        "name": "body",
        "description": "Health, nutrition, anatomy, physical therapy, exercise, herbalism",
        "collection": "expert_body",
        "tags": ["health", "body"],
        "keywords": [
            "nutrition", "herbal", "supplement", "vitamin", "mineral",
            "anatomy", "physiology", "biomechanic", "fascial", "myofascial",
            "physical therapy", "rehabilitation", "recovery", "pilates",
            "exercise", "training", "fitness", "strength", "conditioning",
            "posture", "core", "stretching", "mobility",
            "brain health", "neurobic", "memory loss", "dementia",
            "smoking", "addiction recovery", "weight loss", "metabolism",
            "chinese herb", "ayurveda", "medicinal", "phytotherapy",
            "acid-base", "hydration", "tissue",
            "car maintenance", "braking", "steering", "suspension",  # physical systems
            "grow youthful", "anti-aging", "longevity", "youthful",
            "mind enhancing", "food", "drug", "nutritional",
            "encyclopedia of mind",
            "how to treat", "chinese herbs",
            "lower back pain", "chronic pain", "pain management",
            "self practice", "meditation self",
            "nlp skill", "skill building",
            "critical thinking skills",  # physical book about thinking
            "superforecasting",  # prediction skill
            "power up your mind",  # brain performance
            "memory program", "prevent memory loss",
            "the 100% brain course",
            "stop smoking", "therapy session",
            "eastern body", "western mind",  # body-mind connection
        ],
        "path_match": [
            "Human Biology", "Health",
        ],
    },
    {
        "name": "mind",
        "description": "Psychology, habits, cognition, learning, influence, memory, NLP, trauma",
        "collection": "expert_mind",
        "tags": ["psychology", "cognition"],
        "keywords": [
            "psychology", "cognitive", "behavioral", "neuroscience",
            "habit", "procrastination", "motivation", "grit", "willpower",
            "influence", "persuasion", "negotiation", "social psychology",
            "memory", "speed reading", "learning", "study skill",
            "nlp", "neuro-linguistic", "hypnosis", "hypnotic",
            "trauma", "ptsd", "emdr", "inner child",
            "addiction", "compulsive", "ocd", "anxiety", "depression",
            "personality", "temperament", "character", "introvert", "extrovert",
            "thinking fast", "kahneman", "bias", "heuristic",
            "gifted child", "drama", "aloneness", "attachment",
            "brain course", "brain alive", "dopamine",
            "creativity", "creative thinking", "mind map",
            "superforecasting", "prediction", "judgment",
            "gifts of imperfection", "vulnerability", "shame",
            "dare to lead", "courage", "leadership psychology",
            "freud", "psychoanaly", "psychopathology",
            "ways of learning", "how to learn", "study skill",
            "brain at will", "control your brain",
            "gifted child", "aloneness", "wholeness",
            "rewiring", "addicted brain", "break addiction",
            "waking the tiger", "healing trauma",
            "artist's way", "julia cameron",
            "critical thinking", "thinking skills",
            "reading body language", "lie detection", "micro expression",
        ],
        "path_match": [
            "Psychology & Cognitive", "Psychology",
        ],
    },
    {
        "name": "wisdom",
        "description": "Philosophy, ethics, meaning, systems thinking, meditation, spirituality, history of ideas",
        "collection": "expert_wisdom",
        "tags": ["philosophy", "wisdom"],
        "keywords": [
            "philosophy", "ethics", "morality", "virtue", "stoic",
            "meditation", "mindfulness", "vipassana", "buddhis", "zen",
            "spiritual", "consciousness", "awareness", "enlighten",
            "meaning", "purpose", "existential", "frankl",
            "systems thinking", "system dynamics", "meadows", "leverage",
            "black swan", "antifragile", "taleb", "nassim",
            "logic", "reasoning", "critical thinking", "argument",
            "scientific method", "philosophy of science", "kuhn", "popper",
            "plato", "aristotle", "socrates", "stoicism",
            "cosmology", "nature of reality", "metaphysics",
            "sagan", "pale blue dot", "demon haunted",
            "guns germs", "civilization", "history of science",
            "intuition pumps", "dennett", "consciousness explained",
            "structure of scientific revolutions",
            "logic of scientific discovery",
            "lobotomy", "open your mind",
            "photo reading", "whole mind",
            "life mission", "north star", "intention",
            "history of mathematics", "curious mind",
            "euclid", "element", "geometry",
            "mathematician", "physicist", "biograph",
            "tales of", "science and", "science in",
            "real science", "scientific revolution",
            "demon haunted", "candle in the dark",
            "what it means", "what it is",
            "selected myths", "cosmology",
            "christianity", "religion", "theology",
            "personality", "character", "temperament",
        ],
        "path_match": [],
    },
    {
        "name": "voice",
        "description": "Communication, conversation, public speaking, leadership, social skills",
        "collection": "expert_voice",
        "tags": ["communication", "social"],
        "keywords": [
            "conversation", "communication skill", "public speaking", "rhetoric",
            "how to win friends", "dale carnegie", "influence people",
            "charisma", "small talk", "social skill", "rapport",
            "body language", "lie detection", "micro expression",
            "negotiation", "never split the difference", "chris voss",
            "captivating conversation", "art of conversation",
            "leadership", "coaching",
            "personal magnetism", "magnetism personal", "charm",
            "nlp lie", "nlp reading body",
            "10 tips", "successful public speaking",
        ],
        "path_match": [],
    },
]

EXPERT_NAMES = {e["name"] for e in EXPERTS}

# ── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class BookCandidate:
    path: Path
    source_root: Path
    ext: str
    format_priority: int
    content_hash: str = ""
    size_bytes: int = 0
    expert: str = ""
    source_label: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class Manifest:
    candidates: list[BookCandidate] = field(default_factory=list)
    skipped_duplicates: int = 0
    skipped_junk: int = 0
    skipped_no_expert: int = 0


# ── Helpers ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("ingest")


def _content_hash(path: Path) -> str:
    h = hashlib.sha256()
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            h.update(f.read(65536))
        h.update(str(size).encode())
    except OSError:
        h.update(str(path).encode())
    return h.hexdigest()[:16]


def _clean_name(name: str) -> str:
    """Clean a filename into a readable source label."""
    name = name.replace("%20", " ").replace("%3A", ":").replace("%2C", ",")
    for suffix in ["_liber3", " (z-library.sk, 1lib.sk, z-lib.sk)", " (z-library.sk)",
                    " -- Lotus Pub_ ; North Atlantic Books", " (z-library.sk, 1lib.sk, z-lib.sk).pdf"]:
        if suffix in name:
            name = name[:name.index(suffix)]
    name = name.strip(" -_")
    return name


def _detect_chapter_group(path: Path) -> str | None:
    """Detect if a file is a chapter fragment. Returns group key or None."""
    name = path.name
    patterns = [
        (r"^(CH\d+)\.(pdf|PDF)$", "ch"),
        (r"^(Chapter\d+)\.(pdf|PDF)$", "chapter"),
        (r"^(\d{4,})\s+\d+\.(pdf|PDF)$", "num"),
        (r"^(\d{3,})\s+PDF\s+.*\.(pdf|PDF)$", "numpdf"),
        (r"^(Sprague\s+(?:TP\s+)?\d+)\s+\d+\.(pdf|PDF)$", "sprague"),
    ]
    for pattern, _ in patterns:
        m = re.match(pattern, name, re.IGNORECASE)
        if m:
            parent = path.parent.name
            return f"{parent}/{m.group(1)}"
    return None


def _route_to_expert(path: Path) -> tuple[str, list[str]]:
    """Route a book to an expert. Returns (expert_name, tags).

    Priority: keyword match (high confidence) → path+keyword (medium) → skip.
    No match = skip. We don't force books into experts.
    """
    name_lower = path.stem.lower()
    path_str = str(path).lower()

    # Negative signals — these are NOT technical even if in technical folders
    negative = [
        "meditation", "buddhis", "spiritual", "consciousness",
        "psychology", "cognitive", "trauma", "healing", "inner child",
        "conversation", "public speaking", "charisma", "body language",
        "grit", "courage", "vulnerability", "imperfection",
        "self-help", "self improvement", "personal development",
        "fiction", "novel", "story", "memoir",
        "giovanni", "baldwin", "sagan", "pale blue dot",
        "lobotomy", "creative thinking", "mind map",
        "photo reading", "speed reading", "memory",
        "hypnosis", "hypnotic", "nlp",
        "universe", "life mission", "north star", "intention",
        "dopamine", "procrastination", "motivation",
        "grow youthful", "anti-aging", "longevity",
        "encyclopedia of mind", "mind enhancing",
        "gain experience", "leveraging the universe",
    ]
    if any(neg in name_lower for neg in negative):
        # Re-route to mind/wisdom/body instead of builder
        for expert in EXPERTS:
            if expert["name"] in ("mind", "wisdom", "body", "voice"):
                for kw in expert["keywords"]:
                    if kw.lower() in name_lower:
                        return expert["name"], expert["tags"]
        # Default to mind for psychology/self-help
        if any(neg in name_lower for neg in ["psychology", "cognitive", "trauma", "healing",
                                               "grit", "courage", "vulnerability", "imperfection",
                                               "dopamine", "procrastination", "motivation",
                                               "memory", "hypnosis", "nlp", "speed reading"]):
            return "mind", ["psychology", "cognition"]
        if any(neg in name_lower for neg in ["meditation", "buddhis", "spiritual", "consciousness",
                                               "universe", "life mission", "intention", "lobotomy"]):
            return "wisdom", ["philosophy", "wisdom"]
        if any(neg in name_lower for neg in ["conversation", "public speaking", "charisma", "body language"]):
            return "voice", ["communication", "social"]
        if any(neg in name_lower for neg in ["grow youthful", "anti-aging", "longevity",
                                               "encyclopedia of mind", "mind enhancing"]):
            return "body", ["health", "body"]
        return "", []  # skip if can't categorize

    # 1. Keyword match (highest confidence)
    best_expert = ""
    best_score = 0
    for expert in EXPERTS:
        score = sum(1 for kw in expert["keywords"] if kw.lower() in name_lower)
        if score > best_score:
            best_score = score
            best_expert = expert["name"]

    if best_score >= 2:
        expert_meta = next(e for e in EXPERTS if e["name"] == best_expert)
        return best_expert, expert_meta["tags"]

    # 2. Single keyword match (medium confidence)
    if best_score == 1:
        expert_meta = next(e for e in EXPERTS if e["name"] == best_expert)
        return best_expert, expert_meta["tags"]

    # 3. Path-based match — only if we have at least one keyword signal
    # This prevents books with zero technical keywords from being routed
    # just because they're in a technical folder.
    if best_score == 0:
        return "", []  # no signal = skip

    return "", []


# ── Scanning ─────────────────────────────────────────────────────────────────

def scan_all_sources() -> list[BookCandidate]:
    """Scan all source folders for ingestible files."""
    candidates = []
    for root in SOURCES:
        if not root.exists():
            log.warning("Source not found: %s", root)
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext not in INGESTIBLE_EXTENSIONS:
                continue
            size = path.stat().st_size
            if size < MIN_FILE_SIZE_BYTES:
                continue
            parts = set(path.relative_to(root).parts)
            if parts & JUNK_DIRS:
                continue
            name_lower = path.stem.lower()
            if any(jp in name_lower for jp in JUNK_PATTERNS):
                continue

            candidates.append(BookCandidate(
                path=path, source_root=root, ext=ext,
                format_priority=FORMAT_PRIORITY.get(ext, 9),
                size_bytes=size,
            ))
    return candidates


def deduplicate(candidates: list[BookCandidate]) -> list[BookCandidate]:
    """Deduplicate by content hash, keeping best format."""
    hash_groups: dict[str, list[BookCandidate]] = {}
    for c in candidates:
        c.content_hash = _content_hash(c.path)
        hash_groups.setdefault(c.content_hash, []).append(c)

    source_priority = {"books_canonical_v2": 0, "ingestion_curated_deep_ocr": 1, "ingestion_curated_deep": 2}

    result = []
    for group in hash_groups.values():
        def sort_key(c: BookCandidate):
            sp = 2
            for name, p in source_priority.items():
                if name in str(c.source_root):
                    sp = p
                    break
            return (c.format_priority, sp, c.path.name)
        group.sort(key=sort_key)
        result.append(group[0])
    return result


def group_chapters(candidates: list[BookCandidate]) -> list[BookCandidate]:
    """Group chapter fragments. Each fragment gets the same expert + source_label."""
    standalone: list[BookCandidate] = []
    fragment_groups: dict[str, list[BookCandidate]] = {}

    for c in candidates:
        group_key = _detect_chapter_group(c.path)
        if group_key:
            fragment_groups.setdefault(group_key, []).append(c)
        else:
            standalone.append(c)

    result = list(standalone)
    for group_key, fragments in fragment_groups.items():
        parent_dir = _clean_name(fragments[0].path.parent.name)
        fragments.sort(key=lambda c: c.path.name)
        for i, frag in enumerate(fragments):
            frag._chapter_group = parent_dir
            frag._chapter_index = i
            frag._chapter_total = len(fragments)
            result.append(frag)

    if fragment_groups:
        log.info("Chapter groups: %d groups (%d files)", len(fragment_groups),
                 sum(len(g) for g in fragment_groups.values()))
    return result


def route_all(candidates: list[BookCandidate]) -> tuple[list[BookCandidate], int]:
    """Route all candidates to experts. Returns (routed, skipped_count)."""
    routed = []
    skipped = 0
    for c in candidates:
        expert, tags = _route_to_expert(c.path)
        if not expert:
            skipped += 1
            continue
        c.expert = expert
        c.tags = tags

        # Build source label
        name = _clean_name(c.path.stem)
        if hasattr(c, '_chapter_group') and c._chapter_group:
            name = f"{c._chapter_group} — Ch.{c._chapter_index + 1}/{c._chapter_total}"
        c.source_label = name

        routed.append(c)
    return routed, skipped


# ── Ingestion ────────────────────────────────────────────────────────────────

async def ingest_book(candidate: BookCandidate, dry_run: bool = True) -> dict:
    """Ingest a single book."""
    if dry_run:
        return {
            "source_label": candidate.source_label,
            "expert": candidate.expert,
            "format": candidate.ext,
            "size_mb": round(candidate.size_bytes / 1024 / 1024, 1),
            "status": "dry_run",
        }

    from gateway import knowledge

    expert_meta = next(e for e in EXPERTS if e["name"] == candidate.expert)

    try:
        result = await knowledge.ingest(
            file_path=candidate.path,
            sensitivity="low",
            source_label=candidate.source_label,
            doc_type=None,  # pipeline auto-detects
            collection=expert_meta["collection"],
            tags=candidate.tags,
            force_refresh=False,
        )
        return {
            "source_label": candidate.source_label,
            "expert": candidate.expert,
            "format": candidate.ext,
            "size_mb": round(candidate.size_bytes / 1024 / 1024, 1),
            "status": result.status,
            "chunks": result.chunks_count,
            "error": result.error_message,
        }
    except Exception as exc:
        return {
            "source_label": candidate.source_label,
            "expert": candidate.expert,
            "format": candidate.ext,
            "size_mb": round(candidate.size_bytes / 1024 / 1024, 1),
            "status": "error",
            "error": str(exc),
        }


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Ingest books into Kitty's 5-expert knowledge base")
    parser.add_argument("--execute", action="store_true", help="Actually ingest")
    parser.add_argument("--limit", type=int, default=0, help="Max books to ingest")
    parser.add_argument("--expert", type=str, default="", help="Only this expert (builder/body/mind/wisdom/voice)")
    parser.add_argument("--manifest", type=str, default="", help="Write manifest JSON")
    args = parser.parse_args()
    dry_run = not args.execute

    # 1. Scan
    log.info("Scanning sources...")
    raw = scan_all_sources()
    log.info("  Found %d ingestible files", len(raw))

    # 2. Dedup
    deduped = deduplicate(raw)
    log.info("  After dedup: %d unique (%d removed)", len(deduped), len(raw) - len(deduped))

    # 3. Group chapters
    grouped = group_chapters(deduped)

    # 4. Route to experts
    routed, skipped = route_all(grouped)
    log.info("  After routing: %d books (%d skipped — no expert match)", len(routed), skipped)

    # 5. Filter by expert
    if args.expert:
        routed = [c for c in routed if c.expert == args.expert]
        log.info("  Filtered to expert '%s': %d books", args.expert, len(routed))

    # 6. Limit
    if args.limit > 0:
        routed = routed[:args.limit]

    # 7. Expert breakdown
    expert_counts = {}
    for c in routed:
        expert_counts[c.expert] = expert_counts.get(c.expert, 0) + 1
    for name, count in sorted(expert_counts.items()):
        log.info("  %s: %d books", name, count)

    # 8. Manifest
    if args.manifest:
        manifest_data = [{
            "source_label": c.source_label,
            "expert": c.expert,
            "format": c.ext,
            "size_mb": round(c.size_bytes / 1024 / 1024, 1),
            "path": str(c.path),
            "content_hash": c.content_hash,
            "tags": c.tags,
        } for c in routed]
        Path(args.manifest).write_text(json.dumps(manifest_data, indent=2))
        log.info("Manifest: %s", args.manifest)

    # 9. Ingest
    if dry_run:
        log.info("DRY RUN — sample:")
        for c in routed[:20]:
            log.info("  [%s] %s (%.1f MB) → %s", c.ext, c.source_label, c.size_bytes / 1024 / 1024, c.expert)
        if len(routed) > 20:
            log.info("  ... and %d more", len(routed) - 20)
        log.info("Run with --execute to ingest.")
        return

    log.info("Ingesting %d books...", len(routed))
    results = []
    start = time.time()

    for i, c in enumerate(routed, 1):
        log.info("[%d/%d] %s → %s (%.1f MB)", i, len(routed), c.source_label, c.expert, c.size_bytes / 1024 / 1024)
        result = await ingest_book(c, dry_run=False)
        results.append(result)
        status = result["status"]
        if status == "success":
            log.info("  → %d chunks", result.get("chunks", 0))
        elif status == "skipped":
            log.info("  → already ingested")
        else:
            log.warning("  → %s: %s", status, result.get("error", "")[:100])

    elapsed = time.time() - start
    success = sum(1 for r in results if r["status"] == "success")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] in ("error", "failed"))

    log.info("=" * 60)
    log.info("Done in %.0fs — success=%d skipped=%d failed=%d", elapsed, success, skipped, failed)
    if failed:
        for r in results:
            if r["status"] in ("error", "failed"):
                log.warning("  FAILED: %s — %s", r["source_label"], r.get("error", "")[:80])


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
