
import os
import json
import re
from pathlib import Path
from collections import defaultdict

# Priority order: 0 is highest (keep this), 3 is lowest
PRIORITY_MAP = [
    "/Volumes/DATA/Books/ingestion_curated_deep_ocr",
    "/Volumes/DATA/Books/ingestion_curated_deep",
    "/Volumes/DATA/Books/ingestion_curated",
    "/Volumes/DATA/Books"
]

def normalize_name(name: str) -> str:
    """Removes messy suffixes and special chars to identify 'the same book'."""
    name = name.lower()
    # Remove common messy suffixes
    name = re.sub(r"\(z-library\..*?\)", "", name)
    name = re.sub(r"\(1lib\..*?\)", "", name)
    name = re.sub(r"_liber3", "", name)
    name = re.sub(r"annas archive", "", name, flags=re.IGNORECASE)
    # Remove file extensions
    name = Path(name).stem
    # Remove non-alphanumeric (keep spaces)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    # Collapse whitespace
    return " ".join(name.split())

def get_priority(path_str: str) -> int:
    for i, prefix in enumerate(PRIORITY_MAP):
        if path_str.startswith(prefix):
            return i
    return 999

def map_canonical_library(root_dir: Path):
    """
    Groups all versions of a book and picks the best one.
    """
    book_groups = defaultdict(list)
    
    print("🔍 Scanning all directories for book versions...")
    for root, _, files in os.walk(root_dir):
        if "books_dedup_backup" in root: continue
        
        for f in files:
            if f.startswith(".") or f.endswith(".json") or f.endswith(".md"): 
                continue
                
            full_path = Path(root) / f
            norm_name = normalize_name(f)
            priority = get_priority(str(full_path))
            
            book_groups[norm_name].append({
                "path": str(full_path),
                "priority": priority,
                "size": full_path.stat().st_size
            })

    canonical_manifest = {}
    total_size = 0
    
    print("⚖️ Selecting winners and calculating canonical size...")
    for norm_name, versions in book_groups.items():
        # Sort by priority (lowest number first), then by size (largest as tie-breaker for better scans)
        winner = sorted(versions, key=lambda x: (x["priority"], -x["size"]))[0]
        canonical_manifest[norm_name] = winner
        total_size += winner["size"]

    # Save Manifest
    manifest_path = Path("data/canonical_library_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(canonical_manifest, f, indent=2)
        
    print(f"\n✅ Mapping Complete!")
    print(f"   Unique Books Identified: {len(canonical_manifest)}")
    print(f"   Total Canonical Size: {total_size / (1024**3):.2f} GB")
    print(f"   Manifest Saved to: {manifest_path}")

if __name__ == "__main__":
    BOOKS_ROOT = Path("/Volumes/DATA/Books")
    map_canonical_library(BOOKS_ROOT)
