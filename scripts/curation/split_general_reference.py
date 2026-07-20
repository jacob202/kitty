#!/usr/bin/env python3
"""Split the 'general reference' KB into focused knowledge bases.

Reads filenames from the DB, classifies them by pattern matching,
creates new KBs as needed, and moves files via the Open WebUI API.
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)
# Idempotent basicConfig: do not overwrite if the caller already
# wired logs (e.g. a future pytest or --log-level invocation).
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

DB_PATH = Path.home() / "kitty-services/open-webui-data/webui.db"
WEBUI_URL = "http://127.0.0.1:3001"
EMAIL = "jacobbrizinski@gmail.com"
PASSWORD = "1234"

GENERAL_REF_ID = "515d85ec-2b2a-4282-b2a7-2819104fe971"

NEW_KBS = [
    ("health & fitness", "Anatomy, exercise, physiotherapy, nutrition, bodywork, recovery"),
    ("mind & psychology", "Memory, learning, psychology, self-help, trauma, brain health, charisma"),
    ("science & philosophy", "Philosophy of science, history of science, epistemology, scientific method"),
    ("spiritual & esoteric", "Reiki, meditation, spiritual healing, metaphysics, energy work"),
    ("writing & communication", "Conversation skills, public speaking, writing, speed reading, communication"),
]

# Pattern -> KB name mapping (checked in order, first match wins)
CLASSIFIERS = [
    # health & fitness
    ("health & fitness", [
        "anatomy", "physiology", "exercise", "gymnastic", "bodyweight",
        "myofascial", "fascial", "stretch", "muscle", "posture", "core",
        "pilates", "training", "workout", "nutrition", "supplement",
        "vitamin", "mineral", "healing back pain", "supple leopard",
        "human performance", "recovery", "strength", "power methods",
        "therapeutic modalities", "soft tissue", "massage", "hair loss",
        "prostate", "natto", "ayurvedic", "ayurveda", "herbal",
        "saw palmetto", "brain alive", "neurobic",
        "anatomy trains", "fascial stretch", "myofascial release",
        "overcoming gravity", "optimal muscle", "total body",
        "mens health", "jerry shapiro", "hair",
        "david niven miller", "grow youthful",
        "evan brand", "nootropics",
        "treat yourself with chinese herbs",
        "complete human performance",
        "exercise technique",
        "treating non-specific chronic lower back",
        "theory and application of modern strength",
        "theory and application of modern power",
        "isometric", "tegener",
        "building the gymnastic",
        "book1_complete_human",
        "book2_exercise",
        "guyton", "human anatomy", "knk", "knk.repaired",
        "wade", "total body workbook",
        "therapeutic modalities.*injuries", "denegar",
        "touche", "pilates method",
        "gregory johnson", "soft-tissue",
        "chaitow", "muscle energy",
        "duncan", "myofascial release",
        "frederick", "fascial stretch therapy",
        "myers", "anatomy trains",
        "starrett", "supple leopard",
        "sarno", "healing back pain",
        "optimal muscle training",
        "kinakinx",
        "posture and core", "grisaffi",
        "isometric power",
        "training secrets", "gironda",
        "ultimate training", "enamait",
        "ultimate nutrition",
        "mens health.*workbook",
    ]),
    # mind & psychology
    ("mind & psychology", [
        "memory", "learning", "psychology", "persuasion", "influence",
        "charisma", "self-help", "trauma", "brain", "mind", "thinking",
        "hypnot", "addict", "depression", "grit", "dare to lead",
        "deep work", "limitless", "super-power memory",
        "speed reading", "speed memory", "alpha-netics",
        "mind map", "photo reading", "use your memory",
        "develop a perfect memory", "mind powers",
        "maximize your brainpower", "keep your brain alive",
        "rewiring the addicted brain",
        "drama of the gifted child",
        "healing your aloneness",
        "no bad parts", "richard schwartz",
        "running on empty", "jonice webb",
        "waking the tiger", "peter levine",
        "trauma and memory", "bessel",
        "sarno", "healing back pain",
        "mind-body", "inner child",
        "influence.*cialdini", "never split the difference",
        "how to make people like you",
        "effective communication skills",
        "how to influence people",
        "body language", "read others",
        "dare to lead", "brene brown",
        "gifts of imperfection",
        "driven to distraction",
        "man.*search.*meaning", "frankl",
        "eastern body western mind",
        "intuition pumps", "dennett",
        "thinking fast and slow", "kahneman",
        "black swan", "taleb",
        "superforecasting", "tetlock",
        "how to read a book", "adler",
        "artist.*way", "julia cameron",
        "heal yourself with writing",
        "doidge", "brain that changes itself",
        "lost connections", "hari",
        "matt kahn", "universe always has a plan",
        "gabrielle bernstein", "universe has your back",
        "steve madison", "universe is calling",
        "eric butterworth",
        "michael samuels", "just ask the universe",
        "mary anne radmacher", "live with intention",
        "dean rickles", "life is short",
        "naomi stephan", "finding your life mission",
        "martha beck", "north star",
        "terry cole-whittaker", "what you think of me",
        "harry carpenter", "genie within",
        "adam", "intention heals",
        "stanley keleman", "your body speaks",
        "anodea judith", "eastern body",
        "inayat khan", "personality",
        "pieter middelkoop", "wise old man",
        "simon jacobson", "meaningful life",
        "viktor frankl", "man.*search",
        "johann hari", "lost connections",
        "edward hallowell", "driven to distraction",
        "ratey",
        "cal newport", "deep work",
        "robert cialdini", "influence",
        "chris voss", "never split",
        "angela duckworth", "grit",
        "brene brown", "dare to lead",
        "jim kwik", "limitless",
        "norman doidge", "brain",
        "peter levine", "waking the tiger",
        "bessel van der kolk", "trauma",
        "richard schwartz", "no bad parts",
        "jonice webb", "running on empty",
        "julia cameron", "artist",
        "catherine ann jones", "heal yourself with writing",
        "erika chopich", "healing your aloneness",
        "margaret paul",
        "lorraine flaherty", "past life",
        "thomas myers", "anatomy trains",
        "ann frederick", "fascial stretch",
        "ruth duncan", "myofascial release",
        "peter levine", "trauma and memory",
        "erwan le corre", "natural movement",
        "ronald bazar", "prostate massage",
        "daniel erichsen", "natto",
        "pressman", "vitamins",
        "hopeking", "esoteric healing",
        "penczak", "reiki",
        "alan hopking",
    ]),
    # science & philosophy
    ("science & philosophy", [
        "philosophy of science", "scientific revolution", "epistemology",
        "socrates", "plato", "aristotle", "euclid", "geometry",
        "feynman", "sagan", "cosmos", "pale blue dot", "demon-haunted",
        "structure of scientific", "kuhn", "popper", "logic of scientific",
        "history of science", "science and technology",
        "science and society", "science in the ancient",
        "science in the contemporary", "science reflects reality",
        "possibility of knowledge", "cassam",
        "knowledge and its limits", "williams",
        "studying for science",
        "fabulous science", "waller",
        "lost discoveries", "teresi",
        "laws of plato", "plato.*cosmology",
        "socrates by voltaire",
        "hemlock cup",
        "xenophon.*socrates",
        "charmides", "temperance",
        "lysis", "friendship",
        "statesman", "symposium",
        "republic", "penal code",
        "daimonion",
        "bryson", "short history",
        "guns.*germs", "diamond",
        "meaning of it all", "perfectly reasonable",
        "surely you.*joking", "curious character",
        "feynman.*rainbow",
        "wonders of the universe", "cox",
        "why does.*m.*c", "forshaw",
        "complexity and chaos",
        "michael starbird", "calculus",
        "einstein", "relativity",
        "dirac", "quantum mechanics",
        "schrodinger", "schrodingers",
        "proofs from the book",
        "greenberg", "euclidean",
        "heath.*euclid",
        "mcmahon.*complex variables",
        "sidi.*extrapolation",
        "nicholson.*linear algebra",
        "petry.*math",
        "1397_pdf",
        "applebaum", "scientific revolution",
        "falcon.*aristotle",
        "darrigol", "electrodynamics",
        "gindikin", "tales of mathematicians",
        "pickover", "archimedes",
        "taylor.*hidden unity",
        "kelvin.*flood",
        "christianson.*isaac newton",
        "pais.*dirac",
        "macdougall", "nature.*clocks",
        "haven.*science discoveries",
        "mostert", "edison to ipod",
        "sherman.*science and society",
        "mcclellan.*science and technology",
        "science in popular culture",
        "van riper", "popular culture",
        "gillies", "philosophy of science",
        "boyd.*philosophy of science",
        "kuipers", "general philosophy",
        "ladyman", "understanding philosophy",
        "sellars", "science, perception",
        "brown.*smoke and mirrors",
        "ziman", "real science",
        "white.*studying for science",
        "pritchard", "ways of learning",
        "korzybski", "science and sanity",
        "gentner", "language in mind",
        "cambridge dictionary of scientists",
        "hender.*mathematicians",
        "leiter.*physicists",
        "mcelroy.*mathematicians",
        "todd.*scientists",
        "timeline of science",
        "ochoa",
        "quirky sides", "topper",
        "survival skills.*scientists", "rosei",
    ]),
    # spiritual & esoteric
    ("spiritual & esoteric", [
        "reiki", "meditation", "spiritual", "metaphysics", "energy",
        "esoteric healing", "magick of reiki", "penczak",
        "intention heals", "genie within",
        "universe.*calling", "butterworth",
        "universe.*back", "bernstein",
        "toward a meaningful life", "jacobson",
        "just ask the universe", "samuels",
        "life is short", "rickles",
        "live with intention", "radmacher",
        "finding your life mission", "stephan",
        "finding your own north star", "beck",
        "personality.*inayat khan",
        "what you think of me", "cole-whittaker",
        "psilocybin", "mushroom",
        "harvard psychedelic club",
        "methaqualone",
        "mind-lines", "transform minds",
        "tap the incredible secret powers",
        "how to control your brain at will",
        "do-it-yourself lobotomy",
        "100.*brain course",
        "reuniting the two selves",
        "hypnotism.*spells",
        "art of hypnotism",
        "success secrets.*hypnotism",
        "coiled serpent",
        "eros unveiled",
        "magick",
        "reiki.*manual", "reikiii", "reikii", "reiki",
        "alan hopking",
        "encyclopedia of mind enhancing",
    ]),
    # writing & communication
    ("writing & communication", [
        "conversation", "charisma", "speaking", "communication",
        "public speaking", "speech", "voice", "right to speak",
        "rodenburg", "skinner.*distinction",
        "is your voice telling", "boone.*voice",
        "set your voice free", "roger love",
        "speed reading workbook", "evelyn wood",
        "rapid reading", "skousen",
        "creative training idea book",
        "smart thinking skills",
        "critical understanding",
        "small talk", "dating", "flirting",
        "art of captivating conversation",
        "master of effective",
        "king.*dale.*influence",
        "lowndes", "carnegie",
        "blyth", "art of conversation",
        "haunts", "art of conversation",
        "vincent ng", "small talk",
        "patrick king", "captivating",
        "stephen haunts",
        "catherine blyth",
        "lucas", "power up your mind",
    ]),
    # electronics (existing KB)
    ("electronics", [
        "op amp", "operational amplifier",
        "cmos", "ic layout",
        "soldering", "desoldering",
        "welding",
        "power supply", "buck and boost",
        "regulator", "voltage",
        "electrical engineer",
        "electrical science",
        "doe.*electrical",
        "sensor", "transducer",
        "radio-frequency", "rf",
        "smt", "surface mount",
        "dielectric",
        "negative resistance",
        "noise", "vibration",
        "mechanical vibration",
        "fundamentals of mechanical vibration",
        "vibration isolation",
        "common noise and vibration",
        "basic relays",
        "difference between.*latch.*flip",
        "triac",
        "power tube life",
        "ultralinear", "ot.*tap",
        "output stage",
        "fusion", "fusible",
        "f-2723", "f-2720", "f-2721", "f-2722",
        "82.*ohm", "150.*ohm",
        "wiring guide",
        "building tips and tricks",
        "checking caps",
        "current mirrors",
        "gain experience",
        "grounding",
        "electroplating",
        "signal and power integrity",
        "mixed signal",
        "dsp design",
        "hpH.*dielectric",
        "audio.*design", "douglas self",
        "audio expert",
        "small signal audio",
        "analog circuits cookbook",
        "art and science of analog circuit",
        "analog circuit design",
        "practical electrical engineering",
        "practical radio-frequency",
        "handbook of plastics",
        "forge practice", "heat treatment",
        "steel",
        "esab welding",
        "us army.*welding",
        "plating metals",
        "cabinet handbook",
        "assoc.pdf",
        "suck less",
        "tubes for dummies",
        "aa 151", "tommcnally",
        "sam.*magical.*151",
        "anti-skate",
        "audio handbook",
        "building tips",
        "note.md", "note.1.md", "untitled note",
        "techniques to maximize",
        "in stock form",
        "there are 4 fusibles",
        "wiring guide",
        "terrell.*op amp",
        "warne.*handbook",
        "sinclair.*smt",
        "strauss.*soldering",
        "hickman.*radio-frequency",
        "guide to electric power", "pansini",
        "vogel.*practical organic",
        "electroplating.*plating",
        "effect of negative resistance",
        "hpH.*dielectric absorption",
        "cmos integrated adc",
        "cmos ic layout",
        "signal and power integrity.*bogatin",
        "mixed signal and dsp",
        "mpeg.7.audio",
        "audio.1.md", "audio.md",
    ]),
    # ai & programming (existing KB)
    ("ai & programming", [
        "machine learning", "machine-learning",
        "bishop.*pattern recognition",
        "hands-on.*scikit", "aurelien geron",
        "refactoring", "martin fowler",
        "data-intensive applications", "kleppmann",
        "data mining",
        "harmelen.*knowledge representation",
        "building machine learning",
        "jennex.*knowledge management",
        "claude code context cleanup",
    ]),
    # math & physics (existing KB)
    ("math & physics", [
        "calculus", "differential", "derivative",
        "eigenvalue", "eigenvector",
        "trig", "trigonometry",
        "math.*110", "coursebook",
        "physics", "mechanics",
        "relativity", "einstein",
        "quantum", "dirac",
        "euclid", "geometry",
        "vibration", "oscillation",
        "fourier transform",
        "complex variables",
        "linear algebra",
        "proofs from the book",
        "extrapolation methods",
    ]),
    # automotive (existing KB)
    ("automotive", [
        "gas mileage", "fuel economy",
        "internal combustion engine", "heywood",
        "car window", "sparkling car",
        "obd2",
        "bmw.*p1632",
        "honda.*ridgeline",
        "improve gas mileage",
        "modern technology.*mileage",
    ]),
]


def login() -> str:
    r = requests.post(
        f"{WEBUI_URL}/api/v1/auths/signin",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def get_kb_map(token: str) -> dict[str, str]:
    """name -> id"""
    r = requests.get(
        f"{WEBUI_URL}/api/v1/knowledge/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    items = data["items"] if isinstance(data, dict) else data
    return {item["name"]: item["id"] for item in items}


def create_kb(token: str, name: str, description: str) -> str:
    r = requests.post(
        f"{WEBUI_URL}/api/v1/knowledge/create",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "description": description, "data": {}},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["id"]


def add_file_to_kb(token: str, kb_id: str, file_id: str) -> bool:
    r = requests.post(
        f"{WEBUI_URL}/api/v1/knowledge/{kb_id}/file/add",
        headers={"Authorization": f"Bearer {token}"},
        json={"file_id": file_id},
        timeout=60,
    )
    if r.ok:
        return True
    text = r.text.lower()
    if "duplicate" in text or "already" in text:
        return True
    return False


def remove_file_from_kb(token: str, kb_id: str, file_id: str) -> bool:
    r = requests.post(
        f"{WEBUI_URL}/api/v1/knowledge/{kb_id}/file/remove",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"file_id": file_id},
        timeout=30,
    )
    return r.ok


def get_files_in_kb_from_db(kb_id: str) -> list[tuple[str, str]]:
    """Returns list of (file_id, filename) for files in the given KB."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT kf.file_id, f.filename FROM knowledge_file kf "
            "JOIN file f ON kf.file_id = f.id "
            "WHERE kf.knowledge_id=?",
            (kb_id,),
        ).fetchall()
    finally:
        conn.close()
    return rows


def classify(filename: str) -> str | None:
    """Classify a filename into a KB name. Returns None for 'keep in general reference'."""
    lower = filename.lower()
    for kb_name, patterns in CLASSIFIERS:
        for pattern in patterns:
            if re.search(pattern, lower):
                # Skip false positives
                if kb_name == "ai & programming" and "gymnastic" in lower:
                    continue
                return kb_name
    return None  # stays in general reference


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pause", type=float, default=0.1)
    args = parser.parse_args()

    logger.info("Authenticating...")
    token = login()

    kb_map = get_kb_map(token)
    logger.info(f"Existing KBs: {list(kb_map.keys())}")

    # Create new KBs if needed
    for name, desc in NEW_KBS:
        if name not in kb_map:
            if args.dry_run:
                logger.info(f"[dry-run] would create KB: {name}")
                continue
            kb_map[name] = create_kb(token, name, desc)
            logger.info(f"created KB: {name}")

    # Get all files in general reference
    gen_files = get_files_in_kb_from_db(GENERAL_REF_ID)
    logger.info(f"\nFiles in general reference: {len(gen_files)}")

    # Classify each file
    moves: dict[str, list[tuple[str, str]]] = {}  # kb_name -> [(file_id, filename)]
    keep: list[tuple[str, str]] = []

    for file_id, filename in gen_files:
        kb = classify(filename)
        if kb and kb in kb_map:
            moves.setdefault(kb, []).append((file_id, filename))
        else:
            keep.append((file_id, filename))

    logger.info("\nClassification summary:")
    logger.info(f"  Keep in general reference: {len(keep)}")
    for kb_name, files in sorted(moves.items()):
        logger.info(f"  Move to '{kb_name}': {len(files)}")

    if args.dry_run:
        logger.info("\n[dry-run] Done.")
        return 0

    # Execute moves
    total = sum(len(v) for v in moves.values())
    done = 0
    errors = 0

    for kb_name, files in sorted(moves.items()):
        kb_id = kb_map[kb_name]
        logger.info(f"\nMoving {len(files)} files to '{kb_name}'...")
        for file_id, filename in files:
            done += 1
            # Add to new KB
            ok = add_file_to_kb(token, kb_id, file_id)
            if ok:
                # Remove from general reference
                remove_file_from_kb(token, GENERAL_REF_ID, file_id)
            else:
                errors += 1
                logger.error(f"  FAIL: {filename}")
            if args.pause:
                time.sleep(args.pause)
            if done % 50 == 0:
                logger.error(f"  {done}/{total} done, {errors} errors")

    logger.error(f"\nDone. Moved {done - errors}/{total}, {errors} errors")
    logger.info(f"Remaining in general reference: {len(keep)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
