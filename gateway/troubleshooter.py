"""
Queries the knowledge base for a specific device and symptom,
then uses the LLM to format the FIRST diagnostic step in a Socratic way.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger("kitty.troubleshooter")


def initiate_troubleshooting(device: str, symptom: str) -> str:
    from gateway.knowledge import search_knowledge
    from gateway.context_builder import build_worker_context
    from gateway.llm_client import chat
    from pathlib import Path

    # 1. Find the technical truth in the DB
    query = f"troubleshooting diagnostic {device} {symptom}"
    chunks = search_knowledge(query, limit=3)

    if not chunks:
        return f"I don't have the manual or notes for {device} relating to '{symptom}' in my knowledge base yet. Want to look for the service manual together?"

    # Combine context
    context = "\n\n".join([c["text"] for c in chunks])

    # 2. Use LLM to formulate the "Partner" response
    task_desc = f"""Jacob is reporting a symptom: "{symptom}" on device: "{device}".
Here is what the service manual or our notes say about this:
{context}

TASK:
Do NOT dump the entire troubleshooting process on him.
Act as a Socratic repair partner.
1. Acknowledge the symptom (warm, brief).
2. Tell him what the manual says the *very first* step or test point is.
3. Ask him if he has his tools ready to check that specific thing.
End with a question to prompt his action.
Keep it under 4 sentences. Speak Canadian."""

    prompt = build_worker_context("troubleshooter", task_desc=task_desc)

    try:
        return chat(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.4,
        )
    except Exception as e:
        logger.error(f"Troubleshooter synthesis failed: {e}")
        return "I see some notes on that in the manual, but my processor tripped up. What's the first voltage check you want to run?"
