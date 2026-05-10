import logging
import os
from typing import Optional

logger = logging.getLogger("kitty.troubleshooter")

def initiate_troubleshooting(device: str, symptom: str) -> str:
    """
    Queries the knowledge base for a specific device and symptom,
    then uses the LLM to format the FIRST diagnostic step in a Socratic way.
    """
    import requests
    from gateway.knowledge import search_knowledge
    from pathlib import Path

    # 1. Find the technical truth in the DB
    query = f"troubleshooting diagnostic {device} {symptom}"
    chunks = search_knowledge(query, limit=3)
    
    if not chunks:
        return f"I don't have the manual or notes for {device} relating to '{symptom}' in my knowledge base yet. Want to look for the service manual together?"

    # Combine context
    context = "\n\n".join([c["text"] for c in chunks])
    
    from gateway.paths import PROMPTS_DIR
    # 2. Use LLM to formulate the "Partner" response
    api_key = os.environ.get("OPENROUTER_API_KEY")
    soul_path = PROMPTS_DIR / "soul_v1.md"
    soul_context = soul_path.read_text() if soul_path.exists() else ""

    prompt = f"""{soul_context}

CONTEXT:
Jacob is reporting a symptom: "{symptom}" on device: "{device}".
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

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/jacobbrizinski/kitty",
            },
            json={
                "model": "google/gemini-2.0-flash-exp:free" if not api_key else "deepseek/deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.4,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Troubleshooter synthesis failed: {e}")
        return "I see some notes on that in the manual, but my processor tripped up. What's the first voltage check you want to run?"
