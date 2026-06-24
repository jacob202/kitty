import csv
import json
import base64
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger("kitty.inventory")

from gateway.paths import DATA_DIR
from gateway.llm_client import call_llm
from gateway.prompts import INVENTORY_PHOTO_PROMPT

INVENTORY_CSV = DATA_DIR / "inventory.csv"

def extract_parts_from_image(image_path: str | Path) -> List[Dict]:
    """Uses Claude 3.7 Sonnet to extract electronic components from a photo."""
    path = Path(image_path)
    if not path.exists():
        logger.error("Image not found: %s", path)
        return []

    try:
        with open(path, "rb") as f:
            img_data = f.read()
        base64_img = base64.b64encode(img_data).decode("utf-8")

        prompt = INVENTORY_PHOTO_PROMPT

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}},
                    ],
                }
            ],
            "temperature": 0.1,
        }

        content = call_llm(model="anthropic/claude-3.7-sonnet", **payload, timeout=45)
        if not content:
            return []
            
        # Clean up if the model wrapped it in markdown anyway
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
            
        parts = json.loads(content)
        return parts if isinstance(parts, list) else []

    except Exception as e:
        logger.error("Visual inventory extraction failed: %s", e)
        return []

def append_to_inventory(parts: List[Dict]) -> bool:
    """Appends extracted parts to the master CSV inventory."""
    if not parts:
        return False

    INVENTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    file_exists = INVENTORY_CSV.exists()
    
    fieldnames = ["part_number", "value", "type", "quantity", "notes", "date_added"]
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        with open(INVENTORY_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            
            for part in parts:
                row = {
                    "part_number": part.get("part_number", ""),
                    "value": part.get("value", ""),
                    "type": part.get("type", ""),
                    "quantity": part.get("quantity", 1),
                    "notes": part.get("notes", ""),
                    "date_added": today
                }
                writer.writerow(row)
        logger.info("Successfully added %d items to inventory.", len(parts))
        return True
    except Exception as e:
        logger.error("Failed to write to inventory CSV: %s", e)
        return False

def process_inventory_image(image_path: str | Path) -> str:
    """Full workflow: extract from image and append to CSV."""
    parts = extract_parts_from_image(image_path)
    if not parts:
        return "I couldn't identify any parts clearly in that photo."
    
    success = append_to_inventory(parts)
    if success:
        items = "\n".join([f"- {p.get('quantity', 1)}x {p.get('part_number') or p.get('value')} ({p.get('type')})" for p in parts])
        return f"Got it. Added these to your inventory:\n{items}"
    return "I found the parts but failed to save them to the CSV."
