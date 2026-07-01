from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser

from config import get_settings


CATEGORY_ORDER = [
    "economic_agenda",
    "ipo_agenda",
    "geopolitic_prediction",
    "noteworthy_news",
]

CATEGORY_KEYWORDS = {
    "economic_agenda": [
        "cpi",
        "pce",
        "fomc",
        "fed",
        "rate decision",
        "inflation",
        "jobs report",
        "nonfarm",
        "nfp",
        "gdp",
        "pmi",
        "retail sales",
        "unemployment",
        "jobless claims",
        "ecb",
        "boj",
        "economic calendar",
    ],
    "ipo_agenda": [
        "ipo",
        "initial public offering",
        "listing",
        "public listing",
        "prospectus",
        "bookbuilding",
        "debut",
        "hkex",
        "hong kong listing",
        "nasdaq debut",
        "nyse debut",
        "set ipo",
    ],
    "geopolitic_prediction": [
        "geopolitic",
        "war",
        "sanction",
        "tariff",
        "election",
        "conflict",
        "middle east",
        "china",
        "taiwan",
        "russia",
        "ukraine",
        "opec",
        "oil supply",
    ],
    "noteworthy_news": [
        "earnings",
        "guidance",
        "dividend",
        "buyback",
        "merger",
        "acquisition",
        "upgrade",
        "downgrade",
        "sec",
        "etf",
        "crypto",
        "ai",
    ],
}


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _clean_text(value: str | None, limit: int = 600) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def _article_key(article: dict[str, Any]) -> str:
    title = article.get("title", "")
    link = article.get("link", "")
    return (link or title[:100]).lower()


def _entry_to_article(entry: Any, source: str) -> dict[str, Any]:
    return {
        "title": _clean_text(entry.get("title", ""), 240),
        "summary": _clean_text(entry.get("summary", entry.get("description", "")), 700),
        "published": entry.get("published", entry.get("updated", "")),
        "source": source,
        "link": entry.get("link", ""),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_monitor_articles(max_items: int | None = None, sources: list[str] | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    max_items = max_items or settings.monitor_report_max_news_items
    feed_urls = sources if sources is not None else split_csv(settings.monitor_rss_sources)

    articles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        source = feed.feed.get("title", url) if getattr(feed, "feed", None) else url
        for entry in getattr(feed, "entries", [])[: max_items * 2]:
            article = _entry_to_article(entry, source)
            if not article["title"]:
                continue
            key = _article_key(article)
            if key in seen:
                continue
            seen.add(key)
            articles.append(article)
            if len(articles) >= max_items:
                break
        if len(articles) >= max_items:
            break

    return articles[:max_items]


def classify_articles(articles: list[dict[str, Any]], economic_indicators: list[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    settings = get_settings()
    indicators = economic_indicators or split_csv(settings.monitor_economic_indicators)
    keyword_map = {category: list(words) for category, words in CATEGORY_KEYWORDS.items()}
    keyword_map["economic_agenda"].extend(indicators)

    categories: dict[str, list[dict[str, Any]]] = {category: [] for category in CATEGORY_ORDER}
    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        matched = False
        for category in CATEGORY_ORDER[:-1]:
            if any(keyword.lower() in text for keyword in keyword_map[category]):
                categories[category].append(article)
                matched = True
        if not matched or any(keyword.lower() in text for keyword in keyword_map["noteworthy_news"]):
            categories["noteworthy_news"].append(article)

    return {category: items[:10] for category, items in categories.items()}


def fetch_agenda_categories(max_items: int | None = None) -> dict[str, list[dict[str, Any]]]:
    return classify_articles(fetch_monitor_articles(max_items=max_items))


def load_ipo_watchlist(path: str | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    raw_path = path if path is not None else settings.monitor_ipo_watchlist_path
    if not raw_path:
        return []

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        backend_root = Path(__file__).resolve().parents[1]
        candidate = backend_root / candidate

    if not candidate.exists():
        return []

    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    items: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or item.get("name") or "").strip()
        if not company:
            continue
        items.append(
            {
                "company": company,
                "symbol": item.get("symbol"),
                "exchange": item.get("exchange"),
                "expected_date": item.get("expected_date") or item.get("date"),
                "status": item.get("status", "watching"),
                "summary": item.get("summary", ""),
                "link": item.get("link", ""),
                "source": item.get("source", "manual_watchlist"),
            }
        )
    return items
