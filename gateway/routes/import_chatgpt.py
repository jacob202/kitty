"""ChatGPT import endpoint for the onboarding wizard.

Accepts a conversations.json upload, runs the existing extraction pipeline,
and stores approved items in idea_mine_items per packet 024 phase 2-3 rules.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger("kitty.import_chatgpt")
router = APIRouter(tags=["import"])


@router.post("/import/chatgpt")
async def import_chatgpt(file: UploadFile = File(...)):
    """Accept a ChatGPT conversations.json export, extract goldmine items,
    and stage them for review via the idea-mine pipeline."""
    if not file.filename or not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Expected a .json file")

    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        extractor = find_extractor()
        if extractor is None:
            return {"items": 0, "message": "Extraction pipeline not found — the scripts/curation/extract_chat_goldmine.py file is missing. Chat history will be importable after the extractor is in place."}

        project_root = Path(__file__).resolve().parent.parent.parent
        result = subprocess.run(
            ["python3.12", str(extractor), "--source", str(tmp_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )

        items_count = 0
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    items_count = len(data)
                elif isinstance(data, dict):
                    items_count = data.get("count", len(data))
            except json.JSONDecodeError:
                items_count = result.stdout.strip().count('\n') + 1

        return {
            "items": items_count,
            "message": f"Found {items_count} conversation threads to review" if items_count else "No extractable items were found in the file",
        }
    except subprocess.TimeoutExpired:
        return {"items": 0, "message": "The import took too long — try a smaller export file"}
    except Exception as exc:
        logger.warning("ChatGPT import failed: %s", exc)
        return {"items": 0, "message": f"Import failed: {exc}"}
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def find_extractor() -> Path | None:
    candidates = [
        Path("scripts/curation/extract_chat_goldmine.py"),
        Path(__file__).resolve().parent.parent.parent / "scripts" / "curation" / "extract_chat_goldmine.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None
