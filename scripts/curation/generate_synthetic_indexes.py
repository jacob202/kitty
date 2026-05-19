import os
import json
import logging
from pathlib import Path
from pypdf import PdfReader
from gateway.llm_client import call_llm

CURATED_ROOT = Path("/Volumes/DATA/books/ingestion_curated_deep")
OUTPUT_DIR = Path("/Volumes/DATA/books/synthetic_indexes")

def generate_book_index(folder_path):
    files = sorted([f for f in folder_path.iterdir() if f.is_file() and not f.name.startswith(".")])
    if not files:
        return
    
    print(f"Indexing: {folder_path.name}")
    
    # Sample the first and middle chapter for context
    previews = []
    for f in [files[0], files[len(files)//2]]:
        try:
            if f.suffix.lower() == ".pdf":
                reader = PdfReader(f)
                text = reader.pages[0].extract_text() or ""
                previews.append(f"File: {f.name}\nPreview: {text[:1000]}")
        except: pass

    prompt = f"""You are a Master Librarian. I have a collection of files for a single book titled '{folder_path.name}'.
    Here are previews of some chapters:
    
    {"-"*20}
    {" ".join(previews)}
    {"-"*20}
    
    TASK:
    1. Summarize the main thesis of this book in 3 sentences.
    2. Provide a 'Specialist Instruction' for an AI agent on how to use this book (e.g., 'Treat this as the source of truth for 1970s Sansui bias adjustment').
    3. List the logical flow of the chapters based on the file names: {", ".join([f.name for f in files])}.
    
    Format the output as a Markdown file.
    """
    
    response = call_llm(
        messages=[{"role": "user", "content": prompt}],
        model="kitty-default",
        operation="synthetic_indexing"
    )
    
    if response:
        with open(folder_path / "00_OVERVIEW.md", "w") as f:
            f.write(response)
        print(f"Created overview for {folder_path.name}")

def main():
    # Only index folders that contain chapter fragments
    for root, dirs, files in os.walk(CURATED_ROOT):
        folder = Path(root)
        if folder == CURATED_ROOT: continue
        
        # If it's a leaf node folder (a book folder)
        if not dirs and len(files) > 2:
            generate_book_index(folder)

if __name__ == "__main__":
    main()
