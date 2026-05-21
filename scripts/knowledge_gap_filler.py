import sys
import os
from pathlib import Path

def search_and_append(query, category):
    print(f"Searching web for: {query} (Category: {category})")
    # This would use the research skill or firecrawl to get content
    # For now, we mock the 'proactive' discovery logic
    content = f"### Web Discovery: {query}\n\n[Findings from search would go here]"
    
    dest_dir = Path(f"/Volumes/DATA/books/ingestion_curated/{category}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    filename = query.lower().replace(" ", "_")[:50] + "_supplement.md"
    with open(dest_dir / filename, "w") as f:
        f.write(content)
    print(f"Appended knowledge to: {filename}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        search_and_append(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python3 knowledge_gap_filler.py <query> <category>")
