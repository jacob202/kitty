from gateway.paths import PROJECT_ROOT

try:
    import feedparser
except ImportError:  # optional dependency — TTS/brief features degrade gracefully
    feedparser = None  # type: ignore[assignment]
import asyncio
import logging
import os
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional: trafilatura pulls clean article body text from a URL so the brief
# can be more than headline-only. Opt-in via BRIEF_ENRICH_ARTICLES=1 because it
# adds 2–4s of HTTP at brief refresh time.
try:
    import trafilatura

    HAS_TRAFILATURA = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_TRAFILATURA = False

_ENRICH_ARTICLES = os.environ.get("BRIEF_ENRICH_ARTICLES", "0") == "1"
_BODY_FETCH_TIMEOUT_SECONDS = 4.0
_BODY_MAX_LEN = 800

# Optional: tenacity gives the feed fetcher a tiny retry on transient
# connection/timeout errors. If not installed, _retry_transient is a no-op.
try:
    from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

    _retry_transient = retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(0.4),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
except ImportError:  # pragma: no cover - optional dependency

    def _retry_transient(fn):  # type: ignore[misc]
        return fn
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
    "world": "https://feeds.bbci.co.uk/news/world/rss.xml",
}


_RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


@_retry_transient
def _fetch_feed_response(url: str) -> requests.Response:
    response = requests.get(url, timeout=FEED_TIMEOUT_SECONDS, headers=_RSS_HEADERS)
    response.raise_for_status()
    return response


def _fetch_single_feed(category: str, url: str, limit: int) -> List[NewsHeadline]:
    """Fetch headlines from a single RSS feed."""
    headlines = []
    logger.info("Fetching %s news from %s...", category, url)
    try:
        response = _fetch_feed_response(url)
        feed = feedparser.parse(response.content)
        for entry in feed.entries[:limit]:
            headlines.append(
                NewsHeadline(
                    title=entry.title,
                    url=entry.link,
                    snippet=entry.get("summary", entry.get("description", ""))[:200],
                )
            )
    except Exception as e:
        logger.error("Failed to fetch %s news: %s", category, e)
    return headlines


def _extract_article_body(url: str) -> str:
    """Fetch and clean an article body via trafilatura. Returns "" on any failure."""
    if not HAS_TRAFILATURA:
        return ""
    try:
        resp = requests.get(url, timeout=_BODY_FETCH_TIMEOUT_SECONDS, headers=_RSS_HEADERS)
        resp.raise_for_status()
        text = trafilatura.extract(resp.text, favor_recall=False) or ""
        return text.strip()[:_BODY_MAX_LEN]
    except Exception as e:  # pragma: no cover - network paths
        logger.debug("trafilatura extract failed for %s: %s", url, e)
        return ""


def _enrich_with_bodies(headlines: List[NewsHeadline]) -> List[NewsHeadline]:
    if not _ENRICH_ARTICLES or not HAS_TRAFILATURA or not headlines:
        return headlines
    with ThreadPoolExecutor(max_workers=min(len(headlines), 6)) as pool:
        future_to_headline = {pool.submit(_extract_article_body, h.url): h for h in headlines}
        for fut in as_completed(future_to_headline):
            headline = future_to_headline[fut]
            try:
                body = fut.result(timeout=_BODY_FETCH_TIMEOUT_SECONDS + 1)
                if body:
                    headline.body = body
            except Exception:
                pass
    return headlines


def fetch_news(limit_per_feed: int = 3) -> List[NewsHeadline]:
    """Fetch headlines from all feeds in parallel, optionally enriched with article bodies."""
    all_headlines = []
    with ThreadPoolExecutor(max_workers=len(DEFAULT_FEEDS)) as pool:
        futures = {
            pool.submit(_fetch_single_feed, cat, url, limit_per_feed): cat
            for cat, url in DEFAULT_FEEDS.items()
        }
        for future in as_completed(futures):
            all_headlines.extend(future.result())
    return _enrich_with_bodies(all_headlines)


def get_tasks_summary() -> str:
    """Read the 'Next Smallest Action' from TASKS.md."""
    tasks_path = PROJECT_ROOT / "TASKS.md"
    try:
        content = tasks_path.read_text()
        if "## Next Smallest Action" in content:
            summary = (
                content.split("## Next Smallest Action")[1].strip().split("\n\n")[0]
            )
            return summary
    except Exception as e:
        logger.warning("Could not read TASKS.md: %s", e)
    return "No next action found. Check TASKS.md."


def _build_brief_worker_context(
    *, top_task: str, memory: str, tz: str = "America/Regina"
) -> str:
    parts_list = []
    if top_task:
        parts_list.append(f"Current Top Task: {top_task}")
    if memory:
        parts_list.append(
            memory
            if memory.startswith("Recent Memories:")
            else f"Recent Memories: {memory}"
        )
    if tz:
        parts_list.append(f"Timezone: {tz}")
    return "\n".join(parts_list)


def synthesize_brief_with_llm(
    headlines: List[NewsHeadline], task_summary: str, memory_snippet: str
) -> str:
    """Use LLM via LiteLLM to turn raw data into a warm, character-driven morning brief."""
    from gateway.context_enrichment import (
        calendar_today_text_sync,
        todos_text_sync,
        weather_text_sync,
    )
    from gateway.llm_client import chat

    news_text = "\n".join([f"- {h.title}" for h in headlines[:6]])
    calendar_text = calendar_today_text_sync()
    weather_text = weather_text_sync()
    todos_text = todos_text_sync()
    context_data = _build_brief_worker_context(
        top_task=task_summary,
        memory=memory_snippet,
    )

    calendar_section = f"\n- Calendar:\n{calendar_text}" if calendar_text else ""
    weather_section = f"\n- Weather: {weather_text}" if weather_text else ""
    todos_section = f"\n- Active Todos:\n{todos_text}" if todos_text else ""
    prompt = f"""GATHERED DATA FOR TODAY:
- News Headlines:
{news_text}{weather_section}{calendar_section}{todos_section}
{context_data}

TASK:
Write a short, warm, and proactive morning greeting for Jacob (3-4 paragraphs).
1. Acknowledge the start of the day. If weather is notable (cold, storm), mention it briefly.
2. If there are calendar events, mention any that look important or time-sensitive.
3. Mention the next action/task with a focus on 'Resume, don't restart'. Reference active todos if relevant.
4. MANDATORY: Include a 'Boring Path' recommendation. This must be the most conservative, low-risk, and surgical way to handle the current top task, prioritizing reliability over speed.
5. End with a supportive, 'friend who is paying attention' vibe.

Rules: Use contractions. No corporate filler. Be dry-funny if appropriate. Speak Canadian."""

    try:
        return chat(
            model="kitty-sonnet",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.4,
        )
    except Exception as e:
        logger.error("LLM Brief Synthesis failed: %s", e)
        return generate_brief_text(headlines, task_summary)


def _fetch_memory_snippet() -> str:
    """Fetch unified context for brief synthesis."""
    try:
        from gateway.memory_graph import unified_context

        return asyncio.run(unified_context("morning brief"))
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


def get_cached_brief(
    max_age_seconds: Optional[int] = BRIEF_CACHE_TTL_SECONDS,
) -> Optional[dict]:
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
