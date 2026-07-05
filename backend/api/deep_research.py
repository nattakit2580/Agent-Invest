"""Deep Research API — /deep-research endpoint."""
from __future__ import annotations

import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from fetchers.market_fetcher import fetch_market_data
from fetchers.news_fetcher import fetch_all_news
from agents.deep_research_agent import DeepResearchAgent
from agents.orchestrator import Orchestrator
from services.agent_feedback import get_agent_feedback
from services.knowledge_rag import count_documents
from services.kg_rag import get_graph_context, seed_watchlist, get_graph_stats
from services import rag as rag_service

router = APIRouter(prefix="/api", tags=["deep-research"])


class DeepResearchRequest(BaseModel):
    symbol: str = Field(..., description="Ticker symbol e.g. NVDA, BTC-USD")
    timeframe: str = Field("1w", description="1d | 1w | 1m | 3m")
    max_papers: int = Field(5, ge=1, le=10)
    max_filings: int = Field(3, ge=0, le=10)


@router.post("/deep-research")
def deep_research(req: DeepResearchRequest, db: Session = Depends(get_db)):
    """
    Full deep research pipeline:
    1. Fetch market data + news
    2. Fetch arXiv papers + SEC filings → ingest to knowledge DB
    3. Run deep research synthesis
    4. Run standard 4-agent ensemble (with research context injected)
    5. Return combined result with sources cited
    """
    start = time.time()
    symbol = req.symbol.upper()

    # ── Market data + news ────────────────────────────────────────────────
    market_data = fetch_market_data(symbol)
    news = fetch_all_news(symbol)

    # ── Deep research (fetch papers/filings + ingest + synthesize) ────────
    dr_agent = DeepResearchAgent()
    dr_result = dr_agent.research(
        symbol, market_data, news, db,
        max_papers=req.max_papers,
        max_filings=req.max_filings,
    )

    # ── Standard ensemble ─────────────────────────────────────────────────
    # Inject research + graph context into market_data for FundamentalAgent
    from services.knowledge_rag import get_research_context
    research_ctx = get_research_context(symbol, db, k=5)
    graph_ctx = get_graph_context(symbol, db, depth=2)
    market_data_enriched = {
        **market_data,
        "research_context": research_ctx,
        "graph_context": graph_ctx,
    }

    orchestrator = Orchestrator()
    agent_outputs = orchestrator.run_all_agents(symbol, market_data_enriched, news)

    # Add deep_research as an extra agent signal
    agent_outputs["deep_research"] = dr_result

    # RAG similar cases
    similar_cases = rag_service.get_similar_cases(symbol, market_data, agent_outputs, db)

    # Agent feedback / dynamic weights
    agent_fb = get_agent_feedback(db)

    # Synthesis + critic
    result = orchestrator.synthesize(
        symbol, market_data, agent_outputs, req.timeframe, similar_cases, agent_fb
    )

    # ── Attach research metadata ──────────────────────────────────────────
    result["deep_research"] = {
        "papers_found": dr_result.get("papers_found", 0),
        "filings_found": dr_result.get("filings_found", 0),
        "new_docs_indexed": dr_result.get("new_docs_indexed", 0),
        "highlights": dr_result.get("research_highlights", []),
    }
    result["elapsed_seconds"] = round(time.time() - start, 2)

    return result


@router.get("/deep-research/knowledge/stats")
def knowledge_stats(db: Session = Depends(get_db)):
    """Return document counts per source in the knowledge DB."""
    return {
        "knowledge_docs": count_documents(db),
        "knowledge_graph": get_graph_stats(db),
    }


@router.post("/deep-research/knowledge/seed-graph")
def seed_graph(db: Session = Depends(get_db)):
    """Seed the entity graph with known relationships for default watchlist symbols."""
    count = seed_watchlist(db)
    return {"seeded_relationships": count, "graph": get_graph_stats(db)}


@router.get("/deep-research/knowledge/graph/{symbol}")
def get_entity_graph(symbol: str, db: Session = Depends(get_db)):
    """Return the entity graph context for a symbol (as prompt text)."""
    ctx = get_graph_context(symbol.upper(), db, depth=2)
    return {"symbol": symbol.upper(), "context": ctx or "(no graph data — call /seed-graph first)"}


@router.delete("/deep-research/knowledge/{source_id}")
def delete_knowledge_doc(source_id: str, db: Session = Depends(get_db)):
    """Remove a specific knowledge document by its DB id."""
    from models.knowledge import KnowledgeDocument
    doc = db.query(KnowledgeDocument).filter_by(id=source_id).first()
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"deleted": source_id}
