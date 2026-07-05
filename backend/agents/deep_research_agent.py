"""Deep Research Agent — multi-step: fetch papers/filings → ingest → synthesize insights."""
from __future__ import annotations

from sqlalchemy.orm import Session

from agents.base_agent import BaseAgent
from fetchers.research_fetcher import fetch_research_for_symbol
from services.knowledge_rag import ingest_fetched, get_research_context


class DeepResearchAgent(BaseAgent):
    name = "deep_research"

    def research(
        self,
        symbol: str,
        market_data: dict,
        news: list[dict],
        db: Session,
        *,
        max_papers: int = 5,
        max_filings: int = 3,
    ) -> dict:
        """
        Full pipeline:
        1. Fetch arXiv papers + SEC filings
        2. Ingest into knowledge DB
        3. Build research context from DB
        4. LLM synthesis → structured investment insight
        """
        sector = market_data.get("sector", "")

        # ── Step 1+2: fetch & ingest ──────────────────────────────────────
        fetched = fetch_research_for_symbol(
            symbol, sector=sector,
            max_papers=max_papers,
            max_filings=max_filings,
        )
        new_docs = ingest_fetched(fetched, symbols=[symbol], db=db)

        papers_found = len(fetched.get("papers", []))
        filings_found = len(fetched.get("filings", []))

        # ── Step 3: pull research context from DB ─────────────────────────
        research_context = get_research_context(symbol, db, k=max_papers)

        # ── Step 4: LLM synthesis ─────────────────────────────────────────
        if not research_context:
            research_context = "ไม่พบเอกสารวิจัยหรือรายงาน SEC ที่เกี่ยวข้อง"

        news_headlines = "\n".join(
            f"- {n.get('title', '')}" for n in news[:5]
        )

        system = (
            "You are a quantitative research analyst with deep expertise in academic finance. "
            "Return ONLY valid JSON. No markdown. "
            "Write all text fields (summary, key_points, research_highlights) in Thai language. "
            "Keep JSON keys, direction values (bullish/bearish/neutral), and numbers in English."
        )

        user = f"""Analyze {symbol} using the research documents and market data below.

MARKET DATA:
- Price: {market_data.get('price')}
- Change: {market_data.get('price_change_pct')}%
- PE Ratio: {market_data.get('pe_ratio')}
- Sector: {sector or 'n/a'}

RECENT NEWS:
{news_headlines or '(none)'}

{research_context}

Based on the research documents, academic papers, and filings above, provide a research-driven investment assessment.

Return this exact JSON:
{{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": <float 0.0-1.0>,
  "summary": "<2-3 sentence research-based assessment in Thai>",
  "key_points": ["<insight from research 1>", "<insight 2>", "<insight 3>"],
  "research_highlights": ["<key finding from paper/filing 1>", "<finding 2>"],
  "papers_found": {papers_found},
  "filings_found": {filings_found},
  "new_docs_indexed": {new_docs}
}}"""

        try:
            raw = self._call_llm(system, user, max_tokens=1500)
            result = self._parse_json(raw)
            result.setdefault("direction", "neutral")
            result.setdefault("confidence", 0.5)
            result.setdefault("summary", "")
            result.setdefault("key_points", [])
            result.setdefault("research_highlights", [])
            result["papers_found"] = papers_found
            result["filings_found"] = filings_found
            result["new_docs_indexed"] = new_docs
            return result
        except Exception as e:
            return {
                "direction": "neutral",
                "confidence": 0.4,
                "summary": f"วิเคราะห์งานวิจัยไม่สำเร็จ: {str(e)[:100]}",
                "key_points": [],
                "research_highlights": [],
                "papers_found": papers_found,
                "filings_found": filings_found,
                "new_docs_indexed": new_docs,
            }

    # keep standard interface so orchestrator can call it optionally
    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        """Lightweight version without DB — returns empty research insight."""
        return {
            "direction": "neutral",
            "confidence": 0.4,
            "summary": "DeepResearch ต้องการ DB — ใช้ endpoint /deep-research แทน",
            "key_points": [],
        }
