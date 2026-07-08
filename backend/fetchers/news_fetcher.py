import time
import threading
import feedparser
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from config import get_settings

_news_cache: dict[str, tuple[list, float]] = {}
_news_lock = threading.Lock()
_NEWS_TTL = 900  # 15 minutes

settings = get_settings()

# ---------------------------------------------------------------------------
# RSS feed sources
# ---------------------------------------------------------------------------

RSS_SOURCES: dict[str, list[str]] = {
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
    # Chinese and Hong Kong financial news (English-language)
    "china_hk": [
        "https://www.caixinglobal.com/rss/",                          # Caixin Global — China finance (EN)
        "https://www.scmp.com/rss/91/feed",                           # SCMP Business — HK/China (EN)
        "https://www.chinadaily.com.cn/rss/bizchina_rss.xml",         # China Daily Business (EN)
        "https://asia.nikkei.com/rss/feed/nar",                       # Nikkei Asia — Asia coverage (EN)
        "https://www.yicaiglobal.com/rss",                            # Yicai Global — China economy (EN)
    ],
}

# Major Chinese ADRs listed on US exchanges — detected by ticker
_CHINA_ADR_SYMBOLS = frozenset([
    "BABA", "JD", "PDD", "BIDU", "NIO", "XPEV", "LI", "TME", "NTES",
    "BILI", "VIPS", "WB", "IQ", "TIGR", "FUTU", "LUFAX",
    "TCEHY", "TAL", "EDU", "YUMC", "DIDI", "GRAB",
])

# HK-listed stocks: numeric code → company name for RSS keyword matching
_HK_CODE_MAP: dict[str, str] = {
    "0700": "Tencent", "9988": "Alibaba", "3690": "Meituan",
    "1299": "AIA", "0005": "HSBC", "0941": "China Mobile",
    "0883": "CNOOC", "0388": "HKEX", "2318": "Ping An",
    "1810": "Xiaomi", "0175": "Geely", "9618": "JD",
    "9999": "NetEase", "3968": "China Merchants Bank",
    "2628": "China Life", "0386": "Sinopec", "0857": "PetroChina",
    "1093": "CSPC Pharma", "2020": "Anta Sports",
}


def _is_china_hk(symbol: str) -> bool:
    base = symbol.upper().split(".")[0]
    return (
        symbol.upper().endswith(".HK") or
        symbol.upper().endswith(".SS") or
        symbol.upper().endswith(".SZ") or
        base in _CHINA_ADR_SYMBOLS
    )


def _keyword_for_symbol(symbol: str) -> str:
    """Return the best search keyword for a symbol."""
    base = (
        symbol.upper()
        .replace("-USD", "")
        .replace(".BK", "")
        .replace(".SS", "")
        .replace(".SZ", "")
    )
    # HK numeric codes → company name
    if symbol.upper().endswith(".HK"):
        code = base.replace(".HK", "").lstrip("0") or "0"
        padded = base.replace(".HK", "")
        return _HK_CODE_MAP.get(padded, _HK_CODE_MAP.get(code, base))
    return base


# ---------------------------------------------------------------------------
# RSS
# ---------------------------------------------------------------------------

def fetch_rss_news(symbol: str, max_items: int = 15) -> list[dict]:
    keyword = _keyword_for_symbol(symbol)

    feeds_to_try = list(RSS_SOURCES["general"])
    sym_upper = symbol.upper()
    if any(x in keyword for x in ("BTC", "ETH")) or sym_upper.endswith("-USD"):
        feeds_to_try += RSS_SOURCES["crypto"]
    if sym_upper.endswith(".BK"):
        feeds_to_try += RSS_SOURCES["thai"]
    if _is_china_hk(symbol):
        feeds_to_try += RSS_SOURCES["china_hk"]

    articles = []
    for url in feeds_to_try:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                if keyword.lower() in title.lower() or keyword.lower() in summary.lower():
                    articles.append({
                        "title": title,
                        "summary": summary[:500],
                        "published": entry.get("published", ""),
                        "source": feed.feed.get("title", url),
                        "link": entry.get("link", ""),
                    })
        except Exception:
            continue

    # fallback: take top items if no keyword match
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


# ---------------------------------------------------------------------------
# NewsAPI
# ---------------------------------------------------------------------------

def fetch_newsapi(symbol: str, max_items: int = 10) -> list[dict]:
    if not settings.news_api_key:
        return []
    keyword = _keyword_for_symbol(symbol)
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": keyword,
                "sortBy": "publishedAt",
                "pageSize": max_items,
                "language": "en",
                "apiKey": settings.news_api_key,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return [
                {
                    "title": a.get("title", ""),
                    "summary": (a.get("description") or "")[:500],
                    "published": a.get("publishedAt", ""),
                    "source": a.get("source", {}).get("name", "NewsAPI"),
                    "link": a.get("url", ""),
                }
                for a in resp.json().get("articles", [])
            ]
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Alpha Vantage News & Sentiment  (free: 25 req/day)
# ---------------------------------------------------------------------------

def fetch_alphavantage_news(symbol: str, max_items: int = 10) -> list[dict]:
    """Returns news items with embedded sentiment label + score."""
    if not settings.alpha_vantage_api_key:
        return []
    ticker = _keyword_for_symbol(symbol)
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "limit": max_items,
                "apikey": settings.alpha_vantage_api_key,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        results = []
        for item in resp.json().get("feed", [])[:max_items]:
            sentiment = item.get("overall_sentiment_label", "")
            score = item.get("overall_sentiment_score", "")
            body = (item.get("summary") or "")
            if sentiment:
                body = f"[{sentiment} {score}] {body}"
            results.append({
                "title": item.get("title", ""),
                "summary": body[:500],
                "published": item.get("time_published", ""),
                "source": f"AlphaVantage/{item.get('source', '')}",
                "link": item.get("url", ""),
            })
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Finnhub Company News  (free: 60 calls/min)
# ---------------------------------------------------------------------------

def fetch_finnhub_news(symbol: str, max_items: int = 10) -> list[dict]:
    if not settings.finnhub_api_key:
        return []
    ticker = _keyword_for_symbol(symbol)
    # Finnhub only accepts plain US tickers (no dots/dashes); skip otherwise
    if not ticker.isalpha():
        return []
    to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": from_date, "to": to_date, "token": settings.finnhub_api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        items = resp.json()
        if not isinstance(items, list):
            return []
        return [
            {
                "title": item.get("headline", ""),
                "summary": (item.get("summary") or "")[:500],
                "published": datetime.fromtimestamp(
                    item.get("datetime", 0), tz=timezone.utc
                ).isoformat() if item.get("datetime") else "",
                "source": f"Finnhub/{item.get('source', '')}",
                "link": item.get("url", ""),
            }
            for item in items[:max_items]
            if item.get("headline")
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# SEC EDGAR — recent 8-K filings as breaking news  (no API key needed)
# ---------------------------------------------------------------------------

_EDGAR_NS = "http://www.w3.org/2005/Atom"


def fetch_sec_edgar_news(symbol: str, max_items: int = 5) -> list[dict]:
    """
    Pulls recent 8-K filings (material events) from SEC EDGAR as news items.
    8-K covers: earnings surprises, M&A, CEO changes, product recalls, etc.
    Skips crypto and non-US tickers.
    """
    ticker = symbol.replace("-USD", "").upper()
    if not ticker.isalpha() or len(ticker) > 6:
        return []
    try:
        resp = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar",
            params={
                "action": "getcompany",
                "CIK": ticker,
                "type": "8-K",
                "dateb": "",
                "owner": "include",
                "count": str(max_items),
                "output": "atom",
            },
            headers={"User-Agent": "agent-invest contact@agent-invest.local"},
            timeout=12,
        )
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        results = []
        for entry in root.findall(f"{{{_EDGAR_NS}}}entry")[:max_items]:
            def _text(tag: str) -> str:
                el = entry.find(f"{{{_EDGAR_NS}}}{tag}")
                return el.text.strip() if el is not None and el.text else ""

            title = _text("title")
            if not title:
                continue
            link_el = entry.find(f"{{{_EDGAR_NS}}}link")
            results.append({
                "title": f"[SEC 8-K] {ticker}: {title}",
                "summary": _text("summary")[:500],
                "published": _text("updated"),
                "source": "SEC EDGAR",
                "link": link_el.get("href", "") if link_el is not None else "",
            })
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def fetch_all_news(symbol: str) -> list[dict]:
    key = symbol.upper()
    with _news_lock:
        if key in _news_cache:
            cached, ts = _news_cache[key]
            if time.time() - ts < _NEWS_TTL:
                return cached

    news: list[dict] = []
    news += fetch_rss_news(symbol)
    news += fetch_sec_edgar_news(symbol)
    news += fetch_alphavantage_news(symbol)
    news += fetch_finnhub_news(symbol)
    news += fetch_newsapi(symbol)

    seen: set[str] = set()
    unique: list[dict] = []
    for item in news:
        k = (item.get("title") or "")[:60]
        if k and k not in seen:
            seen.add(k)
            unique.append(item)
    result = unique[:25]

    with _news_lock:
        _news_cache[key] = (result, time.time())
    return result
