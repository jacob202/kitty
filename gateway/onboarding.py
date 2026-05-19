"""Onboarding interview logic — fact extraction and state management."""
from __future__ import annotations
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("kitty.onboarding")

from gateway.paths import DATA_DIR
STATE_FILE = DATA_DIR / "onboarding_state.json"

DOMAINS = {
    "identity": {
        "sensitivity": "low",
        "title": "Identity & Values",
        "questions": [
            "Who are you and what are you trying to build in your life right now?",
            "What does 'getting your life back on track' actually mean to you? What would that look like?",
            "What are your non-negotiables — things you won't compromise on?",
            "What's the biggest gap between who you are and who you want to be?",
        ],
    },
    "health": {
        "sensitivity": "medical",
        "title": "Health & Medical",
        "questions": [
            "What are your current health conditions or ongoing medical issues, if any?",
            "What medications or supplements are you taking regularly?",
            "How would you describe your sleep — hours, quality, when you wake up?",
            "What are your main health goals right now?",
            "Anything you've already tried that didn't work, health-wise?",
        ],
    },
    "fitness": {
        "sensitivity": "low",
        "title": "Fitness",
        "questions": [
            "What's your current fitness level and what do you actually do for exercise?",
            "What are your fitness goals — lose weight, build strength, more energy?",
            "Any injuries, limitations, or things you physically can't do?",
            "What equipment do you have access to?",
        ],
    },
    "automotive": {
        "sensitivity": "low",
        "title": "Automotive & Repair",
        "questions": [
            "What vehicles do you own? Make, model, year, and any known issues.",
            "What's your mechanical skill level — oil changes only, or full engine rebuilds?",
            "What tools do you have available?",
            "Any ongoing repair projects or things that need fixing?",
        ],
    },
    "productivity": {
        "sensitivity": "low",
        "title": "Productivity & Work",
        "questions": [
            "How would you describe your work style — hyperfocus, scattered, deadline-driven?",
            "What does a good day look like for you versus a bad day?",
            "What are your biggest time wasters or drains right now?",
            "What are your current main projects or goals?",
        ],
    },
    "finances": {
        "sensitivity": "financial",
        "title": "Finances",
        "questions": [
            "What are your financial goals — not numbers, just direction?",
            "What passive income ideas have you already considered or tried?",
            "Any Canadian-specific context I should know — province, situation?",
        ],
    },
    "learning": {
        "sensitivity": "low",
        "title": "Learning & Interests",
        "questions": [
            "What topics are you deep into right now?",
            "What do you want to learn that you haven't started yet?",
            "How do you learn best — video, doing it, reading, talking it through?",
        ],
    },
    "relationships": {
        "sensitivity": "low",
        "title": "Relationships & Social",
        "questions": [
            "Who are the most important people in your life right now?",
            "Where do you want more connection or community?",
            "Anything Kitty should help you maintain — check-ins, birthdays, important conversations?",
        ],
    },
}


def load_state() -> dict:
    """Load onboarding progress. Returns dict of {domain: completed_bool}."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {domain: False for domain in DOMAINS}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def extract_facts(domain: str, question: str, answer: str, sensitivity: str) -> list[str]:
    """Call LLM to extract key facts from a question/answer pair via LiteLLM."""
    from gateway.llm_client import chat
    from gateway.context_builder import build_worker_context

    task_desc = f"""Extract 1-5 key facts about Jacob from this onboarding answer.
Return ONLY a JSON array of short factual statements. No explanation, no preamble.
Each fact should be a complete sentence starting with "Jacob".
Sensitivity: {sensitivity} — extract only what's appropriate to store.

Question: {question}
Answer: {answer}

Example output: ["Jacob owns a 2010 Honda Civic.", "Jacob is comfortable doing oil changes himself."]

Facts:"""
    prompt = build_worker_context("onboarding", user_text=task_desc)
    try:
        content = chat(
            model="kitty-default",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.1,
        )
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
    except Exception as e:
        logger.warning("Fact extraction failed: %s", e)
    return [f"Jacob said about {domain}: {answer[:200]}"]


def store_answer(domain: str, question: str, answer: str, sensitivity: str) -> int:
    """Extract facts, store in Mem0 and ChromaDB. Returns number of facts stored."""
    from gateway.memory import add_memory
    from gateway.knowledge import ingest_file
    import tempfile

    facts = extract_facts(domain, question, answer, sensitivity)

    # Determine allowed_models based on sensitivity
    allowed = ["local_only"] if sensitivity in ("medical", "financial") else ["cloud_ok"]

    for fact in facts:
        add_memory(
            fact,
            namespace="facts",
            metadata={
                "domain": domain,
                "source": "onboarding",
                "sensitivity": sensitivity,
                "human_confirmed": True,
                "allowed_models": json.dumps(allowed),
            },
        )

    # Also write Q&A to a temp file and ingest into ChromaDB
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"Onboarding — {domain}\nQ: {question}\nA: {answer}\n")
            tmp_path = f.name
        ingest_file(
            tmp_path,
            sensitivity=sensitivity,
            source_label=f"onboarding_{domain}_{int(time.time())}",
        )
        Path(tmp_path).unlink(missing_ok=True)
    except Exception as e:
        logger.warning("ChromaDB ingestion failed (non-fatal): %s", e)

    return len(facts)
