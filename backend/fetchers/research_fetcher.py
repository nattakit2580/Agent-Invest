"""Fetch research papers (arXiv) and SEC EDGAR filings for a symbol."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx

_ARXIV_BASE = "https://export.arxiv.org/api/query"
_EDGAR_BROWSE = "https://www.sec.gov/cgi-bin/browse-edgar"

_NS = {"atom": "http://www.w3.org/2005/Atom"}
_NS_EDGAR = {
    "atom": "http://www.w3.org/2005/Atom",
    "edgar": "https://www.sec.gov/Archives/edgar/full-index/",
}


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


_SYMBOL_NAME_MAP: dict[str, str] = {
    "NVDA": "NVIDIA",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "TSLA": "Tesla",
    "GOOGL": "Google Alphabet",
    "AMZN": "Amazon",
    "META": "Meta Facebook",
    "NFLX": "Netflix",
    "AMD": "AMD semiconductor",
    "INTC": "Intel",
    "SPY": "S&P 500",
    "QQQ": "NASDAQ technology ETF",
    "BTC-USD": "Bitcoin cryptocurrency",
    "ETH-USD": "Ethereum cryptocurrency",
    "BTCUSDT": "Bitcoin cryptocurrency",
}


def fetch_arxiv_papers(query: str, max_results: int = 5, category: str = "q-fin") -> list[dict]:
    """
    Search arXiv q-fin category for finance/quant papers matching *query*.
    Falls back to all categories if no results found in q-fin.
    Returns list of dicts: {source_id, title, summary, authors, published_at, link}.
    """
    cat_filter = f"cat:{category} AND " if category else ""
    params = {
        "search_query": f"{cat_filter}all:{query}",
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    try:
        resp = httpx.get(_ARXIV_BASE, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[research_fetcher] arXiv error: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return []

    papers: list[dict] = []
    for entry in root.findall("atom:entry", _NS):
        arxiv_id_el = entry.find("atom:id", _NS)
        title_el = entry.find("atom:title", _NS)
        summary_el = entry.find("atom:summary", _NS)
        published_el = entry.find("atom:published", _NS)
        link_el = entry.find("atom:link[@rel='alternate']", _NS)

        arxiv_id = (arxiv_id_el.text or "").strip()
        title = _clean(title_el.text if title_el is not None else "")
        summary = _clean(summary_el.text if summary_el is not None else "")[:1000]
        published_raw = (published_el.text or "").strip() if published_el is not None else ""
        link = link_el.attrib.get("href", "") if link_el is not None else arxiv_id

        authors = [
            _clean(a.findtext("atom:name", default="", namespaces=_NS))
            for a in entry.findall("atom:author", _NS)
        ][:5]

        published_at = None
        if published_raw:
            try:
                published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        if not title:
            continue

        papers.append({
            "source": "arxiv",
            "source_id": arxiv_id,
            "title": title,
            "summary": summary,
            "content": summary,
            "authors": authors,
            "published_at": published_at,
            "link": link,
        })

    # if q-fin returned no results, try without category filter
    if not papers and category:
        return fetch_arxiv_papers(query, max_results=max_results, category="")

    return papers


# ---------------------------------------------------------------------------
# SEC EDGAR
# ---------------------------------------------------------------------------

def _ticker_to_cik_symbol(symbol: str) -> str:
    """Strip crypto suffix (-USD) and return an EDGAR-usable ticker."""
    return symbol.replace("-USD", "").replace("-", "").upper()


def fetch_sec_filings(
    symbol: str,
    form_types: list[str] | None = None,
    max_results: int = 5,
) -> list[dict]:
    """
    Fetch recent SEC EDGAR filings for *symbol* via the EDGAR company browse API.
    Uses Atom feed output — reliable and does not require CIK lookup.
    Returns list of dicts: {source_id, title, summary, form_type, published_at, link}.
    """
    ticker = _ticker_to_cik_symbol(symbol)
    # crypto / FX symbols don't have SEC filings
    if len(ticker) > 6 or not ticker.isalpha():
        return []

    selected_form_types = form_types or ["10-K", "10-Q", "8-K"]
    filings: list[dict] = []

    for form_type in selected_form_types:
        if len(filings) >= max_results:
            break
        params = {
            "company": "",
            "CIK": ticker,
            "type": form_type,
            "dateb": "",
            "owner": "include",
            "count": str(max_results),
            "search_text": "",
            "action": "getcompany",
            "output": "atom",
        }
        try:
            resp = httpx.get(
                _EDGAR_BROWSE,
                params=params,
                timeout=30,
                headers={"User-Agent": "AgentInvest research@agentinvest.ai"},
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"[research_fetcher] SEC EDGAR ({form_type}) error: {e}")
            continue

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            continue

        # EDGAR Atom uses default namespace
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            id_el = entry.find("atom:id", ns)
            title_el = entry.find("atom:title", ns)
            updated_el = entry.find("atom:updated", ns)
            link_el = entry.find("atom:link", ns)
            summary_el = entry.find("atom:summary", ns)

            source_id = (id_el.text or "").strip()
            title = _clean(title_el.text if title_el is not None else "")
            updated_raw = (updated_el.text or "").strip() if updated_el is not None else ""
            link = link_el.attrib.get("href", "") if link_el is not None else ""
            summary_text = _clean(summary_el.text if summary_el is not None else "")

            if not title:
                continue

            published_at = None
            if updated_raw:
                try:
                    published_at = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
                except ValueError:
                    pass

            full_title = f"{ticker} — {form_type}: {title}"
            summary_out = (
                summary_text or
                f"{form_type} filing for {ticker}. Filed: {str(published_at)[:10] if published_at else 'n/a'}."
            )[:500]

            filings.append({
                "source": "sec",
                "source_id": source_id or link,
                "title": full_title[:500],
                "summary": summary_out,
                "content": summary_out,
                "form_type": form_type,
                "published_at": published_at,
                "link": link,
            })

            if len(filings) >= max_results:
                break

    return filings


# ---------------------------------------------------------------------------
# Combined fetch for a symbol
# ---------------------------------------------------------------------------

def fetch_research_for_symbol(
    symbol: str,
    sector: str | None = None,
    max_papers: int = 5,
    max_filings: int = 3,
) -> dict[str, list[dict]]:
    """
    Fetch arXiv papers and SEC filings for *symbol*.
    Does two arXiv passes:
    1. q-fin category — finance/investment papers mentioning the company
    2. CS/all categories — technology papers about the company's domain
    """
    human_name = _SYMBOL_NAME_MAP.get(symbol.upper(), symbol.replace("-USD", ""))

    # Pass 1: q-fin finance papers
    half = max(2, max_papers // 2)
    finance_papers = fetch_arxiv_papers(
        f"{human_name} stock investment",
        max_results=half,
        category="q-fin",
    )

    # Pass 2: domain/technology papers (all categories)
    remaining = max_papers - len(finance_papers)
    domain_papers = []
    if remaining > 0:
        domain_query = human_name
        if sector:
            domain_query = f"{human_name} {sector}"
        domain_papers = fetch_arxiv_papers(
            domain_query,
            max_results=remaining,
            category="",
        )

    # deduplicate by source_id
    seen: set[str] = {p["source_id"] for p in finance_papers}
    combined = finance_papers + [p for p in domain_papers if p["source_id"] not in seen]

    filings = fetch_sec_filings(symbol, max_results=max_filings)
    return {"papers": combined[:max_papers], "filings": filings}
