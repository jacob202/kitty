"""Web Change Tracker — Orca-inspired cross-session web tracking.

This module tracks changes to web content across visits, similar to Orca's
change tracking functionality.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import List

from gateway.paths import DATA_DIR

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    TRACKER_AVAILABLE = True
except Exception as exc:
    TRACKER_AVAILABLE = False
    TRACKER_IMPORT_ERROR: Exception | None = exc
else:
    TRACKER_IMPORT_ERROR = None

logger = logging.getLogger("kitty.web_tracker")

KITTY_DIR = DATA_DIR


class WebChangeTracker:
    """Track web content changes across visits — Orca-inspired."""

    def __init__(self):
        self.tracker_dir = KITTY_DIR / "web_tracker"
        self.tracker_dir.mkdir(exist_ok=True)
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2") if TRACKER_AVAILABLE else None
        if not TRACKER_AVAILABLE:
            logger.warning("Web tracker disabled: %s", TRACKER_IMPORT_ERROR)

    def capture(self, url: str, content: str) -> str:
        """Capture a snapshot of a web page."""
        if not TRACKER_AVAILABLE:
            logger.warning("Tracker not available - using mock capture")
            return str(self.tracker_dir / "mock_snapshot.json")

        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        snapshot_file = (
            self.tracker_dir / f"{url_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        try:
            emb = self.encoder.encode([content[:2000]])[0].tolist()
        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            emb = [0.0] * 384  # Fallback zero vector

        snapshot = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "content_preview": content[:5000],
            "embedding": emb,
        }
        snapshot_file.write_text(json.dumps(snapshot, indent=2))
        logger.info("Captured snapshot: %s", url)
        return str(snapshot_file)

    def compare(self, url: str) -> str:
        """Compare latest snapshot with previous one for the same URL."""
        if not TRACKER_AVAILABLE:
            return "Web tracker comparison not available (missing dependencies)."

        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        snapshots = sorted(self.tracker_dir.glob(f"{url_hash}_*.json"))

        if len(snapshots) < 2:
            return "No previous snapshot to compare against."

        prev = json.loads(snapshots[-2].read_text())
        curr = json.loads(snapshots[-1].read_text())

        # Compute cosine similarity
        prev_emb = np.array(prev.get("embedding", []))
        curr_emb = np.array(curr.get("embedding", []))

        if len(prev_emb) == 0 or len(curr_emb) == 0:
            return "No embedding data available for comparison."

        similarity = np.dot(prev_emb, curr_emb) / (
            np.linalg.norm(prev_emb) * np.linalg.norm(curr_emb) + 1e-9
        )

        return (
            f"Content similarity: {similarity:.2%}\n\n"
            f"Previous ({prev['timestamp']}):\n{prev['content_preview'][:500]}\n\n"
            f"Current ({curr['timestamp']}):\n{curr['content_preview'][:500]}"
        )

    def get_snapshots(self, url: str) -> List[dict]:
        """Get all snapshots for a URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        snapshots = sorted(self.tracker_dir.glob(f"{url_hash}_*.json"))

        result = []
        for snap_file in snapshots:
            try:
                data = json.loads(snap_file.read_text())
                result.append(data)
            except Exception as e:
                logger.warning("Could not read snapshot %s: %s", snap_file, e)

        return result

    def list_tracked_urls(self) -> List[str]:
        """List all URLs being tracked."""
        urls = set()
        for snap_file in self.tracker_dir.glob("*.json"):
            try:
                data = json.loads(snap_file.read_text())
                urls.add(data.get("url", ""))
            except Exception:
                pass
        return list(urls)

    def is_available(self) -> bool:
        """Check if tracker is available."""
        return TRACKER_AVAILABLE


# Global instance
web_tracker = WebChangeTracker()
