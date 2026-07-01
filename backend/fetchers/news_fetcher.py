import feedparser
import requests
from datetime import datetime, timezone, timedelta
from config import get_settings

settings = get_settings()

RSS_SOURCES = {
    "general": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline",
        "https://www.investing.com/rss/news.rss",
    ],
    "crypto": [
        "https://cointelegraph.com/rss",
        "https://coindesk.com/arc/outboundfeeds/rss/",
    ],
    "thai": [
        "https://www.set.or.th/th/news/rss/news_rss.html",
    ],
}


def fetch_rss_news(symbol: str, max_items: int = 15) -> list[dict]:
    articles = []
    keyword = symbol.replace("-USD", "").replace(".BK", "").upper()

    feeds_to_try = RSS_SOURCES["general"]
    if "BTC" in keyword or "ETH" in keyword or "USD" in keyword:
        feeds_to_try += RSS_SOURCES["crypto"]
    if ".BK" in symbol:
        feeds_to_try += RSS_SOURCES["thai"]

    for url in feeds_to_try:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                if keyword.lower() in title.lower() or keyword.lower() in summary.lower():
                    published = entry.get("published", "")
                    articles.append({
                        "title": title,
                        "summary": summary[:500],
                        "published": published,
                        "source": feed.feed.get("title", url),
                        "link": entry.get("link", ""),
                    })
        except Exception:
            continue

    if not articles:
        for url in feeds_to_try:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    articles.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", entry.get("description", ""))[:500],
                        "published": entry.get("published", ""),
                        "source": feed.feed.get("title", url),
                        "link": entry.get("link", ""),
                    })
            except Exception:
                continue

    return articles[:max_items]


def fetch_newsapi(symbol: str, max_items: int = 10) -> list[dict]:
    if not settings.news_api_key:
        return []
    keyword = symbol.replace("-USD", "").replace(".BK", "")
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": keyword,
            "sortBy": "publishedAt",
            "pageSize": max_items,
            "language": "en",
            "apiKey": settings.news_api_key,
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [
                {
                    "title": a.get("title", ""),
                    "summary": a.get("description", "")[:500],
                    "published": a.get("publishedAt", ""),
                    "source": a.get("source", {}).get("name", ""),
                    "link": a.get("url", ""),
                }
                for a in data.get("articles", [])
            ]
    except Exception:
        pass
    return []


def fetch_all_news(symbol: str) -> list[dict]:
    news = fetch_rss_news(symbol)
    news += fetch_newsapi(symbol)
    seen = set()
    unique = []
    for item in news:
        key = item["title"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:20]
