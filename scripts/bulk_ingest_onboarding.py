import os
import sys
import json
import re
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path("/Users/jacobbrizinski/Projects/kitty")
sys.path.insert(0, str(PROJECT_ROOT))

from gateway.onboarding import store_answer

def parse_markdown(file_path):
    content = Path(file_path).read_text()
    # Find all Q&A pairs. 
    # Pattern: **Q: ...** followed by A: ...
    # Or just Sections.
    sections = re.split(r'\n## \d+\.', content)
    
    qa_pairs = []
    for section in sections:
        lines = section.split('\n')
        if not lines: continue
        domain = lines[0].strip().lower()
        
        # Simple extraction for this specific format
        current_q = None
        current_a = []
        
        for line in lines[1:]:
            if line.startswith("**Q:"):
                if current_q and current_a:
                    qa_pairs.append((domain, current_q, "\n".join(current_a).strip()))
                current_q = line.replace("**Q:", "").replace("**", "").strip()
                current_a = []
            elif line.startswith("A:"):
                current_a.append(line.replace("A:", "").strip())
            elif current_q and line.strip():
                current_a.append(line.strip())
        
        if current_q and current_a:
            qa_pairs.append((domain, current_q, "\n".join(current_a).strip()))
            
    return qa_pairs

def main():
    draft_path = PROJECT_ROOT / "ONBOARDING_DRAFT.md"
    if not draft_path.exists():
        print("Draft file not found.")
        return

    print(f"Reading {draft_path}...")
    qa_pairs = parse_markdown(draft_path)
    
    print(f"Found {len(qa_pairs)} Q&A pairs. Starting ingestion...")
    
    for i, (domain, q, a) in enumerate(qa_pairs, 1):
        # Determine sensitivity based on domain name
        sensitivity = "low"
        if "health" in domain or "medical" in domain:
            sensitivity = "medical"
        elif "finance" in domain:
            sensitivity = "financial"
            
        print(f"[{i}/{len(qa_pairs)}] Ingesting {domain}...")
        try:
            # We use the store_answer from gateway.onboarding which we just updated
            n = store_answer(domain, q, a, sensitivity)
            print(f"  Stored {n} facts.")
        except Exception as e:
            print(f"  Failed: {e}")

    print("\nIngestion complete.")

if __name__ == "__main__":
    main()
