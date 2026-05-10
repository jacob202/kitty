import logging
import os
from pathlib import Path

logger = logging.getLogger("kitty.learning")

def generate_micro_lesson(topic: str) -> str:
    """
    Queries the knowledge base for textbook information on a topic
    and synthesizes a 10-minute action-oriented micro-lesson.
    """
    import requests
    from gateway.knowledge import search_knowledge

    # Force the search to look specifically at textbook chunks
    query = f"concept fundamental theory {topic}"
    chunks = search_knowledge(query, limit=5)
    
    # Filter chunks to favor books if possible, though search_knowledge handles relevance
    textbook_chunks = [c for c in chunks if c.get("doc_type") in ("book", "textbook")]
    if not textbook_chunks:
        # Fallback to whatever we found
        textbook_chunks = chunks

    if not textbook_chunks:
        return f"I don't have any textbooks ingested covering '{topic}' right now."

    context = "\n\n".join([c["text"] for c in textbook_chunks[:3]])

    from gateway.paths import PROMPTS_DIR
    api_key = os.environ.get("OPENROUTER_API_KEY")
    soul_path = PROMPTS_DIR / "soul_v1.md"
    soul_context = soul_path.read_text() if soul_path.exists() else ""

    prompt = f"""{soul_context}

CONTEXT:
Jacob wants to learn about: "{topic}".
Here is the core material extracted from our ingested textbooks:
{context}

TASK:
Turn this raw textbook data into a 10-Minute Micro-Lesson.
Remember, Jacob learns best by doing, breaking things down, and cause-and-effect reasoning. No generic theory without application.

Structure the response:
1. **The Core Concept**: Explain it in plain English, 2 sentences max. Use an analogy to cars or audio repair if it fits.
2. **The Mechanism**: How does it actually work under the hood? (Brief).
3. **The 10-Minute Proof**: Give him ONE physical or mental action to prove he understands it right now. (e.g., "Go look at the schematic for the AU-7900 and find...")

Keep it punchy. No filler."""

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
                "max_tokens": 400,
                "temperature": 0.5,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Lesson planner synthesis failed: {e}")
        return "I hit a snag trying to build that lesson. Let's try again in a minute."
