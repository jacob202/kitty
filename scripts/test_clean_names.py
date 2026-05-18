import os
import re
from urllib.parse import unquote
from pathlib import Path

BOOKS_DIR = Path("/Volumes/DATA/books")

CLEANUP_PATTERNS = [
    r"_liber\d+",
    r"\(z-library\.sk, 1lib\.sk, z-lib\.sk\)",
    r"\(z-lib\.org\)",
    r"-- Anna’s Archive",
    r"\(Z-Library\)",
    r"\(z-library\.sk\)",
    r"\(1lib\.sk\)",
    r"\(z-lib\.sk\)",
    r"\{.*\}",  # remove curly brace suffixes like {138194547}
    r"\(.*(19|20)\d{2}.*\)", # Remove year in parens if it's too much, but maybe keep it? Let's be careful.
]

def clean_name(name: str) -> str:
    # 1. Unquote URL encoding
    name = unquote(name)
    
    # 2. Basic cleanup
    base = Path(name).stem
    ext = Path(name).suffix
    
    new_name = base
    for pattern in CLEANUP_PATTERNS:
        new_name = re.sub(pattern, "", new_name, flags=re.IGNORECASE)
    
    # Remove extra spaces and underscores
    new_name = new_name.replace("_", " ").strip()
    new_name = re.sub(r"\s+", " ", new_name)
    
    # Remove leading/trailing dashes/dots
    new_name = new_name.strip(" -.")
    
    return f"{new_name}{ext}"

def main():
    files = []
    for root, dirs, filenames in os.walk(BOOKS_DIR):
        for f in filenames:
            if f.startswith("."): continue
            old_path = Path(root) / f
            new_f = clean_name(f)
            if new_f != f:
                print(f"RENAME: {f} -> {new_f}")

if __name__ == "__main__":
    main()
