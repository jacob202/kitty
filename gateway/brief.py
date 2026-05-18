from gateway.paths import PROJECT_ROOT

import feedparser
import logging
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional
from contracts.brief_item import NewsHeadline
from gateway.model_digest import get_model_digest_section

logger = logging.getLogger("kitty.brief")
FEED_TIMEOUT_SECONDS = 1.25
BRIEF_CACHE_TTL_SECONDS = 900
_brief_cache_lock = threading.Lock()
_brief_cache: Optional[dict] = None

DEFAULT_FEEDS = {
    "regina": "https://www.cbc.ca/cmlink/rss-canada-saskatchewan",
    "audiophile": "https://www.stereophile.com/rss.xml",
    "ai_research": "https://arxiv.org/rss/cs.AI",
    "ai_news": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "high_signal": "https://news.ycombinator.com/rss",
    "world": "https://feeds.bbci.co.uk/news/world/rss.xml"
}


def _fetch_single_feed(category: str, url: str, limit: int) -> List[NewsHeadline]:
    """Fetch headlines from a single RSS feed."""
    headlines = []
    logger.info("Fetching %s news from %s...", category, url)
    try:
        response = requests.get(
            url,
            timeout=FEED_TIMEOUT_SECONDS,
            headers={"User-Agent": "KittyBrief/1.0"},
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        for entry in feed.entries[:limit]:
            headlines.append(NewsHeadline(
                title=entry.title,
                url=entry.link,
                snippet=entry.get("summary", entry.get("description", ""))[:200]
            ))
    except Exception as e:
        logger.error("Failed to fetch %s news: %s", category, e)
    return headlines


def fetch_news(limit_per_feed: int = 3) -> List[NewsHeadline]:
    """Fetch headlines from all feeds in parallel."""
    all_headlines = []
    with ThreadPoolExecutor(max_workers=len(DEFAULT_FEEDS)) as pool:
        futures = {
            pool.submit(_fetch_single_feed, cat, url, limit_per_feed): cat
            for cat, url in DEFAULT_FEEDS.items()
        }
        for future in as_completed(futures):
            all_headlines.extend(future.result())
    return all_headlines


def get_tasks_summary() -> str:
    """Read the 'Next Smallest Action' from TASKS.md."""
    from gateway.paths import PROJECT_ROOT
    tasks_path = PROJECT_ROOT / "TASKS.md"
    try:
        content = tasks_path.read_text()
        if "## Next Smallest Action" in content:
            summary = content.split("## Next Smallest Action")[1].strip().split("\n\n")[0]
            return summary
    except Exception as e:
        logger.warning("Could not read TASKS.md: %s", e)
    return "No next action found. Check TASKS.md."


def synthesize_brief_with_llm(headlines: List[NewsHeadline], task_summary: str, memory_snippet: str) -> str:
    """Use LLM via LiteLLM to turn raw data into a warm, character-driven morning brief."""
    from gateway.llm_client import chat
    from gateway.context_builder import build_worker_context

    news_text = "\n".join([f"- {h.title}" for h in headlines[:6]])
    context_data = build_worker_context(
        "brief",
        top_task=f"Current Top Task: {task_summary}",
        memory=f"Recent Memories: {memory_snippet}",
        tz="America/Regina"
    )

    prompt = f"""GATHERED DATA FOR TODAY:
- News Headlines:
{news_text}
{context_data}

TASK:
Write a short, warm, and proactive morning greeting for Jacob (3-4 paragraphs).
1. Acknowledge the start of the day and maybe one interesting news item.
2. Mention the next action/task with a focus on 'Resume, don't restart'.
3. MANDATORY: Include a 'Boring Path' recommendation. This must be the most conservative, low-risk, and surgical way to handle the current top task, prioritizing reliability over speed.
4. End with a supportive, 'friend who is paying attention' vibe.

Rules: Use contractions. No corporate filler. Be dry-funny if appropriate. Speak Canadian."""

    try:
        return chat(
            model="anthropic/claude-3.7-sonnet",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.4,
        )
    except Exception as e:
        logger.error("LLM Brief Synthesis failed: %s", e)
        return generate_brief_text(headlines, task_summary)


def _fetch_memory_snippet() -> str:
    """Fetch a short memory snippet for context."""
    try:
        from gateway.memory import search_memory
        results = search_memory("morning brief context", limit=2)
        return "\n".join([m.get("memory", "") for m in results])
    except Exception:
        return ""


def generate_brief_text(headlines: List[NewsHeadline], task_summary: str) -> str:
    """Fallback brief text when LLM is unavailable."""
    news_summary = "\n".join([f"- {h.title}" for h in headlines[:4]])
    return f"Good morning, Jacob. Here's what's happening today:\n\n{news_summary}\n\nYour next action: {task_summary}"


def _build_brief_result(
    *,
    today: str,
    headlines: List[NewsHeadline],
    memory: str,
    intention: str,
) -> dict:
    from contracts.brief_item import BriefItem

    item = BriefItem(
        date=today,
        headlines=headlines,
        memory_snippet=memory[:500] if memory else "",
        intention=intention,
    )
    result = item.model_dump(mode="json")
    model_news = get_model_digest_section(limit=3)
    if model_news:
        result["model_news"] = model_news
    return result


def _store_cached_brief(result: dict) -> dict:
    global _brief_cache
    cached = dict(result)
    cached["_cached_at"] = datetime.now(timezone.utc).timestamp()
    with _brief_cache_lock:
        _brief_cache = cached
    return result


def get_cached_brief(max_age_seconds: Optional[int] = BRIEF_CACHE_TTL_SECONDS) -> Optional[dict]:
    with _brief_cache_lock:
        cached = dict(_brief_cache) if _brief_cache else None
    if not cached:
        return None
    cached_at = cached.pop("_cached_at", None)
    if max_age_seconds is not None and cached_at is not None:
        age_seconds = datetime.now(timezone.utc).timestamp() - cached_at
        if age_seconds > max_age_seconds:
            return None
    return cached


def generate_fast_brief() -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    task_summary = get_tasks_summary()
    memory = _fetch_memory_snippet()
    intention = generate_brief_text([], task_summary)
    return _build_brief_result(
        today=today,
        headlines=[],
        memory=memory,
        intention=intention,
    )


def generate_brief() -> dict:
    """Generate a morning brief. Returns a dict matching BriefItem schema."""
    today = datetime.now(timezone.utc).date().isoformat()
    headlines = fetch_news()
    task_summary = get_tasks_summary()
    memory = _fetch_memory_snippet()

    brief_text = synthesize_brief_with_llm(headlines, task_summary, memory)

    result = _build_brief_result(
        today=today,
        headlines=headlines,
        memory=memory,
        intention=brief_text,
    )

    # Push to phone if notify is configured
    try:
        from gateway.notify import send_brief, is_configured
        if is_configured():
            send_brief(brief_text)
    except Exception:
        pass

    return _store_cached_brief(result)
