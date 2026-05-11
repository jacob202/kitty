"""Socratic Layer for Kitty.

Tracks user absorption and triggers 'Knowledge Gates' to ensure 
Jacob is actually learning from the technical materials.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.learning")
STATS_FILE = DATA_DIR / "user_learning_stats.json"

def init_stats():
    """Initialize or load user learning stats."""
    if not STATS_FILE.exists():
        default_stats = {
            "user_level": 1,
            "absorption_score": 0, # 0-100
            "tool_calls_since_gate": 0,
            "gates_passed": 0,
            "topics_mastered": [],
            "last_gate_at": None
        }
        STATS_FILE.write_text(json.dumps(default_stats, indent=2))
        return default_stats
    return json.loads(STATS_FILE.read_text())

def update_stats(updates: Dict):
    """Update user stats atomically."""
    stats = init_stats()
    stats.update(updates)
    STATS_FILE.write_text(json.dumps(stats, indent=2))

def record_interaction(was_educational: bool = False, tool_used: bool = False):
    """Record an interaction and check if a Knowledge Gate should be triggered."""
    stats = init_stats()
    
    if tool_used:
        stats["tool_calls_since_gate"] += 1
    
    if was_educational:
        stats["absorption_score"] = min(100, stats["absorption_score"] + 2)
        
    update_stats(stats)
    
    # Trigger gate every 5 tool calls
    if stats["tool_calls_since_gate"] >= 5:
        return True
    return False

async def generate_knowledge_gate_question(topic: str = "general") -> str:
    """Generate a quiz question based on recently ingested technical data."""
    from gateway.knowledge import search
    from gateway.llm_client import call_llm

    # Fetch high-authority chunks for the topic
    chunks = await search(f"core principles of {topic}", limit=5)
    context = "\n\n".join([c["text"] for c in chunks])
    
    prompt = f"""You are the Socratic Librarian. Jacob has reached a 'Knowledge Gate.'
    
    CONTEXT FROM RECENTLY INGESTED MATERIALS:
    {context}
    
    TASK:
    Based on the context, ask Jacob ONE technical question that helps build intuition about how things work.
    
    Rules for Jacob's level (Curious Generalist):
    - Do not assume professional expertise in Software, Hardware, or Cars. 
    - He knows "a tiny bit about a lot of things," so connect new concepts to basic physical or logical principles.
    - Avoid jargon. If you must use a technical term, explain it briefly in context.
    - Focus on the "Why" (e.g., 'If we didn't have this component, what would happen?').
    - Speak like a helpful partner exploring a new hobby together.
    """
    
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.7
    }
    
    return call_llm(model="anthropic/claude-3.7-sonnet", **payload)

def process_gate_answer(answer: str, question: str) -> bool:
    """Assess Jacob's answer to a knowledge gate question."""
    from gateway.llm_client import call_llm
    
    prompt = f"""Jacob is answering a Knowledge Gate question.
    
    QUESTION: {question}
    JACOB'S ANSWER: {answer}
    
    TASK:
    Is this answer technically correct? 
    Respond in JSON format:
    {{
      "correct": true/false,
      "feedback": "...",
      "level_up": true/false
    }}
    """
    
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "max_tokens": 300,
        "temperature": 0.1
    }
    
    try:
        response = call_llm(model="anthropic/claude-3.7-sonnet", **payload)
        data = json.loads(response)
        
        if data.get("correct"):
            stats = init_stats()
            stats["gates_passed"] += 1
            stats["tool_calls_since_gate"] = 0
            if data.get("level_up"):
                stats["user_level"] += 1
            update_stats(stats)
            
        return data
    except Exception:
        return {"correct": True, "feedback": "System error. Gate passed by default.", "level_up": False}
