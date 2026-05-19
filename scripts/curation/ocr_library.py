import os
import subprocess
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

SOURCE_ROOT = Path("/Volumes/DATA/books/ingestion_curated_deep")
CONVERTED_ROOT = Path("/Volumes/DATA/books/ingestion_curated_deep_ocr")

def run_ocr(file_path):
    rel_path = file_path.relative_to(SOURCE_ROOT)
    dest_path = CONVERTED_ROOT / rel_path
    
    if dest_path.exists():
        return f"SKIP: {rel_path}"
    
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"OCR START: {rel_path}")
    try:
        # --skip-text: Skip if text already exists (saves time)
        # --optimize 1: basic optimization
        # --jobs 2: use 2 cores for this process
        cmd = [
            "ocrmypdf",
            "--skip-text",
            "--optimize", "1",
            "--output-type", "pdf",
            str(file_path),
            str(dest_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return f"SUCCESS: {rel_path}"
        else:
            # Fallback copy if OCR fails
            shutil.copy2(file_path, dest_path)
            return f"ERROR (Copied raw): {rel_path} - {result.stderr[:200]}"
    except Exception as e:
        return f"CRITICAL: {rel_path} - {str(e)}"

def main():
    if not CONVERTED_ROOT.exists():
        CONVERTED_ROOT.mkdir()

    # We prioritize Engineering and Automotive as they contain the most non-searchable diagrams
    priorities = ["Engineering", "Automotive"]
    
    all_pdfs = []
    for root, dirs, files in os.walk(SOURCE_ROOT):
        for f in files:
            if f.lower().endswith(".pdf"):
                path = Path(root) / f
                all_pdfs.append(path)

    print(f"Found {len(all_pdfs)} PDFs. Starting parallel OCR (2 jobs)...")
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run_ocr, all_pdfs))
    
    for r in results:
        print(r)

if __name__ == "__main__":
    import shutil
    main()
