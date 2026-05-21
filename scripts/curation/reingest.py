
import asyncio
import os
from pathlib import Path

from gateway.knowledge import ingest

async def main():
    """Iterates through all files in the knowledge base source directory and ingests them."""
    source_dir = Path("/Volumes/DATA/Books")
    if not source_dir.is_dir():
        print(f"Error: Source directory not found at {source_dir}")
        return

    for root, _, files in os.walk(source_dir):
        for file in files:
            file_path = Path(root) / file
            print(f"Ingesting {file_path}...")
            try:
                result = await ingest(file_path)
                print(f"Ingestion result: {result.status}")
            except Exception as e:
                print(f"Error ingesting {file_path}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
