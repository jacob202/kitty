
import os
from pathlib import Path

def deduplicate_by_size(directory):
    """
    Recursively scans a directory and deletes duplicate files based on their size.
    """
    sizes = {}
    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = Path(root) / filename
            try:
                size = os.path.getsize(filepath)
                if size in sizes:
                    print(f"Deleting duplicate file: {filepath}")
                    os.remove(filepath)
                else:
                    sizes[size] = filepath
            except FileNotFoundError:
                # The file may have been deleted by a previous run of the script
                pass

if __name__ == "__main__":
    BOOKS_DIR = Path("/Volumes/DATA/books")
    deduplicate_by_size(BOOKS_DIR)
