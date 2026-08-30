import os
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

BOOKS_DIR = Path("/Volumes/DATA/books")
INGESTION_DIR = Path("/Volumes/DATA/books/ingestion_curated")

CLEANUP_PATTERNS = [
    r"_liber\d+",
    r"\(z-library\.sk, 1lib\.sk, z-lib\.sk\)",
    r"\(z-lib\.org\)",
    r"-- Anna’s Archive",
    r"\(Z-Library\)",
    r"\(z-library\.sk\)",
    r"\(1lib\.sk\)",
    r"\(z-lib\.sk\)",
    r"\{.*\}",
    r"\(.*(19|20)\d{2}.*\)",
]

# Mapping of keywords to categories
CATEGORY_MAP = {
    "Engineering & Physical Systems": [
        "electronics", "circuit", "automotive", "honda", "repair", "service manual",
        "engine", "mechanic", "electrical", "soldering", "power supply", "audio repair",
        "sansui", "amplifier", "hi-fi", "electromagnetic", "vibration", "handbook",
        "technician", "radar", "microwave", "propagation", "direct current",
        "alternating current", "synchro", "servos", "equipment", "classical mechanics",
        "calculus", "differential equations", "physics", "quantum", "relativity",
        "einstein", "feynman", "hawking", "mathematics", "algebra", "geometry",
        "statistics", "probability", "fluid", "thermodynamic", "mechanics",
        "signal processing", "semiconductor", "mosfet", "transistor", "op amp",
        "integrated circuit", "pcb", "arduino", "microcontroller"
    ],
    "AI & Software Craftsmanship": [
        "ai", "machine learning", "llm", "python", "programming", "software",
        "refactoring", "mlops", "transformer", "rag", "code", "cookbook",
        "data intensive", "pragmatic programmer", "designing ml", "langchain",
        "hugging face", "neural network", "deep learning", "agentic",
        "foundation model", "computer scientist"
    ],
    "Human Biology & Movement": [
        "health", "anatomy", "myofascial", "biomechanics", "exercise", "strength",
        "fascia", "herbal", "medicinal", "pharmacognosy", "ayurveda", "nutrition",
        "sleep", "dopamine", "human performance", "gymnastic", "supple leopard",
        "warrior", "recovery", "natural movement", "isometric", "posture",
        "back pain", "body speaks", "reiki", "medicinal plant", "herbalism",
        "pharmacopoeia", "vitamins", "minerals", "natto", "supplements"
    ],
    "Psychology & Cognitive Science": [
        "psychology", "trauma", "memory", "mind", "self-help", "habits",
        "depression", "personality", "therapy", "nlp", "meditation",
        "creativity", "brain", "neurobic", "limitless", "kwik", "courage to be disliked",
        "gifted child", "gifts of imperfection", "artist's way", "thinking fast and slow",
        "lost connections", "influence", "persuasion", "man's search for meaning",
        "stoic", "stoicism", "emotional intelligence", "resilience", "cognitive",
        "inner child", "hypnosis", "hypnotic"
    ],
    "Systems Thinking & Strategic Intelligence": [
        "antifragile", "black swan", "thinking in systems", "decision",
        "superforecasting", "logic", "critical thinking", "strategy", "complexity",
        "intuition pumps", "chaos", "game theory", "systemic"
    ],
    "Learning & Communication": [
        "learning", "speed reading", "voice", "speech", "public speaking",
        "communication", "read a book", "win friends", "influence people",
        "speak with distinction", "charisma", "conversation", "language",
        "evelyn wood", "memory program"
    ]
}

def clean_name(name: str) -> str:
    name = unquote(name)
    base = Path(name).stem
    ext = Path(name).suffix

    new_name = base
    for pattern in CLEANUP_PATTERNS:
        new_name = re.sub(pattern, "", new_name, flags=re.IGNORECASE)

    new_name = new_name.replace("_", " ").replace("-", " ").strip()
    new_name = re.sub(r"\s+", " ", new_name)
    new_name = new_name.strip(" -.")

    return f"{new_name}{ext}"

def is_corrupted(path: Path) -> bool:
    if path.stat().st_size < 100:  # Too small to be a book
        return True
    try:
        with open(path, "rb") as f:
            f.read(1024)
        return False
    except (OSError,):
        # Treat unreadable / permission-denied files as corrupted so the
        # curation pass skips them. KeyboardInterrupt / SystemExit still
        # propagate so the operator can break out.
        return True

def classify(filename: str) -> str:
    fl = filename.lower()
    for cat, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in fl:
                return cat
    return "Miscellaneous"

def main():
    if not INGESTION_DIR.exists():
        INGESTION_DIR.mkdir(parents=True)

    for cat in CATEGORY_MAP.keys():
        (INGESTION_DIR / cat).mkdir(exist_ok=True)
    (INGESTION_DIR / "Miscellaneous").mkdir(exist_ok=True)

    processed_files = set()

    # We'll walk the BOOKS_DIR but avoid the INGESTION_DIR itself
    for root, dirs, filenames in os.walk(BOOKS_DIR):
        if "ingestion_curated" in root:
            continue

        for f in filenames:
            if f.startswith("."): continue
            old_path = Path(root) / f

            if is_corrupted(old_path):
                print(f"SKIP (corrupted/tiny): {f}")
                continue

            new_f = clean_name(f)
            category = classify(new_f)

            # For curation, we'll only take the most "relevant" ones
            # For now, let's just copy and rename everything to the curated folder
            # but we can filter later.

            dest_path = INGESTION_DIR / category / new_f

            # Avoid duplicates by name in the curated folder
            if new_f in processed_files:
                # If it's a duplicate, maybe compare size?
                if dest_path.exists() and old_path.stat().st_size > dest_path.stat().st_size:
                    shutil.copy2(old_path, dest_path)
                continue

            print(f"CURATE: {f} -> {category}/{new_f}")
            shutil.copy2(old_path, dest_path)
            processed_files.add(new_f)

if __name__ == "__main__":
    main()
