"""
AI Development Monitor - tracks MLX, Apple Silicon, local LLM developments
relevant to the Kitty project. Provides dashboard data with tagged highlights.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_FILE = DATA_DIR / "ai_dev_monitor.json"

TOPICS = [
    "MLX framework Apple Silicon ML optimization",
    "Apple MLX models quantization fine-tuning",
    "local LLM Apple Silicon performance",
    "open source LLM distillation small models",
    "MLX community model release",
    "Apple M4 Ultra ML performance",
    "LoRA fine-tuning Apple Silicon Mac",
    "open source AI agent frameworks",
    "small language model benchmark comparison",
]

SOURCES = [
    "https://huggingface.co/mlx-community",
    "https://github.com/ml-explore/mlx",
    "https://developer.apple.com/machine-learning/",
    "https://github.com/ml-explore/mlx-examples",
    "https://pypi.org/project/mlx-lm/",
    "https://github.com/Blaizzy/mlx-vlm",
    "https://huggingface.co/spaces/mlx-community/leaderboard",
    "https://arxiv.org/list/cs.LG/recent",
    "https://news.ycombinator.com/",
    "https://github.com/ggml-org/llama.cpp",
    "https://ollama.com/blog",
    "https://simonwillison.net/tags/mlx/",
    "https://www.answer.ai/posts/",
]


@dataclass
class DevItem:
    title: str
    url: str
    source: str
    summary: str
    tag: str  # "standout" | "relevant" | "general"
    reason: str  # why it matters to Kitty
    date: str = ""
    topics: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


class AIDevMonitor:
    def __init__(self):
        self._items: list[DevItem] = []
        self._last_fetch: float = 0
        self._load()

    def _load(self):
        if DATA_FILE.exists():
            try:
                raw = json.loads(DATA_FILE.read_text())
                self._items = [DevItem(**i) for i in raw.get("items", [])]
                self._last_fetch = raw.get("last_fetch", 0)
            except Exception as e:
                logger.warning(f"Failed to load dev monitor data: {e}")
                self._items = []
                self._last_fetch = 0

    def _save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps({
            "last_fetch": self._last_fetch,
            "items": [i.to_dict() for i in self._items],
        }, indent=2))

    def get_items(self, tag: Optional[str] = None, limit: int = 20) -> list[DevItem]:
        items = self._items
        if tag:
            items = [i for i in items if i.tag == tag]
        items.sort(key=lambda x: x.date, reverse=True)
        return items[:limit]

    def get_summary(self) -> dict:
        return {
            "total": len(self._items),
            "standout": len([i for i in self._items if i.tag == "standout"]),
            "relevant": len([i for i in self._items if i.tag == "relevant"]),
            "last_fetch": datetime.fromtimestamp(self._last_fetch).isoformat() if self._last_fetch else None,
            "topics_covered": list(set(t for i in self._items for t in i.topics)),
        }

    def fetch(self, tavily_key: Optional[str] = None) -> list[DevItem]:
        """Fetch latest AI developments via web search or Tavily."""
        api_key = tavily_key or os.getenv("TAVILY_API_KEY")
        new_items = []

        if api_key:
            new_items = self._fetch_via_tavily(api_key)
        else:
            new_items = self._fetch_via_httpx()

        if new_items:
            self._items = new_items + self._items
            self._items = self._items[:100]
            self._last_fetch = time.time()
            self._save()

        return self._items

    def _fetch_via_tavily(self, api_key: str) -> list[DevItem]:
        """Fetch via Tavily search API."""
        items = []
        try:
            for topic in TOPICS:
                resp = httpx.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": topic,
                        "search_depth": "basic",
                        "max_results": 5,
                        "include_answer": True,
                    },
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                summary = data.get("answer", "")
                for result in data.get("results", []):
                    items.append(DevItem(
                        title=result.get("title", "Untitled"),
                        url=result.get("url", ""),
                        source="tavily",
                        summary=result.get("content", summary)[:300],
                        tag=self._classify(result.get("title", "") + " " + summary),
                        reason=self._why_relevant(result),
                        topics=[topic],
                    ))
        except Exception as e:
            logger.error(f"Tavily fetch failed: {e}")
        return items

    def _fetch_via_httpx(self) -> list[DevItem]:
        """Fallback: basic web search via DuckDuckGo-style scraping."""
        items = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            for topic in TOPICS[:3]:
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(topic)}"
                resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
                if resp.status_code != 200:
                    continue
                import re
                results = re.findall(
                    r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>',
                    resp.text
                )
                for href, title in results[:5]:
                    items.append(DevItem(
                        title=self._clean_html(title),
                        url=href,
                        source="duckduckgo",
                        summary=f"Search result for: {topic}",
                        tag=self._classify(title),
                        reason=self._why_relevant_title(title),
                        topics=[topic],
                    ))
        except Exception as e:
            logger.error(f"HTTPX fetch failed: {e}")
        return items

    def _classify(self, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ("mlx", "apple silicon", "m4", "m3", "mlx-lm", "mlx-community")):
            return "standout"
        if any(w in t for w in ("quantiz", "lora", "fine-tun", "distill", "small model", "4bit")):
            return "relevant"
        return "general"

    def _why_relevant(self, result: dict) -> str:
        title = (result.get("title") or "").lower()
        content = (result.get("content") or "").lower()
        if "mlx" in title or "apple" in title:
            return "Directly affects Kitty's MLX inference stack"
        if "quantiz" in content or "4bit" in content:
            return "Quantization improvements = faster/smaller models for Kitty"
        if "lora" in content or "fine-tun" in content:
            return "LoRA/fine-tuning = personalized models for Kitty"
        if "distill" in title or "small" in title:
            return "Smaller capable models = more specialists for Kitty"
        return "General AI advancement worth tracking"

    def _why_relevant_title(self, title: str) -> str:
        t = title.lower()
        if "mlx" in t:
            return "Directly affects Kitty's MLX inference stack"
        if "apple" in t:
            return "Apple Silicon improvements benefit Kitty directly"
        if "quant" in t or "4bit" in t:
            return "Better quantization = more efficient Kitty models"
        return "General AI development"

    @staticmethod
    def _clean_html(text: str) -> str:
        import re
        return re.sub(r"<[^>]+>", "", text).strip()[:200]


_monitor: Optional[AIDevMonitor] = None

def get_monitor() -> AIDevMonitor:
    global _monitor
    if _monitor is None:
        _monitor = AIDevMonitor()
    return _monitor
