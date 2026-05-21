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

WEBUI_URL = "http://127.0.0.1:3000"
EMAIL = os.environ.get("OWUI_EMAIL", "")
PASSWORD = os.environ.get("OWUI_PASSWORD", "")
DB_PATH = Path.home() / "kitty-services/open-webui-data/webui.db"
USER_ID = "717d741d-18ee-4bbc-aaa6-910157e54933"

# --------------------------------------------------------------------------
# KB definitions: (name, description, filename_keywords)
# --------------------------------------------------------------------------
KB_DEFS = [
    (
        "electronics",
        "Electrical engineering, circuits, RF, power electronics, electromagnetics",
        [
            "electromagnet",
            "maxwell",
            "electricity",
            "electronic",
            "circuit",
            "rf power",
            "atx",
            "power supply",
            "555",
            "oscillator",
            "op-amp",
            "opamp",
            "power electronic",
            "industrial power",
            "shock and vibration",
            "analog circuit",
            "integrated circuit",
            "transistor",
            "capacitor",
            "resistor",
            "inductor",
            "microcontroller",
            "arduino",
            "pcb",
            "signal processing",
            "filter design",
            "feedback control",
            "semiconductor",
            "diode",
            "mosfet",
            "bjt",
            "thyristor",
            "inverter",
            "converter",
            "rectifier",
            "smps",
            "switching",
            "harris",
            "fleisch",
            "student guide",
        ],
    ),
    (
        "audio repair",
        "Vintage audio, amplifier repair, Sansui, Audiokarma mods, hi-fi",
        [
            "sansui",
            "au999",
            "audiokarma",
            "audio mod",
            "tone control",
            "preamp",
            "fm tuner",
            "amplifier",
            "speaker",
            "vintage audio",
            "hi-fi",
            "hifi",
            "stereo",
            "audio power",
            "audio modification",
            "eliminating the tone",
            "audio modifications",
        ],
    ),
    (
        "automotive",
        "Vehicle service, repair, diagnostics, Honda, car maintenance",
        [
            "honda ridgeline",
            "ridgeline service",
            "vehicle diagnosis",
            "vehicle technology",
            "advanced vehicle",
            "car locksmith",
            "car maintenance",
            "car key",
            "braking component",
            "automotive",
            "auto repair",
            "obd",
            "engine repair",
            "basic tips.*car",
            "looking after your car",
        ],
    ),
    (
        "bettering myself",
        "Personal development, mindfulness, habits, psychology, self-improvement",
        [
            "4 agreements",
            "60-day recovery",
            "recovery journal",
            "public speaking",
            "creativity",
            "problem solving",
            "hypnotic",
            "hypnosis",
            "buddhism",
            "buddhist",
            "meditation",
            "organize.*life",
            "clutter",
            "mindful",
            "self-help",
            "light speed reading",
            "habits",
            "atomic habits",
            "nlp",
            "neuro-linguistic",
            "motivat",
            "personal develop",
            "biomechanics",
            "corrective program",
            "emotional intelligence",
            "resilience",
            "stoic",
            "stoicism",
            "cognitive",
        ],
    ),
    (
        "math & physics",
        "Mathematics, physics, calculus, differential equations, relativity, quantum",
        [
            "mathematics",
            "calculus",
            "algebra",
            "geometry",
            "differential equations",
            "partial differential",
            "relativity",
            "quantum",
            "physics",
            "thermodynamic",
            "brief history of math",
            "graduate school math",
            "mathematical",
            "statistics",
            "probability",
            "linear algebra",
            "abstract algebra",
            "number theory",
            "topology",
            "real analysis",
            "complex analysis",
            "vector analysis",
            "tensors",
            "fluid",
            "mechanics",
        ],
    ),
    (
        "ai & programming",
        "Machine learning, AI, LLMs, software engineering, Python, data science",
        [
            "machine learning",
            "ai engineering",
            "neural network",
            "deep learning",
            "agentic",
            "foundation model",
            "llm",
            "transformer",
            "rag",
            "langchain",
            "hugging face",
            "mlops",
            "probabilistic ml",
            "designing ml",
            "ml machine",
            "python cookbook",
            "programming",
            "software engineering",
            "data science",
            "mastering llm",
            "mastering large language",
        ],
    ),
    (
        "herbal & natural",
        "Herbalism, medicinal plants, ethnopharmacology, botanical medicine",
        [
            "herbal",
            "medicinal plant",
            "herbalism",
            "pharmacognosy",
            "ethnopharmacology",
            "botanical",
            "natural remedies",
            "phytochem",
            "adaptogens",
            "encyclopedia of herbal",
            "chinese herbal",
            "herbal tea",
            "psychopharmacology of herbal",
            "indian medicinal",
        ],
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
    r = requests.post(
        f"{WEBUI_URL}/api/v1/knowledge/{kb_id}/file/add",
        headers={"Authorization": f"Bearer {token}"},
        json={"file_id": file_id},
        timeout=120,
    )
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
