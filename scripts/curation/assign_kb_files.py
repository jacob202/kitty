#!/usr/bin/env python3
"""Categorize uploaded Open WebUI files and assign them to knowledge bases.

Creates missing KBs, then POSTs each file to the correct KB (which triggers
embedding into ChromaDB). Runs in parallel batches for speed.

Usage:
    python scripts/assign_kb_files.py
    python scripts/assign_kb_files.py --dry-run
    python scripts/assign_kb_files.py --workers 4
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

WEBUI_URL = os.environ.get("WEBUI_URL", "http://127.0.0.1:3001")
EMAIL = os.environ.get("OWUI_EMAIL", "")
PASSWORD = os.environ.get("OWUI_PASSWORD", "")
DB_PATH = Path.home() / "kitty-services/open-webui-data/webui.db"
USER_ID = "717d741d-18ee-4bbc-aaa6-910157e54933"

# --------------------------------------------------------------------------
# KB definitions: (name, description, filename_keywords)
# --------------------------------------------------------------------------
KB_DEFS = [
    (
        "machine learning",
        "AI, neural networks, deep learning, probabilistic ML, algorithms",
        ["machine learning", "neural network", "deep learning", "probabilistic ml", "ai engineering", "computer scientist", "algorithm", "data science", "pattern recognition"],
    ),
    (
        "programming & arch",
        "Software engineering, refactoring, Python, clean code, architecture",
        ["python", "software engineering", "refactoring", "pragmatic programmer", "clean code", "design patterns", "modular", "cookbook", "git", "bash", "linux", "coding", "javascript", "developer"],
    ),
    (
        "llms & rag",
        "Large Language Models, RAG, Transformers, LangChain, agentic workflows",
        ["llm", "transformer", "rag", "langchain", "hugging face", "foundation model", "prompt engineering", "agentic", "openai", "claude"],
    ),
    (
        "audio repair",
        "Vintage audio, amplifier repair, Sansui, Audiokarma mods, hi-fi, tubes",
        ["sansui", "amplifier", "hifi", "preamp", "tuner", "audiokarma", "valve", "tube", "vinyl", "turntable", "audio power", "small signal audio", "speaker", "audio repair", "hi-fi", "audio handbook", "audio electronics"],
    ),
    (
        "electronics",
        "Circuits, PCB, semiconductors, SMPS, power supplies, components",
        ["circuit", "pcb", "semiconductor", "transistor", "mosfet", "diode", "smps", "power supply", "relay", "inductor", "capacitor", "resistor", "oscillator", "op-amp", "integrated circuit", "electronics", "multimeter", "oscilloscope", "soldering"],
    ),
    (
        "automotive",
        "Vehicle service, repair, diagnostics, Honda Ridgeline, maintenance",
        ["honda", "ridgeline", "automotive", "car repair", "obd", "engine", "vehicle", "mechanic", "braking", "maintenance", "service manual", "alternator", "suspension", "steering"],
    ),
    (
        "math & physics",
        "Mathematics, physics, calculus, relativity, quantum mechanics, probability",
        ["calculus", "physics", "relativity", "quantum", "mathematics", "feynman", "hawking", "algebra", "geometry", "differential", "statistics", "probability", "electromagnetic", "maxwell", "wave propagation"],
    ),
    (
        "nutrition & herbalism",
        "Vitamins, nutrition, supplements, medicinal plants, Ayurveda, botany",
        ["vitamin", "mineral", "nutrition", "natto", "supplements", "herb", "medicinal", "pharmacognosy", "ayurveda", "botanical", "tea", "plant", "herbalism", "pharmacopoeia", "tincture"],
    ),
    (
        "anatomy & biomechanics",
        "Fascia, anatomy trains, structural balance, physiology, posture",
        ["anatomy", "myofascial", "fascia", "biomechanics", "posture", "muscle", "skeleton", "physiology", "structural balance", "anatomy trains", "meridian"],
    ),
    (
        "physical therapy & recovery",
        "Injury rehab, mobility, Supple Leopard, exercise conditioning",
        ["recovery", "supple leopard", "stretch", "therapy", "strength", "exercise", "injury", "mobility", "conditioning", "rehab", "back pain", "body speaks", "pilates", "yoga"],
    ),
    (
        "clinical & trauma",
        "IFS, psychology, trauma-informed care, CBT, mental health, addiction",
        ["trauma", "depression", "ifs", "inner child", "clinical", "psychology", "anxiety", "cbt", "mental health", "sarno", "healing trauma", "addiction", "recovery skills"],
    ),
    (
        "habits & performance",
        "Memory, brain optimization, deep work, limitless, productivity",
        ["habits", "memory", "brain", "focus", "deep work", "limitless", "kwik", "neuro", "cognitive", "learning", "productivity", "mindmap", "speed reading", "rapid learning"],
    ),
    (
        "philosophy & spirituality",
        "Stoicism, Buddhism, meaning of life, meditation, Zen",
        ["stoic", "buddha", "philosophy", "meaning of life", "meditation", "reiki", "spiritual", "zen", "existence", "socrates", "plato", "aristotle", "freud"],
    ),
]

# Files not matching any specific KB go here
FALLBACK_KB = (
    "general reference",
    "Uncategorized reference books, manuals, and documents",
)


def classify(filename: str) -> str:
    fl = filename.lower()
    for kb_name, _, keywords in KB_DEFS:
        for kw in keywords:
            if re.search(kw, fl):
                return kb_name
    return FALLBACK_KB[0]


def get_token() -> str:
    if not EMAIL or not PASSWORD:
        raise SystemExit("Set OWUI_EMAIL and OWUI_PASSWORD before running this script.")
    r = requests.post(
        f"{WEBUI_URL}/api/v1/auths/signin",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def get_existing_kbs(token: str) -> dict[str, str]:
    r = requests.get(
        f"{WEBUI_URL}/api/v1/knowledge/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    items = data["items"] if isinstance(data, dict) else data
    return {kb["name"]: kb["id"] for kb in items}


def create_kb(token: str, name: str, description: str) -> str:
    r = requests.post(
        f"{WEBUI_URL}/api/v1/knowledge/create",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "description": description, "data": {}},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["id"]


def add_file_to_kb(token: str, kb_id: str, file_id: str) -> bool:
    try:
        r = requests.post(
            f"{WEBUI_URL}/api/v1/knowledge/{kb_id}/file/add",
            headers={"Authorization": f"Bearer {token}"},
            json={"file_id": file_id},
            timeout=300,
        )
    except requests.exceptions.ReadTimeout:
        # Open WebUI may still finish processing in the background; treat as ok.
        print(f"  WARN timeout on {file_id} — skipping (WebUI may still embed it)", file=sys.stderr)
        return True
    if r.status_code == 200:
        return True
    if r.status_code == 400 and "already" in r.text.lower():
        return True  # already linked
    print(f"  WARN {r.status_code}: {r.text[:80]}", file=sys.stderr)
    return False


def get_files_from_db() -> list[tuple[str, str]]:
    """Return [(file_id, filename), ...] for all files not yet in any KB."""
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("""
        SELECT f.id, f.filename
        FROM file f
        WHERE f.id NOT IN (SELECT file_id FROM knowledge_file)
        ORDER BY f.filename
        """).fetchall()
    conn.close()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--skip-unlinked-check",
        action="store_true",
        help="Process ALL files, not just unlinked ones",
    )
    args = parser.parse_args()

    print("Authenticating...")
    token = get_token()

    print("Fetching existing knowledge bases...")
    kb_map = get_existing_kbs(token)
    print(f"  Found: {list(kb_map.keys())}")

    # Ensure all target KBs exist
    all_kb_defs = list(KB_DEFS) + [(*FALLBACK_KB, [])]
    for kb_name, kb_desc, _ in all_kb_defs:
        if kb_name not in kb_map:
            if args.dry_run:
                print(f"  [dry-run] Would create KB: {kb_name}")
            else:
                kb_id = create_kb(token, kb_name, kb_desc)
                kb_map[kb_name] = kb_id
                print(f"  Created KB: {kb_name} ({kb_id})")
        else:
            print(f"  KB exists: {kb_name} ({kb_map[kb_name]})")

    # Get unlinked files
    if args.skip_unlinked_check:
        conn = sqlite3.connect(str(DB_PATH))
        files = conn.execute(
            "SELECT id, filename FROM file ORDER BY filename"
        ).fetchall()
        conn.close()
    else:
        files = get_files_from_db()

    print(f"\n{len(files)} files to process")

    # Classify
    by_kb: dict[str, list[str]] = {kb_name: [] for kb_name, *_ in all_kb_defs}
    by_kb[FALLBACK_KB[0]] = []
    for file_id, filename in files:
        kb = classify(filename)
        by_kb[kb].append(file_id)

    for kb_name, ids in sorted(by_kb.items(), key=lambda x: -len(x[1])):
        print(f"  {kb_name}: {len(ids)} files")

    if args.dry_run:
        print("\n[dry-run] Done — no changes made.")
        return

    # Add files to KBs in parallel
    total = len(files)
    done = 0
    errors = 0

    for kb_name, file_ids in by_kb.items():
        if not file_ids:
            continue
        kb_id = kb_map[kb_name]
        print(f"\nAdding {len(file_ids)} files to '{kb_name}' ({kb_id[:8]})...")

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {
                ex.submit(add_file_to_kb, token, kb_id, fid): fid for fid in file_ids
            }
            for fut in as_completed(futs):
                done += 1
                ok = fut.result()
                if not ok:
                    errors += 1
                if done % 50 == 0 or done == total:
                    print(f"  Progress: {done}/{total} (errors: {errors})")

    print(f"\nDone. {done} files processed, {errors} errors.")


if __name__ == "__main__":
    main()
