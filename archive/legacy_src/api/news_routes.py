"""Domain News API routes — refresh and browse domain-specific news."""

import logging
from flask import Blueprint, jsonify, request
from src.services.domain_news_monitor import get_domain_news_monitor

logger = logging.getLogger(__name__)

news_bp = Blueprint("news", __name__)


@news_bp.route("/api/news")
def get_news():
    domain = request.args.get("domain")
    limit = int(request.args.get("limit", 5))
    monitor = get_domain_news_monitor()
    if domain:
        items = monitor.get_news(domain, limit=limit)
        return jsonify({"domain": domain, "items": [i.to_dict() for i in items]})
    all_news = monitor.get_all_news()
    result = {
        d: [i.to_dict() for i in items[:limit]]
        for d, items in all_news.items()
    }
    return jsonify(result)


@news_bp.route("/api/news/summary")
def news_summary():
    monitor = get_domain_news_monitor()
    return jsonify(monitor.get_summary())


@news_bp.route("/api/news/refresh", methods=["POST"])
def refresh_news():
    monitor = get_domain_news_monitor()
    monitor.refresh()
    return jsonify({"status": "ok", "summary": monitor.get_summary()})
