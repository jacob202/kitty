
import os
import shutil
from pathlib import Path
from collections import defaultdict

# Priority order: 0 is highest (keep this), 3 is lowest (delete if others exist)
PRIORITY_MAP = [
    "/Volumes/DATA/books/ingestion_curated_deep_ocr",
    "/Volumes/DATA/books/ingestion_curated_deep",
    "/Volumes/DATA/books/ingestion_curated",
    "/Volumes/DATA/books"  # Root falls here if not in above subdirs
]

BACKUP_DIR = Path("/Volumes/DATA/books_dedup_backup")

def get_priority(path_str):
    for i, prefix in enumerate(PRIORITY_MAP):
        if path_str.startswith(prefix):
            return i
    return 999  # Should not happen given the roots

def smart_deduplicate(directory):
    """
    Scans for duplicates by size and keeps the one with the highest priority folder.
    Moves others to a backup directory.
    """
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir(parents=True)

    sizes = defaultdict(list)
    print("Scanning files and calculating priorities...")
    
    for root, _, files in os.walk(directory):
        if str(BACKUP_DIR) in root:
            continue
            
        for filename in files:
            if filename.startswith("."): continue
            filepath = Path(root) / filename
            try:
                size = os.path.getsize(filepath)
                sizes[size].append(str(filepath))
            except FileNotFoundError:
                pass

    moved_count = 0
    kept_count = 0

    print("Processing duplicates...")
    for size, paths in sizes.items():
        if len(paths) <= 1:
            kept_count += 1
            continue

        # Sort by priority (lower number is better)
        paths_with_priority = sorted([(get_priority(p), p) for p in paths])
        
        # The first one is the winner
        best_priority, best_path = paths_with_priority[0]
        others = paths_with_priority[1:]

        print(f"\nSize {size}: Keeping {best_path} (Priority {best_priority})")
        
        for priority, other_path in others:
            # Create relative path structure in backup to avoid collisions
            rel_path = os.path.relpath(other_path, directory)
            dest = BACKUP_DIR / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"  Moving to backup: {other_path} (Priority {priority})")
            shutil.move(other_path, dest)
            moved_count += 1
        
        kept_count += 1

    print(f"\nDone! Kept {kept_count} unique files. Moved {moved_count} duplicates to {BACKUP_DIR}.")

if __name__ == "__main__":
    BOOKS_DIR = Path("/Volumes/DATA/books")
    smart_deduplicate(BOOKS_DIR)
