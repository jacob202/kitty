"""
Auto-Correcting RAG Worker - Proactively fixes Kitty's knowledge base.
Triggered by consolidation events or manual feedback.
"""

import logging

from src.memory.lightrag_store import LightRAGStore
from src.memory.memory_weave import get_weave

logger = logging.getLogger("kitty.memory.correction")

class CorrectionWorker:
    """
    Worker that identifies conflicting or incorrect knowledge and
    re-indexes the vector store with corrected context.
    """

    def __init__(self):
        self.weave = get_weave()
        self.store = LightRAGStore()

    def process_pending_corrections(self, hours: int = 48) -> int:
        """
        Identify 'wrong' feedback and inject corrective context into LightRAG.
        Returns: Number of corrections applied.
        """
        events = self.weave.get_recent_events(event_type="user_correction", hours=hours)
        corrections = [e for e in events if e["description"] == "wrong"]

        if not corrections:
            return 0

        count = 0
        for item in corrections:
            entity = item["entity"]
            metadata = item.get("metadata", {})
            user_correction = metadata.get("correction_text")

            if user_correction:
                # 1. Create a corrective 'pearl'
                correction_chunk = (
                    f"CORRECTION FOR {entity}:\n"
                    f"Previous knowledge was marked as incorrect by user. "
                    f"Corrected Information: {user_correction}\n"
                    f"Verified on: {item['timestamp']}"
                )

                # 2. Inject directly into LightRAG as high-priority context
                try:
                    self.store.add_document(correction_chunk)
                    logger.info(f"Applied RAG correction for {entity}")
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to apply RAG correction for {entity}: {e}")

        return count

def run_nightly_fixes():
    """Entry point for the Dream Cycle to trigger fixes."""
    worker = CorrectionWorker()
    return worker.process_pending_corrections()
