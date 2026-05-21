
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any

import yaml
from gateway import clerk, llm_client
from contracts.smart_file_schema import FileMetadata

# --- Configuration ---
TEST_FILE = Path("/Volumes/DATA/Books/ingestion_curated_deep_ocr/Engineering/Automotive/Engineering & Physical Systems/2006 2008 Honda Ridgeline Service Manual PNO SC 61SJC02 (Honda).pdf")
PROTOTYPE_DIR = Path("data/prototypes")

async def generate_soul_analysis(filename: str, text_sample: str) -> Dict[str, Any]:
    """Calls LLM to generate the 'Soul, Hooks, and Takes' metadata."""
    
    prompt = f"""
You are the Lead Librarian for the Kitty system. Your task is to perform a deep "Soul Analysis" of a document to transform it into a Smart Markdown Asset.

DOCUMENT FILENAME: {filename}
CONTENT SAMPLE (First 6000 chars):
---
{text_sample}
---

Please provide a JSON response with the following fields:
1. "canonical_name": A clean, descriptive filename without messy suffixes.
2. "primary_category": One of [Engineering, Health, Physics, Psychology, AI, General].
3. "sub_category": A specific sub-domain.
4. "soul": One paragraph describing the core essence and provocative purpose of this document. What is its "reason for being"?
5. "hooks": A list of 3-5 specific, spicy insights or "hooks" that make this document unique.
6. "takes": A list of 2-3 unique perspectives or "takes" this document offers.
7. "specialist_instruction": A one-sentence instruction for a specialist agent on how to best utilize this file's data.
8. "summary": A 3-sentence technical summary.
9. "table_of_contents": A list of the main sections found or inferred.

RESPONSE MUST BE PURE JSON.
"""

    response_text = llm_client.call_llm(
        messages=[{"role": "user", "content": prompt}],
        model="kitty-default",
        max_tokens=2000,
        temperature=0.2
    )
    
    # Try to extract JSON from response
    try:
        # Simple cleanup if LLM wraps in markdown blocks
        clean_json = response_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3].strip()
            
        return json.loads(clean_json)
    except Exception as e:
        print(f"Error parsing LLM response: {e}")
        print(f"Raw Response: {response_text}")
        return {}

async def create_smart_asset(file_path: Path):
    """Orchestrates the creation of a Smart Markdown Asset (SMA)."""
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    print(f"🚀 Starting Smart Asset Prototype for: {file_path.name}")
    
    # 1. Extract Text
    print("  Step 1: Extracting raw text...")
    raw_text = clerk._extract_text(file_path)
    if not raw_text:
        print("  ❌ Extraction failed.")
        return
    
    # 2. Generate Hash
    file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    
    # 3. Deep Analysis
    print("  Step 2: Performing Soul Analysis via LLM...")
    analysis = await generate_soul_analysis(file_path.name, raw_text[:6000])
    if not analysis:
        print("  ❌ LLM Analysis failed.")
        return

    # 4. Assemble Metadata (Pydantic)
    metadata = FileMetadata(
        original_filename=file_path.name,
        canonical_name=analysis.get("canonical_name", file_path.stem),
        file_type=file_path.suffix.lstrip('.'),
        hash=file_hash,
        primary_category=analysis.get("primary_category", "General"),
        sub_category=analysis.get("sub_category", "Misc"),
        soul=analysis.get("soul", ""),
        hooks=analysis.get("hooks", []),
        takes=analysis.get("takes", []),
        specialist_instruction=analysis.get("specialist_instruction", ""),
        summary=analysis.get("summary", ""),
        table_of_contents=analysis.get("table_of_contents", []),
        processed_at="2026-05-18", # Placeholder
        model_used="kitty-default"
    )

    # 5. Assemble the Smart Markdown File
    print("  Step 3: Assembling Smart Markdown Asset...")
    
    # Frontmatter
    frontmatter = yaml.dump(metadata.model_dump(), sort_keys=False)
    
    # Intelligence Header
    header = f"""
# {metadata.canonical_name}

> **The Soul:** {metadata.soul}

## 🎯 Hooks
{chr(10).join([f"- {h}" for h in metadata.hooks])}

## 💡 Takes
{chr(10).join([f"- {t}" for t in metadata.takes])}

## 🛠️ Specialist Instruction
*{metadata.specialist_instruction}*

---

## 📋 Table of Contents
{chr(10).join([f"- {item}" for item in metadata.table_of_contents])}

---
"""

    # Final Content
    full_markdown = f"---\n{frontmatter}---\n{header}\n{raw_text}"
    
    # 6. Save
    PROTOTYPE_DIR.mkdir(parents=True, exist_ok=True)
    target_path = PROTOTYPE_DIR / f"{metadata.canonical_name}.md"
    target_path.write_text(full_markdown)
    
    print(f"✅ Prototype Complete: {target_path}")
    print(f"   Category: {metadata.primary_category} > {metadata.sub_category}")

if __name__ == "__main__":
    asyncio.run(create_smart_asset(TEST_FILE))
