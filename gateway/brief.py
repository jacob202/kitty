import os
import feedparser
import logging
from datetime import datetime
from typing import List, Dict
from contracts.brief_item import NewsHeadline

logger = logging.getLogger("kitty.brief")

DEFAULT_FEEDS = {
    "regina": "https://www.cbc.ca/cmlink/rss-canada-saskatchewan",
    "audiophile": "https://www.stereophile.com/rss.xml",
    "ai_research": "https://arxiv.org/rss/cs.AI",
    "ai_news": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "high_signal": "https://news.ycombinator.com/rss",
    "world": "https://feeds.bbci.co.uk/news/world/rss.xml"
}

def fetch_news(limit_per_feed: int = 3) -> List[NewsHeadline]:
    """Fetch headlines from a set of default RSS feeds."""
    all_headlines = []
    
    for category, url in DEFAULT_FEEDS.items():
        logger.info(f"Fetching {category} news from {url}...")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit_per_feed]:
                all_headlines.append(NewsHeadline(
                    title=entry.title,
                    url=entry.link,
                    snippet=entry.get("summary", entry.get("description", ""))[:200]
                ))
        except Exception as e:
            logger.error(f"Failed to fetch {category} news: {e}")
            
    return all_headlines

def get_tasks_summary() -> str:
    """Read the 'Next Smallest Action' from TASKS.md."""
    tasks_path = "/Users/jacobbrizinski/Projects/kitty/TASKS.md"
    try:
        with open(tasks_path, "r") as f:
            content = f.read()
            # Look for the section after ## Next Smallest Action
            if "## Next Smallest Action" in content:
                summary = content.split("## Next Smallest Action")[1].strip().split("\n\n")[0]
                return summary
    except Exception as e:
        logger.warning(f"Could not read TASKS.md: {e}")
    return "No next action found. Check TASKS.md."

def generate_brief_text(headlines: List[NewsHeadline], task_summary: str) -> str:
    """
    Generate a concise morning brief text.
    In the future, this will be passed to an LLM for 'soul' injection.
    """
    date_str = datetime.now().strftime("%A, %B %d, %Y")

    lines = [f"Good morning, Jacob. It's {date_str}.\n"]

    lines.append("## Your Next Action")
    lines.append(f"{task_summary}\n")

    lines.append("## Recent News")
    for h in headlines[:5]:
        lines.append(f"- {h.title}")

    lines.append("\nResume, don't restart.")

    return "\n".join(lines)


def _fetch_memory_snippet(limit: int = 3) -> str:
    """Pull recent Mem0 memories as a short text block."""
    try:
        from gateway.memory import get_context_block
        return get_context_block("morning daily context recent", limit=limit)
    except Exception as e:
        logger.warning("Memory fetch failed: %s", e)
        return ""


def generate_brief() -> dict:
    """Generate a morning brief. Returns a dict matching BriefItem schema."""
    from contracts.brief_item import BriefItem

    today = datetime.now().date().isoformat()
    headlines = fetch_news()
    task_summary = get_tasks_summary()
    memory = _fetch_memory_snippet()
    brief_text = generate_brief_text(headlines, task_summary)

    item = BriefItem(
        date=today,
        headlines=headlines,
        memory_snippet=memory[:500] if memory else "",
        intention=brief_text,
    )
    return item.model_dump(mode="json")
