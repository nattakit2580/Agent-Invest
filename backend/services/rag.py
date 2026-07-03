"""RAG retriever — embeds predictions and finds similar historical cases."""
import json
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text
from config import get_settings
from models.prediction import Prediction
from models.embedding import PredictionEmbedding, PGVECTOR_AVAILABLE

settings = get_settings()


def _build_text_snapshot(symbol: str, market_data: dict, agent_outputs: dict | None) -> str:
    """Build the text that gets embedded to represent a prediction's context."""
    lines = [f"Symbol: {symbol}"]
    price = market_data.get("price")
    if price:
        lines.append(f"Price: {price}")
    for key in ("rsi_14", "macd", "sma_20", "sma_50", "pe_ratio", "price_change_pct"):
        val = market_data.get(key)
        if val is not None:
            lines.append(f"{key}: {val}")

    for agent_name, data in (agent_outputs or {}).items():
        direction = data.get("direction", "?")
        conf = data.get("confidence", 0)
        summary = data.get("summary", "")[:100]
        lines.append(f"[{agent_name}] {direction} ({conf:.2f}): {summary}")

    return "\n".join(lines)


def _embed(text_input: str) -> list[float] | None:
    """Call embedding API (Jina AI by default, or OpenAI directly)."""
    if not settings.embedding_api_key:
        return None
    try:
        response = httpx.post(
            f"{settings.embedding_base_url.rstrip('/')}/embeddings",
            json={"model": settings.embedding_model, "input": [text_input]},
            headers={
                "Authorization": f"Bearer {settings.embedding_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    except Exception:
        return None


def index_prediction(prediction: Prediction, market_data: dict, db: Session) -> None:
    """Embed a prediction's context and store it for future similarity search."""
    if not PGVECTOR_AVAILABLE or not settings.rag_enabled:
        return

    existing = db.query(PredictionEmbedding).filter(
        PredictionEmbedding.prediction_id == prediction.id
    ).first()
    if existing:
        return

    text_snapshot = _build_text_snapshot(
        prediction.symbol, market_data, prediction.agent_outputs
    )
    embedding = _embed(text_snapshot)

    db.add(PredictionEmbedding(
        prediction_id=prediction.id,
        embedding=embedding,
        text_snapshot=text_snapshot,
    ))
    db.commit()


def get_similar_cases(
    symbol: str,
    market_data: dict,
    agent_outputs: dict | None,
    db: Session,
    k: int | None = None,
) -> list[dict]:
    """
    Find the top-k most similar past predictions that have actual outcomes.
    Returns a list of dicts with symbol, timeframe, direction, actual_direction, accuracy_score, reasoning.
    """
    if not PGVECTOR_AVAILABLE or not settings.rag_enabled:
        return []

    top_k = k or settings.rag_top_k
    text_snapshot = _build_text_snapshot(symbol, market_data, agent_outputs)
    query_embedding = _embed(text_snapshot)
    if query_embedding is None:
        return []

    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text("""
        SELECT p.id, p.symbol, p.timeframe, p.direction, p.actual_direction,
               p.accuracy_score, p.confidence, p.reasoning, p.current_price,
               p.actual_price, p.created_at,
               1 - (pe.embedding <=> :embedding ::vector) AS similarity
        FROM prediction_embeddings pe
        JOIN predictions p ON p.id = pe.prediction_id
        WHERE p.status = 'compared'
          AND p.accuracy_score >= :min_score
          AND pe.embedding IS NOT NULL
        ORDER BY pe.embedding <=> :embedding ::vector
        LIMIT :k
    """)

    rows = db.execute(sql, {
        "embedding": embedding_str,
        "min_score": settings.rag_min_score,
        "k": top_k,
    }).fetchall()

    cases = []
    for row in rows:
        cases.append({
            "symbol": row.symbol,
            "timeframe": row.timeframe,
            "direction": row.direction,
            "actual_direction": row.actual_direction,
            "accuracy_score": row.accuracy_score,
            "confidence": row.confidence,
            "reasoning": (row.reasoning or "")[:200],
            "similarity": round(float(row.similarity), 4),
            "created_at": str(row.created_at)[:10],
        })
    return cases


def format_cases_for_prompt(cases: list[dict]) -> str:
    """Format retrieved cases into a prompt string."""
    if not cases:
        return ""
    lines = ["SIMILAR HISTORICAL CASES (for reference):"]
    for i, c in enumerate(cases, 1):
        outcome = "✓ CORRECT" if c["direction"] == c["actual_direction"] else "✗ WRONG"
        lines.append(
            f"{i}. {c['symbol']} ({c['timeframe']}, {c['created_at']}): "
            f"predicted {c['direction']} → actual {c['actual_direction']} "
            f"[{outcome}, score={c['accuracy_score']:.2f}, sim={c['similarity']:.3f}]"
        )
        if c.get("reasoning"):
            lines.append(f"   Reasoning: {c['reasoning']}")
    return "\n".join(lines)
