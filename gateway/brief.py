from gateway.paths import PROJECT_ROOT
from gateway.journal import recent_entries

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
    # The Verge retired their AI subfeed; VentureBeat's AI category is a
    # solid replacement and is still updated daily.
    "ai_news": "https://venturebeat.com/category/ai/feed/",
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
    """Read the next priority from PROJECT_STATUS.md, falling back to TASKS.md."""
    status_path = PROJECT_ROOT / "docs" / "PROJECT_STATUS.md"
    try:
        content = status_path.read_text()
        for heading in ("## Next Best Step", "## Next Smallest Action", "## Next"):
            if heading in content:
                summary = content.split(heading)[1].strip().split("\n\n")[0]
                if summary:
                    return summary.strip()
    except Exception as e:
        logger.warning("Could not read PROJECT_STATUS.md: %s", e)

    tasks_path = PROJECT_ROOT / "TASKS.md"
    try:
        content = tasks_path.read_text()
        for heading in ("## Next Smallest Action", "## Next"):
            if heading in content:
                summary = content.split(heading)[1].strip().split("\n\n")[0]
                if summary:
                    return summary.strip()
    except Exception as e:
        logger.warning("Could not read TASKS.md: %s", e)
    return ""


def synthesize_brief_with_llm(
    headlines: List[NewsHeadline],
    task_summary: str,
    memory_snippet: str,
    themes: list[dict] = None,
    novelty: dict = None,
) -> str:
    """Use LLM via LiteLLM to turn raw data into a warm, character-driven morning brief.

    When themes are present they are surfaced so the brief can connect news to
    what Jacob's been working on. novelty is accepted for pipeline compatibility
    but is no longer rendered into the prompt — it read as meta-noise.
    """
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
    recent_journal = _fetch_recent_journal_text(limit=3)

    sections: list[str] = [f"News:\n{news_text}"]
    if weather_text:
        sections.append(f"Weather: {weather_text}")
    if calendar_text:
        sections.append(f"Calendar:\n{calendar_text}")
    if todos_text:
        sections.append(f"Active todos:\n{todos_text}")
    if task_summary:
        sections.append(f"Next priority:\n{task_summary}")
    if recent_journal:
        sections.append(f"What Jacob wrote recently:\n{recent_journal}")
    if themes:
        theme_list = ", ".join(t["theme"] for t in themes[:3])
        sections.append(f"Recurring themes in his notes: {theme_list}")
    if memory_snippet:
        sections.append(f"From memory:\n{memory_snippet[:400]}")

    data_block = "\n\n".join(sections)

    prompt = f"""You're writing Jacob's morning brief. Here's today's data:

{data_block}

Write 3–4 short paragraphs that feel like a smart friend catching him up, not a corporate digest.
- Lead with anything time-sensitive (weather, calendar, urgent news).
- Surface one concrete next step using what he's been working on — reference his own words if he wrote anything relevant recently.
- Point out one news item that connects to his current interests, if any.
- End warm but not sappy. Dry-funny is fine.

No bullet points. No headers. No "Certainly!" or "Great question!". Contractions. Speak Canadian."""

    try:
        return chat(
            model="kitty-sonnet",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.4,
        )
    except Exception as e:
        logger.error("LLM Brief Synthesis failed: %s", e)
        return generate_brief_text(headlines, task_summary)


def _fetch_memory_snippet() -> str:
    """Fetch unified context for brief synthesis."""
    try:
        from gateway.memory_graph import unified_context

        return _run_async(unified_context("morning brief"))
    except Exception:
        return ""


def _fetch_recent_journal_text(limit: int = 3) -> str:
    """Return the last few journal entries as plain text for the brief prompt."""
    try:
        entries = recent_entries(days=7, limit=limit)
    except Exception:
        return ""
    if not entries:
        return ""
    lines = []
    for e in entries[:limit]:
        ts = e.get("ts", 0)
        text = (e.get("entry") or "").strip()
        if text:
            try:
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%a %b %-d")
            except Exception:
                dt = ""
            lines.append(f"  [{dt}] {text[:200]}")
    return "\n".join(lines)


def _run_async(coro):
    """Run a coroutine from a sync context.

    Single seam for any async helper in this module. The brief pipeline
    is invoked from CLI and FastAPI handlers, so this hides the
    asyncio.run pattern behind a named function — both so the call
    sites read uniformly and so a future async refactor can swap the
    implementation (e.g. nest_asyncio or an async entry point) without
    touching every call.
    """
    return asyncio.run(coro)


def generate_brief_text(headlines: List[NewsHeadline], task_summary: str) -> str:
    """Fallback brief text when LLM is unavailable."""
    news_summary = "\n".join([f"- {h.title}" for h in headlines[:4]])
    return f"Good morning, Jacob. Here's what's happening today:\n\n{news_summary}\n\nYour next action: {task_summary}"


def summarize_headlines_to_bullets(headlines: List[NewsHeadline]) -> List[str]:
    """Turn enriched headlines into 3–5 bullet 'what's interesting today' lines.

    Requires at least some bodies to be present (i.e. BRIEF_ENRICH_ARTICLES=1).
    Returns [] if there's no body content or the LLM call fails.
    """
    items_with_body = [h for h in headlines if h.body]
    if not items_with_body:
        return []

    from gateway.llm_client import chat

    rows = []
    for h in items_with_body[:8]:
        body = h.body.strip()
        rows.append(f"- {h.title}\n  {body[:500]}")
    article_block = "\n".join(rows)

    prompt = (
        "You're writing a one-screen morning brief for Jacob. Below are today's "
        "top articles with extracted body text. Pick the 3–5 most genuinely "
        "interesting items and write one tight, declarative bullet per item — "
        "specific claim or finding, no hedging, no headlines that just rehash "
        "the title. Keep each bullet under 24 words. Output ONLY the bullets, "
        "one per line, each starting with '- '. No preamble, no headers.\n\n"
        f"ARTICLES:\n{article_block}"
    )

    try:
        raw = chat(
            model="kitty-sonnet",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3,
        )
    except Exception as e:
        logger.warning("Brief bullet summarization failed: %s", e)
        return []

    # chat() returns "" when the entire LLM fallback chain is exhausted;
    # treat that as an explicit failure so it doesn't look like "no
    # interesting bullets today" silently.
    if not raw or not raw.strip():
        logger.warning(
            "Brief bullet summarization: LLM returned empty response "
            "(fallback chain may be exhausted)"
        )
        return []

    bullets: List[str] = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-•*").strip()
        if line:
            bullets.append(line)
    return bullets[:5]


def _build_brief_result(
    *,
    today: str,
    headlines: List[NewsHeadline],
    memory: str,
    intention: str,
    summary_bullets: Optional[List[str]] = None,
) -> dict:
    from contracts.brief_item import BriefItem

    item = BriefItem(
        date=today,
        headlines=headlines,
        memory_snippet=memory[:500] if memory else "",
        intention=intention,
        summary_bullets=summary_bullets or [],
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


def detect_research_themes(limit: int = 5, lookback_days: int = 14) -> list[dict]:
    """Detect Jacob's current research themes from recent journal entries.

    Source: the last ``lookback_days`` of journal entries, ranked by
    bigram frequency. This replaced the earlier "search_all + bigram"
    heuristic that produced noise and lied to the LLM with a fake
    "general knowledge" theme when memory was empty.

    Returns a list of ``{"theme": str, "mentions": int, "source":
    "journal"}`` dicts, ordered by mentions descending, capped at
    ``limit``. Returns ``[]`` when there is no journal data (empty log
    file, all entries older than ``lookback_days``, or read error).

    The caller (``generate_brief``, ``synthesize_brief_with_llm``) is
    responsible for treating ``[]`` honestly — i.e. NOT inserting a
    fabricated theme into the LLM prompt.
    """
    from collections import Counter

    STOPWORDS = {
        "the", "and", "for", "with", "that", "this", "have", "from",
        "are", "was", "but", "not", "you", "your", "they", "them",
        "what", "when", "where", "which", "while", "would", "could",
        "should", "about", "into", "than", "then", "just", "like",
        "more", "some", "very", "been", "will", "their", "there",
    }

    try:
        entries = recent_entries(days=lookback_days, limit=200)
    except Exception as e:
        logger.warning("detect_research_themes: recent_entries failed: %s", e)
        return []

    counter: Counter = Counter()
    for entry in entries:
        text = (entry.get("entry") or "").lower()
        if not text:
            continue
        words = [w.strip(".,!?;:\"'()[]") for w in text.split()]
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            if len(w1) > 4 and len(w2) > 4 and w1 not in STOPWORDS and w2 not in STOPWORDS:
                counter[f"{w1} {w2}"] += 1

    themes: list[dict] = []
    for theme, mentions in counter.most_common(limit):
        themes.append({"theme": theme, "mentions": mentions, "source": "journal"})
    return themes


def rank_headlines_by_relevance(headlines: List[NewsHeadline], themes: list[dict]) -> List[NewsHeadline]:
    """
    Rerank headlines by relevance to detected themes.
    Returns headlines with relevance scores, prioritizing theme-matched content.
    """
    if not themes or not headlines:
        return headlines

    theme_keywords = set()
    for theme_obj in themes:
        theme = theme_obj.get("theme", "").lower()
        theme_keywords.update(theme.split())

    scored = []
    for headline in headlines:
        title_lower = headline.title.lower()
        snippet_lower = headline.snippet.lower() if headline.snippet else ""
        content = f"{title_lower} {snippet_lower}"

        # Score based on theme keyword matches
        matches = sum(1 for keyword in theme_keywords if keyword in content)
        relevance = min(0.99, 0.3 + (matches * 0.15)) if matches > 0 else 0.0
        scored.append((headline, relevance))

    # Sort by relevance descending, then by original order for stability
    scored.sort(key=lambda x: x[1], reverse=True)
    return [h for h, _ in scored]


def detect_brief_novelty(headlines: List[NewsHeadline], themes: list[dict]) -> dict:
    """
    Detect what's novel in today's headlines vs. recent briefs.
    Returns dict with:
    {
        "new_count": N,
        "repeated_count": N,
        "novel_headlines": [...],
        "summary": "X new articles on your themes today"
    }
    """
    cached = get_cached_brief()

    if not cached or "headlines" not in cached:
        # No cache to compare against; everything is new
        return {
            "new_count": len(headlines),
            "repeated_count": 0,
            "novel_headlines": headlines[:3],  # Top 3
            "summary": f"{min(len(headlines), 3)} articles on your research interests today",
        }

    # Get headlines from cached brief
    cached_headlines = cached.get("headlines", [])
    cached_titles = {h.get("title", "") for h in cached_headlines if isinstance(h, dict)}
    cached_titles.update({str(h.title) for h in cached_headlines if isinstance(h, NewsHeadline)})

    # Count novel headlines
    novel = []
    for headline in headlines:
        if headline.title not in cached_titles:
            novel.append(headline)

    return {
        "new_count": len(novel),
        "repeated_count": len(headlines) - len(novel),
        "novel_headlines": novel[:3],  # Top 3 novel
        "summary": f"{len(novel)} new articles on your themes today" if novel else "Same themes as yesterday",
    }


def generate_brief() -> dict:
    """Generate a morning brief. Returns a dict matching BriefItem schema.

    Contextual brief generation:
    1. Detect Jacob's current research themes from memory
    2. Rank headlines by relevance to those themes
    3. Identify novel vs. repeated content
    4. Synthesize brief with theme/novelty context
    """
    today = datetime.now(timezone.utc).date().isoformat()
    headlines = fetch_news()
    task_summary = get_tasks_summary()
    memory = _fetch_memory_snippet()

    # Phase 1: Detect research themes from Jacob's recent activity
    themes = detect_research_themes(limit=5)

    # Phase 2: Rerank headlines by relevance to detected themes
    ranked_headlines = rank_headlines_by_relevance(headlines, themes)

    # Phase 3: Detect what's novel vs. repeated
    novelty = detect_brief_novelty(ranked_headlines, themes)

    # Phase 4: Synthesize brief with theme and novelty context
    brief_text = synthesize_brief_with_llm(
        ranked_headlines,
        task_summary,
        memory,
        themes=themes,
        novelty=novelty,
    )

    # Only attempt bullet synthesis when enrichment is on — without bodies the
    # model would just paraphrase headlines.
    summary_bullets = summarize_headlines_to_bullets(ranked_headlines) if _ENRICH_ARTICLES else []

    result = _build_brief_result(
        today=today,
        headlines=ranked_headlines,
        memory=memory,
        intention=brief_text,
        summary_bullets=summary_bullets,
    )

    # Push to phone if notify is configured
    try:
        from gateway.notify import send_brief, is_configured

        if is_configured():
            send_brief(brief_text)
    except Exception:
        pass

    return _store_cached_brief(result)
