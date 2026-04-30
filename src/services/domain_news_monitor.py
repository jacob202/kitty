"""Domain News Monitor — fetches domain-specific news for each specialist."""

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_FILE = DATA_DIR / "domain_news.json"

DOMAIN_TOPICS = {
    "automotive": [
        "automotive recalls Canada",
        "car repair tips maintenance",
        "Honda Ridgeline known issues",
        "automotive diagnostic tools",
        "new car models Canada",
    ],
    "audio": [
        "audio amplifier repair",
        "vintage stereo restoration",
        "Sansui AU-7900",
        "hi-fi news",
        "guitar pedal electronics",
    ],
    "code": [
        "open source AI agent frameworks",
        "Python 3.12 3.13 updates",
        "software development best practices",
        "new programming tools releases",
        "API design patterns",
    ],
    "fitness": [
        "strength training research",
        "fitness science new studies",
        "workout recovery techniques",
        "exercise physiology",
    ],
    "growth": [
        "personal development research",
        "psychology new findings",
        "productivity science",
        "coaching methodology",
    ],
    "design": [
        "product design news",
        "UX research findings",
        "industrial design trends",
        "design tools updates",
    ],
    "creative": [
        "creative arts news",
        "multimedia tools releases",
        "writing craft tips",
        "digital art trends",
    ],
    "infrastructure": [
        "DevOps new tools",
        "cloud security news",
        "infrastructure as code updates",
        "zero trust security",
    ],
    "research": [
        "arXiv machine learning papers",
        "data science new techniques",
        "scientific computing updates",
        "mathematics breakthroughs",
    ],
    "news": [
        "technology news today",
        "open source AI developments",
        "Apple Machine Learning news",
    ],
}


@dataclass
class DomainNewsItem:
    title: str
    url: str
    source: str
    summary: str
    domain: str
    date: str = ""
    score: int = 0

    def to_dict(self):
        return asdict(self)


class DomainNewsMonitor:
    def __init__(self):
        self._items: dict[str, list[DomainNewsItem]] = {}
        self._last_fetch: float = 0
        self._load()

    def _load(self):
        if DATA_FILE.exists():
            try:
                raw = json.loads(DATA_FILE.read_text())
                self._items = {
                    d: [DomainNewsItem(**i) for i in items]
                    for d, items in raw.get("items", {}).items()
                }
                self._last_fetch = raw.get("last_fetch", 0)
            except Exception as e:
                logger.warning(f"Failed to load domain news data: {e}")
                self._items = {}
                self._last_fetch = 0

    def _save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps({
            "last_fetch": self._last_fetch,
            "items": {
                d: [i.to_dict() for i in items]
                for d, items in self._items.items()
            },
        }, indent=2))

    def get_news(self, domain: str, limit: int = 5) -> list[DomainNewsItem]:
        items = self._items.get(domain, [])
        items.sort(key=lambda x: x.date, reverse=True)
        return items[:limit]

    def get_all_news(self) -> dict[str, list[DomainNewsItem]]:
        return self._items

    def get_summary(self) -> dict:
        return {
            "domains": list(self._items.keys()),
            "total": sum(len(v) for v in self._items.values()),
            "last_fetch": datetime.fromtimestamp(self._last_fetch).isoformat() if self._last_fetch else None,
        }

    def fetch_all(self) -> dict[str, list[DomainNewsItem]]:
        for domain in DOMAIN_TOPICS:
            self._fetch_domain(domain)
        self._last_fetch = time.time()
        self._save()
        return self._items

    def refresh(self):
        self.fetch_all()

    def _fetch_domain(self, domain: str):
        topics = DOMAIN_TOPICS.get(domain, [])[:2]
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/[IP_ADDRESS] Safari/537.36"
        }
        items: list[DomainNewsItem] = []
        seen: set[str] = set()

        try:
            for topic in topics:
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(topic)}"
                resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
                if resp.status_code != 200:
                    continue

                results = re.findall(
                    r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>',
                    resp.text
                )
                for href, title in results[:4]:
                    t = re.sub(r"<[^>]+>", "", title).strip()[:150]
                    if t and t not in seen:
                        seen.add(t)
                        items.append(DomainNewsItem(
                            title=t,
                            url=href,
                            source="duckduckgo",
                            summary=f"Search result for: {topic}",
                            domain=domain,
                        ))
        except Exception as e:
            logger.debug(f"Domain news fetch for {domain} failed: {e}")

        if items:
            self._items[domain] = items + self._items.get(domain, [])
            self._items[domain] = self._items[domain][:20]


_monitor: Optional["DomainNewsMonitor"] = None


def get_domain_news_monitor() -> DomainNewsMonitor:
    global _monitor
    if _monitor is None:
        _monitor = DomainNewsMonitor()
    return _monitor
