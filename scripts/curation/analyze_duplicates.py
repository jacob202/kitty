
import os
from pathlib import Path
from collections import defaultdict

def analyze_duplicates(directory):
    """
    Recursively scans a directory and generates a report of files with duplicate sizes.
    """
    sizes = defaultdict(list)
    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = Path(root) / filename
            try:
                size = os.path.getsize(filepath)
                sizes[size].append(str(filepath))
            except FileNotFoundError:
                pass

    with open("duplicate_analysis_report.txt", "w") as f:
        for size, filepaths in sizes.items():
            if len(filepaths) > 1:
                f.write(f"--- Files with size {size} ---\n")
                for filepath in filepaths:
                    f.write(filepath + "\n")
                f.write("\n")

if __name__ == "__main__":
    BOOKS_DIR = Path("/Volumes/DATA/books")
    analyze_duplicates(BOOKS_DIR)
