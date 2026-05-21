import os
import shutil
import re
from pathlib import Path
from pypdf import PdfReader

# Paths
SOURCE_ROOT = Path("/Volumes/DATA/books_dedup_backup/ingestion_curated")
TARGET_ROOT = Path("/Volumes/DATA/books/ingestion_curated_deep")

# Refined Categories Structure
STRUCTURE = {
    "AI & Software": {
        "Machine Learning": ["machine learning", "neural network", "deep learning", "probabilistic ml", "ai engineering", "computer scientist", "algorithm", "data science", "pattern recognition"],
        "Programming & Arch": ["python", "software engineering", "refactoring", "pragmatic programmer", "clean code", "design patterns", "modular", "cookbook", "git", "bash", "linux", "coding", "javascript", "developer"],
        "LLMs & RAG": ["llm", "transformer", "rag", "langchain", "hugging face", "foundation model", "prompt engineering", "agentic", "openai", "claude"]
    },
    "Engineering": {
        "Audio Repair": ["sansui", "amplifier", "hifi", "preamp", "tuner", "audiokarma", "valve", "tube", "vinyl", "turntable", "audio power", "small signal audio", "speaker", "audio repair", "hi-fi", "audio handbook", "audio electronics"],
        "Electronics": ["circuit", "pcb", "semiconductor", "transistor", "mosfet", "diode", "smps", "power supply", "relay", "inductor", "capacitor", "resistor", "oscillator", "op-amp", "integrated circuit", "electronics", "multimeter", "oscilloscope", "soldering"],
        "Automotive": ["honda", "ridgeline", "automotive", "car repair", "obd", "engine", "vehicle", "mechanic", "braking", "maintenance", "service manual", "alternator", "suspension", "steering"],
        "Math & Physics": ["calculus", "physics", "relativity", "quantum", "mathematics", "feynman", "hawking", "algebra", "geometry", "differential", "statistics", "probability", "electromagnetic", "maxwell", "wave propagation"]
    },
    "Human Biology": {
        "Nutrition & Herbalism": ["vitamin", "mineral", "nutrition", "natto", "supplements", "herb", "medicinal", "pharmacognosy", "ayurveda", "botanical", "tea", "plant", "herbalism", "pharmacopoeia", "tincture"],
        "Anatomy & Biomechanics": ["anatomy", "myofascial", "fascia", "biomechanics", "posture", "muscle", "skeleton", "physiology", "structural balance", "anatomy trains", "meridian"],
        "Physical Therapy & Recovery": ["recovery", "supple leopard", "stretch", "therapy", "strength", "exercise", "injury", "mobility", "conditioning", "rehab", "back pain", "body speaks", "pilates", "yoga"]
    },
    "Psychology & Cognitive": {
        "Clinical & Trauma": ["trauma", "depression", "ifs", "inner child", "clinical", "psychology", "anxiety", "cbt", "mental health", "sarno", "healing trauma", "addiction", "recovery skills"],
        "Habits & Performance": ["habits", "memory", "brain", "focus", "deep work", "limitless", "kwik", "neuro", "cognitive", "learning", "productivity", "mindmap", "speed reading", "rapid learning"],
        "Philosophy & Spirituality": ["stoic", "buddha", "philosophy", "meaning of life", "meditation", "reiki", "spiritual", "zen", "existence", "socrates", "plato", "aristotle", "freud"]
    }
}

def peek_content(path):
    """Read first 3000 chars of a file to understand context."""
    ext = path.suffix.lower()
    content = ""
    try:
        if ext == ".pdf":
            try:
                # Use a timeout for PDF reading
                reader = PdfReader(path)
                pages_to_read = min(2, len(reader.pages))
                content = " ".join([reader.pages[i].extract_text() or "" for i in range(pages_to_read)])
                if len(content) > 3000:
                    content = content[:3000]
            except Exception:
                # If PDF reading fails, just use the filename
                pass
        elif ext in [".txt", ".md"]:
            with open(path, "r", errors="ignore") as f:
                content = f.read(3000)
    except:
        pass
    return content.lower()

def get_best_category(filename, content):
    full_text = (filename + " " + content).lower()
    
    # Priority 1: Audio Repair (Very specific)
    for kw in STRUCTURE["Engineering"]["Audio Repair"]:
        if kw in full_text:
            return "Engineering/Audio Repair"

    # Priority 2: AI & Software (Prevent misclassification in Performance)
    for sub, keywords in STRUCTURE["AI & Software"].items():
        if any(kw in full_text for kw in keywords):
            return f"AI & Software/{sub}"

    # Tier 1: Multi-word phrases
    for cat, subs in STRUCTURE.items():
        if cat in ["AI & Software", "Engineering"]: continue
        for sub, keywords in subs.items():
            for kw in keywords:
                if len(kw.split()) > 1 and kw in full_text:
                    return f"{cat}/{sub}"
    
    # Tier 2: Single word matches
    for cat, subs in STRUCTURE.items():
        if cat == "AI & Software": continue
        for sub, keywords in subs.items():
            for kw in keywords:
                if kw in full_text:
                    return f"{cat}/{sub}"
    
    return "Miscellaneous"

def clean_filename(name):
    name = re.sub(r"\d{7,}", "", name)
    name = name.replace("_", " ").strip()
    return name

def process():
    if not TARGET_ROOT.exists():
        TARGET_ROOT.mkdir(parents=True)
    
    for cat, subs in STRUCTURE.items():
        for sub in subs.keys():
            (TARGET_ROOT / cat / sub).mkdir(parents=True, exist_ok=True)
    (TARGET_ROOT / "Miscellaneous").mkdir(exist_ok=True)

    print("Starting deep analysis and move...")
    
    # Track files already processed to avoid duplicates
    processed_hashes = set()

    for root, dirs, files in os.walk(SOURCE_ROOT):
        if "ingestion_curated_deep" in root: continue
        
        # 1. Group chapter-based fragments
        chapter_files = [f for f in files if re.search(r"(chapter|appendix|section|part|lesson|lec|L\d+|SN\d+)\s*\d*", f, re.I)]
        if len(chapter_files) > 2:
            sample_path = Path(root) / chapter_files[0]
            content = peek_content(sample_path)
            book_title = Path(root).name
            if book_title == "Miscellaneous" or len(book_title) < 5:
                try:
                    reader = PdfReader(sample_path)
                    book_title = reader.metadata.title or "Unknown Book"
                except: pass
            
            book_title = re.sub(r'[\\/*?:"<>|]', "", book_title).strip()
            cat_path = get_best_category(book_title, content)
            dest_dir = TARGET_ROOT / cat_path / book_title
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            for f in files:
                if f.startswith("."): continue
                dest_path = dest_dir / f
                shutil.copy2(Path(root) / f, dest_path)
                print(f"GROUPED: {book_title} -> {cat_path}")
                
                try:
                    from gateway.ingestion_queue import enqueue_file
                    enqueue_file(dest_path)
                except Exception as e:
                    print(f"Failed to enqueue {dest_path}: {e}")
            continue

        for f in files:
            if f.startswith("."): continue
            old_path = Path(root) / f
            print(f"PROCESSING: {f}")
            content = peek_content(old_path)
            cat_path = get_best_category(f, content)
            new_name = clean_filename(f)
            
            if len(Path(new_name).stem) < 5:
                try:
                    reader = PdfReader(old_path)
                    title = reader.metadata.title
                    if title and len(title) > 5:
                        new_name = f"{title.strip()}{Path(f).suffix}"
                except: pass
            
            dest_path = TARGET_ROOT / cat_path / new_name
            shutil.copy2(old_path, dest_path)
            print(f"MOVED: {f} -> {cat_path}/{new_name}")
            
            try:
                from gateway.ingestion_queue import enqueue_file
                enqueue_file(dest_path)
            except Exception as e:
                print(f"Failed to enqueue {dest_path}: {e}")

if __name__ == "__main__":
    process()
