
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
import sqlite3
from datetime import datetime
import mimetypes
import requests

import yaml
from gateway import clerk, llm_client
from contracts.smart_file_schema import FileMetadata

from gateway.config import OWUI_URL, OWUI_ADMIN_EMAIL, OWUI_ADMIN_PASSWORD, CANONICAL_LIBRARY_DIR, STATUS_DB_PATH

# --- OpenWebUI Helpers ---
def owui_login():
    resp = requests.post(f"{OWUI_URL}/api/v1/auths/signin", 
                         json={"email": OWUI_ADMIN_EMAIL, "password": OWUI_ADMIN_PASSWORD}, 
                         timeout=20)
    resp.raise_for_status()
    return resp.json().get("token")

def owui_get_kbs(token):
    resp = requests.get(f"{OWUI_URL}/api/v1/knowledge/", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    items = data["items"] if isinstance(data, dict) else data
    return {item["name"].lower(): item["id"] for item in items}

async def generate_soul_analysis(filename: str, text_sample: str) -> dict:
    prompt = f"""
You are the Lead Librarian for the Kitty system. Your task is to perform a deep "Soul Analysis" of a document to transform it into a Smart Markdown Asset.

DOCUMENT FILENAME: {filename}
CONTENT SAMPLE (First 6000 chars):
---
{text_sample}
---

Please provide a JSON response with the following fields:
1. "canonical_name": A clean, descriptive filename (e.g. "Physics 101 Manual").
2. "primary_category": One of [Engineering, Health, Physics, Psychology, AI, General].
3. "sub_category": A specific sub-domain.
4. "soul": One paragraph describing the "Soul" of the book. Go beyond a summary; identify its core essence, its provocative reason for being, and the one fundamental question it answers better than any other.
5. "hooks": A list of 3-5 "Spicy Hooks". These should be non-obvious, provocative, or counter-intuitive insights extracted from the text that would immediately grab an expert's attention.
6. "takes": A list of 2-3 "Unique Takes". What specific, perhaps controversial, perspectives does this author offer? How does this book contradict the 'standard' view of its subject?
7. "specialist_instruction": A one-sentence instruction for a specialist agent on how to use this file as a weapon of reasoning.
8. "summary": A 3-sentence technical summary.
9. "table_of_contents": A list of the main sections.

RESPONSE MUST BE PURE JSON. MAKE IT BOLD, CREATIVE, AND ANALYTICALLY SHARP.
"""
    try:
        response_text = llm_client.call_llm(
            messages=[{"role": "user", "content": prompt}],
            model="kitty-default",
            max_tokens=2000,
            temperature=0.2
        )
        clean_json = response_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3].strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"Error in LLM analysis: {e}")
        return {}

def update_db_status(book_id, status, error=None, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    updates = [f"{k}=1" for k, v in kwargs.items() if v]
    update_str = ", ".join(updates) + (", " if updates else "")
    
    query = f"UPDATE curation_status SET status=?, error_message=?, {update_str} processed_at=? WHERE id=?"
    cursor.execute(query, (status, error, now, book_id))
    conn.commit()
    conn.close()

async def process_and_upload(book_id: str, source_path: Path):
    """The One-Pass Curation Engine: Extract -> Synthesize -> Assemble -> Upload."""
    print(f"🚀 Starting Full Pipeline: {book_id}")
    update_db_status(book_id, 'in_progress')
    
    try:
        # 1. Extraction
        raw_text = clerk._extract_text(source_path)
        if not raw_text or len(raw_text.strip()) < 50:
            raise ValueError("Extraction yielded no useful text.")
        update_db_status(book_id, 'in_progress', extraction_done=True)

        # 2. Synthesis (Soul/Hooks/Takes)
        analysis = await generate_soul_analysis(source_path.name, raw_text[:8000])
        if not analysis:
            raise ValueError("LLM analysis failed.")
        update_db_status(book_id, 'in_progress', synthesis_done=True)

        # 3. Assembly (SMA)
        file_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        metadata = FileMetadata(
            original_filename=source_path.name,
            canonical_name=analysis.get("canonical_name", source_path.stem),
            file_type=source_path.suffix.lstrip('.'),
            hash=file_hash,
            primary_category=analysis.get("primary_category", "General"),
            sub_category=analysis.get("sub_category", "Misc"),
            soul=analysis.get("soul", ""),
            hooks=analysis.get("hooks", []),
            takes=analysis.get("takes", []),
            specialist_instruction=analysis.get("specialist_instruction", ""),
            summary=analysis.get("summary", ""),
            table_of_contents=analysis.get("table_of_contents", []),
            processed_at=datetime.now().strftime("%Y-%m-%d"),
            model_used="kitty-default"
        )
        
        frontmatter = yaml.dump(metadata.model_dump(), sort_keys=False)
        header = f"\n# {metadata.canonical_name}\n\n> **The Soul:** {metadata.soul}\n\n## 🎯 Hooks\n" + \
                 "\n".join([f"- {h}" for h in metadata.hooks]) + \
                 "\n\n## 💡 Takes\n" + \
                 "\n".join([f"- {t}" for t in metadata.takes]) + \
                 f"\n\n## 🛠️ Specialist Instruction\n*{metadata.specialist_instruction}*\n\n---\n\n## 📋 Table of Contents\n" + \
                 "\n".join([f"- {item}" for item in metadata.table_of_contents]) + "\n\n---\n"
        
        full_content = f"---\n{frontmatter}---\n{header}\n{raw_text}"
        
        dest_dir = CANONICAL_LIBRARY_DIR / metadata.primary_category / metadata.sub_category
        dest_dir.mkdir(parents=True, exist_ok=True)
        target_path = dest_dir / f"{metadata.canonical_name}.md"
        target_path.write_text(full_content)
        update_db_status(book_id, 'in_progress', assembly_done=True)

        # 4. Upload to OpenWebUI
        token = owui_login()
        kb_map = owui_get_kbs(token)
        
        kb_name = metadata.primary_category.lower()
        if kb_name not in kb_map:
            kb_name = "general reference"
        kb_id = kb_map.get(kb_name)

        if kb_id:
            # Upload file
            with target_path.open("rb") as f:
                up_resp = requests.post(f"{OWUI_URL}/api/v1/files/", 
                                        headers={"Authorization": f"Bearer {token}"},
                                        files={"file": (target_path.name, f, "text/markdown")},
                                        timeout=120)
                up_resp.raise_for_status()
                file_id = up_resp.json().get("id")
                
                # Add to KB
                add_resp = requests.post(f"{creds['url']}/api/v1/knowledge/{kb_id}/file/add",
                                         headers={"Authorization": f"Bearer {token}"},
                                         json={"file_id": file_id},
                                         timeout=120)
                add_resp.raise_for_status()
                print(f"  Synced to OpenWebUI: {kb_name}")

        update_db_status(book_id, 'completed')
        print(f"✅ Full Process Success: {metadata.canonical_name}")
        return True

    except Exception as e:
        print(f"❌ Pipeline Failure for {book_id}: {e}")
        update_db_status(book_id, 'failed', error=str(e))
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)
    b_id = sys.argv[1]
    b_path = Path(sys.argv[2])
    asyncio.run(process_and_upload(b_id, b_path))
