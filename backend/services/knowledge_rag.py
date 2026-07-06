"""Knowledge RAG — index and retrieve research documents (papers, filings, web)."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from models.knowledge import KnowledgeDocument, KnowledgeEmbedding
from models.embedding import PGVECTOR_AVAILABLE
from services.rag import _embed
from config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def ingest_document(
    source: str,
    source_id: str,
    title: str,
    summary: str,
    symbols: list[str],
    *,
    content: str | None = None,
    tags: list[str] | None = None,
    authors: list[str] | None = None,
    form_type: str | None = None,
    link: str | None = None,
    published_at: datetime | None = None,
    db: Session,
) -> KnowledgeDocument | None:
    """
    Insert a knowledge document if not already indexed.
    Returns the document (new or existing), or None on error.
    """
    if not settings.rag_enabled:
        return None
    try:
        existing = (
            db.query(KnowledgeDocument)
            .filter_by(source=source, source_id=source_id)
            .first()
        )
        if existing:
            return existing

        doc = KnowledgeDocument(
            source=source,
            source_id=source_id,
            title=title[:1000],
            summary=(summary or "")[:2000],
            content=(content or summary or "")[:5000],
            symbols=symbols or [],
            tags=tags or [],
            authors=authors or [],
            form_type=form_type,
            link=link,
            published_at=published_at,
        )
        db.add(doc)
        db.flush()  # get doc.id

        # embed title + summary
        embed_text = f"{title}\n{summary or content or ''}"[:1000]
        vector = _embed(embed_text)
        if vector is not None:
            db.add(KnowledgeEmbedding(document_id=doc.id, embedding=vector))

        db.commit()
        return doc
    except Exception as e:
        db.rollback()
        print(f"[knowledge_rag] ingest error ({source}/{source_id}): {e}")
        return None


def ingest_fetched(fetched: dict, symbols: list[str], db: Session) -> int:
    """Batch-ingest a dict returned by fetch_research_for_symbol(). Returns count ingested."""
    count = 0
    for item in fetched.get("papers", []):
        doc = ingest_document(
            source=item["source"],
            source_id=item["source_id"],
            title=item["title"],
            summary=item.get("summary", ""),
            symbols=symbols,
            tags=["finance", "quantitative"],
            authors=item.get("authors", []),
            link=item.get("link"),
            published_at=item.get("published_at"),
            db=db,
        )
        if doc:
            count += 1
    for item in fetched.get("filings", []):
        doc = ingest_document(
            source=item["source"],
            source_id=item["source_id"],
            title=item["title"],
            summary=item.get("summary", ""),
            symbols=symbols,
            form_type=item.get("form_type"),
            link=item.get("link"),
            published_at=item.get("published_at"),
            db=db,
        )
        if doc:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_knowledge(
    query: str,
    symbols: list[str] | None = None,
    db: Session | None = None,
    k: int = 5,
) -> list[dict]:
    """
    Semantic search over knowledge documents.
    Falls back to symbol-filtered keyword search when pgvector is unavailable.
    """
    if not settings.rag_enabled or db is None:
        return []

    if not PGVECTOR_AVAILABLE:
        return _keyword_search(symbols or [], db, k)

    query_embedding = _embed(query)
    if query_embedding is None:
        return _keyword_search(symbols or [], db, k)

    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text("""
        SELECT d.id, d.source, d.title, d.summary, d.symbols, d.link,
               d.published_at, d.form_type,
               1 - (ke.embedding <=> :embedding ::vector) AS similarity
        FROM knowledge_embeddings ke
        JOIN knowledge_documents d ON d.id = ke.document_id
        WHERE ke.embedding IS NOT NULL
        ORDER BY ke.embedding <=> :embedding ::vector
        LIMIT :k
    """)

    try:
        rows = db.execute(sql, {"embedding": embedding_str, "k": k}).fetchall()
    except Exception:
        return _keyword_search(symbols or [], db, k)

    return [
        {
            "id": row.id,
            "source": row.source,
            "title": row.title,
            "summary": (row.summary or "")[:300],
            "symbols": row.symbols or [],
            "link": row.link,
            "published_at": str(row.published_at)[:10] if row.published_at else None,
            "form_type": row.form_type,
            "similarity": round(float(row.similarity), 4),
        }
        for row in rows
    ]


def _keyword_search(symbols: list[str], db: Session, k: int) -> list[dict]:
    """Fallback: return most recent docs that mention any of the symbols."""
    try:
        q = db.query(KnowledgeDocument).order_by(KnowledgeDocument.indexed_at.desc())
        docs = q.limit(k * 3).all()
        matched = [
            d for d in docs
            if any(s in (d.symbols or []) for s in symbols)
        ] or docs
        return [
            {
                "id": d.id,
                "source": d.source,
                "title": d.title,
                "summary": (d.summary or "")[:300],
                "symbols": d.symbols or [],
                "link": d.link,
                "published_at": str(d.published_at)[:10] if d.published_at else None,
                "form_type": d.form_type,
                "similarity": 0.0,
            }
            for d in matched[:k]
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Context builder for agent prompts
# ---------------------------------------------------------------------------

def get_research_context(symbol: str, db: Session, k: int = 5) -> str:
    """
    Return a formatted research context string ready to inject into an LLM prompt.
    Empty string if no documents are available.
    """
    docs = search_knowledge(symbol, symbols=[symbol], db=db, k=k)
    if not docs:
        return ""

    lines = ["RESEARCH & FILINGS CONTEXT:"]
    for doc in docs:
        source_label = doc["source"].upper()
        ft = f" ({doc['form_type']})" if doc.get("form_type") else ""
        date = f" [{doc['published_at']}]" if doc.get("published_at") else ""
        lines.append(f"[{source_label}{ft}{date}] {doc['title']}")
        if doc.get("summary"):
            lines.append(f"  {doc['summary']}")
    return "\n".join(lines)


def count_documents(db: Session) -> dict[str, int]:
    """Return document counts per source (for API/health endpoint)."""
    try:
        rows = db.execute(
            text("SELECT source, COUNT(*) as cnt FROM knowledge_documents GROUP BY source")
        ).fetchall()
        return {row.source: row.cnt for row in rows}
    except Exception:
        return {}
