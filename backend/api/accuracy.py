from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models.prediction import Prediction
from models.schemas import AccuracyStats

router = APIRouter(prefix="/accuracy", tags=["accuracy"])


@router.get("", response_model=AccuracyStats)
def get_accuracy_stats(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Prediction)
    if symbol:
        q = q.filter(Prediction.symbol == symbol.upper())
    if timeframe:
        q = q.filter(Prediction.timeframe == timeframe)
    predictions = q.all()

    total = len(predictions)
    compared = [p for p in predictions if p.status == "compared"]
    n = len(compared)

    if n == 0:
        return AccuracyStats(
            total=total, compared=0,
            direction_accuracy=0.0, avg_confidence=0.0, avg_accuracy_score=0.0,
            by_timeframe={}, by_symbol={}
        )

    hits = sum(1 for p in compared if p.direction == p.actual_direction)

    by_tf: dict[str, dict] = {}
    by_sym: dict[str, dict] = {}

    for p in compared:
        for key, bucket in [(p.timeframe, by_tf), (p.symbol, by_sym)]:
            if key not in bucket:
                bucket[key] = {"total": 0, "hits": 0, "scores": []}
            bucket[key]["total"] += 1
            if p.direction == p.actual_direction:
                bucket[key]["hits"] += 1
            if p.accuracy_score is not None:
                bucket[key]["scores"].append(p.accuracy_score)

    def fmt(bucket: dict) -> dict:
        return {
            k: {
                "total": v["total"],
                "direction_accuracy": round(v["hits"] / v["total"], 4),
                "avg_accuracy_score": round(sum(v["scores"]) / len(v["scores"]), 4) if v["scores"] else 0.0,
            }
            for k, v in bucket.items()
        }

    scores = [p.accuracy_score for p in compared if p.accuracy_score is not None]

    return AccuracyStats(
        total=total,
        compared=n,
        direction_accuracy=round(hits / n, 4),
        avg_confidence=round(sum(p.confidence for p in compared) / n, 4),
        avg_accuracy_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
        by_timeframe=fmt(by_tf),
        by_symbol=fmt(by_sym),
    )
