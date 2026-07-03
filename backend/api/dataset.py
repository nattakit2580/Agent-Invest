"""Dataset collection stats and JSONL export for Phase 4/5."""
import json
import io
from collections import Counter
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models.prediction import Prediction

router = APIRouter(prefix="/dataset", tags=["dataset"])

DATASET_TARGETS = [500, 1000, 2000, 5000]


@router.get("/stats")
def dataset_stats(db: Session = Depends(get_db)):
    """Overall dataset quality stats — used for the collection dashboard."""
    all_preds = db.query(Prediction).all()
    compared = [p for p in all_preds if p.status == "compared"]
    export_ready = [p for p in compared if p.accuracy_score is not None]

    direction_dist = Counter(p.direction for p in compared)
    timeframe_dist = Counter(p.timeframe for p in compared)
    score_buckets: dict[str, int] = {}
    for p in export_ready:
        b = f"{int(p.accuracy_score * 10) / 10:.1f}"
        score_buckets[b] = score_buckets.get(b, 0) + 1

    n_ready = len(export_ready)
    next_target = next((t for t in DATASET_TARGETS if t > n_ready), DATASET_TARGETS[-1])
    progress_pct = round(n_ready / next_target * 100, 1)

    return {
        "total_predictions": len(all_preds),
        "compared": len(compared),
        "export_ready": n_ready,
        "next_target": next_target,
        "progress_pct": progress_pct,
        "direction_distribution": dict(direction_dist),
        "timeframe_distribution": dict(timeframe_dist),
        "accuracy_score_buckets": score_buckets,
        "targets": DATASET_TARGETS,
    }


@router.get("/export")
def export_dataset(
    format: str = Query("jsonl", pattern="^(jsonl|csv)$"),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(5000, le=10000),
    db: Session = Depends(get_db),
):
    """Export training-ready cases as JSONL or CSV."""
    q = (
        db.query(Prediction)
        .filter(Prediction.status == "compared")
        .filter(Prediction.accuracy_score >= min_score)
        .filter(Prediction.accuracy_score.isnot(None))
    )
    if symbol:
        q = q.filter(Prediction.symbol == symbol.upper())
    if timeframe:
        q = q.filter(Prediction.timeframe == timeframe)
    predictions = q.limit(limit).all()

    if format == "jsonl":
        # join closest MarketSnapshot for technical indicators
        from models.prediction import MarketSnapshot
        from sqlalchemy import func

        snapshot_map: dict[str, dict] = {}
        if predictions:
            pred_ids_by_symbol: dict[str, list] = {}
            for p in predictions:
                pred_ids_by_symbol.setdefault(p.symbol, []).append(p)

            for sym, sym_preds in pred_ids_by_symbol.items():
                snaps = (
                    db.query(MarketSnapshot)
                    .filter(MarketSnapshot.symbol == sym)
                    .order_by(MarketSnapshot.fetched_at)
                    .all()
                )
                for p in sym_preds:
                    closest = min(
                        snaps,
                        key=lambda s: abs((s.fetched_at - p.created_at.replace(tzinfo=None)).total_seconds()),
                        default=None,
                    ) if snaps else None
                    snapshot_map[p.id] = {
                        "price": p.current_price,
                        "rsi_14": closest.rsi_14 if closest else None,
                        "macd": closest.macd if closest else None,
                        "macd_signal": closest.macd_signal if closest else None,
                        "sma_20": closest.sma_20 if closest else None,
                        "sma_50": closest.sma_50 if closest else None,
                        "pe_ratio": closest.pe_ratio if closest else None,
                        "volume": closest.volume if closest else None,
                        "market_cap": closest.market_cap if closest else None,
                    }

        lines = []
        for p in predictions:
            record = {
                "id": p.id,
                "symbol": p.symbol,
                "timeframe": p.timeframe,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "market_snapshot": snapshot_map.get(p.id, {"price": p.current_price}),
                "agent_outputs": p.agent_outputs or {},
                "prediction": {
                    "direction": p.direction,
                    "confidence": p.confidence,
                    "target_price": p.target_price,
                    "reasoning": p.reasoning,
                },
                "outcome": {
                    "actual_price": p.actual_price,
                    "actual_direction": p.actual_direction,
                    "accuracy_score": p.accuracy_score,
                    "direction_correct": p.direction == p.actual_direction,
                    "price_error_pct": (
                        round(abs((p.actual_price - p.target_price) / p.current_price) * 100, 4)
                        if p.target_price and p.actual_price and p.current_price
                        else None
                    ),
                },
            }
            lines.append(json.dumps(record, ensure_ascii=False))

        content = "\n".join(lines)
        return Response(
            content=content.encode("utf-8"),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=dataset.jsonl"},
        )

    # CSV fallback
    import pandas as pd
    rows = []
    for p in predictions:
        row = {
            "id": p.id,
            "symbol": p.symbol,
            "timeframe": p.timeframe,
            "created_at": p.created_at,
            "direction": p.direction,
            "actual_direction": p.actual_direction,
            "direction_correct": p.direction == p.actual_direction,
            "confidence": p.confidence,
            "current_price": p.current_price,
            "target_price": p.target_price,
            "actual_price": p.actual_price,
            "accuracy_score": p.accuracy_score,
            "reasoning": p.reasoning,
        }
        for agent_name in ("news", "fundamental", "technical", "sentiment"):
            agent_data = (p.agent_outputs or {}).get(agent_name, {})
            row[f"{agent_name}_direction"] = agent_data.get("direction")
            row[f"{agent_name}_confidence"] = agent_data.get("confidence")
        rows.append(row)

    df = pd.DataFrame(rows)
    csv_content = df.to_csv(index=False, encoding="utf-8-sig")
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dataset.csv"},
    )
