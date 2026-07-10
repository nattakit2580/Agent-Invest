from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from collections import defaultdict
from database import get_db
from models.prediction import Prediction
from models.evaluation import EvaluationResult
from models.schemas import AccuracyStats, EvaluationResultResponse, AgentAccuracyItem, CalibrationBucket, DynamicWeightsResponse
from services.agent_feedback import get_agent_feedback, MIN_EVALS_FOR_DYNAMIC

router = APIRouter(prefix="/accuracy", tags=["accuracy"])

AGENT_NAMES = ["news", "fundamental", "technical", "sentiment"]
BUCKETS = ["0.0-0.1", "0.1-0.2", "0.2-0.3", "0.3-0.4", "0.4-0.5",
           "0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-1.0"]


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
            direction_accuracy=0.0, avg_confidence=0.0,
            avg_accuracy_score=0.0, avg_brier_score=None,
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

    evals = (
        db.query(EvaluationResult)
        .filter(EvaluationResult.prediction_id.in_([p.id for p in compared]))
        .all()
    )
    brier_scores = [e.brier_score for e in evals if e.brier_score is not None]
    avg_brier = round(sum(brier_scores) / len(brier_scores), 6) if brier_scores else None

    return AccuracyStats(
        total=total,
        compared=n,
        direction_accuracy=round(hits / n, 4),
        avg_confidence=round(sum(p.confidence for p in compared) / n, 4),
        avg_accuracy_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
        avg_brier_score=avg_brier,
        by_timeframe=fmt(by_tf),
        by_symbol=fmt(by_sym),
    )


@router.get("/agents", response_model=list[AgentAccuracyItem])
def get_agent_accuracy(db: Session = Depends(get_db)):
    """Per-agent direction accuracy across all evaluated predictions."""
    evals = db.query(EvaluationResult).all()
    if not evals:
        return []

    stats: dict[str, dict] = {name: {"total": 0, "hits": 0} for name in AGENT_NAMES}

    for e in evals:
        for agent_name, correct in (e.agent_directions or {}).items():
            if agent_name.startswith("_"):  # internal keys เช่น _critic ไม่ใช่ agent ทายทิศทาง
                continue
            if agent_name not in stats:
                stats[agent_name] = {"total": 0, "hits": 0}
            stats[agent_name]["total"] += 1
            if correct:
                stats[agent_name]["hits"] += 1

    result = []
    for name, v in stats.items():
        if v["total"] == 0:
            continue
        result.append(AgentAccuracyItem(
            agent=name,
            total=v["total"],
            hits=v["hits"],
            direction_accuracy=round(v["hits"] / v["total"], 4),
        ))
    return sorted(result, key=lambda x: x.direction_accuracy, reverse=True)


@router.get("/calibration", response_model=list[CalibrationBucket])
def get_calibration(db: Session = Depends(get_db)):
    """Confidence bucket vs actual hit rate (for calibration curve)."""
    evals = db.query(EvaluationResult).all()
    if not evals:
        return []

    buckets: dict[str, dict] = defaultdict(lambda: {"total": 0, "hits": 0, "avg_confidence": []})

    for e in evals:
        b = e.confidence_bucket
        buckets[b]["total"] += 1
        if e.direction_correct:
            buckets[b]["hits"] += 1

    result = []
    for b in BUCKETS:
        if b not in buckets:
            continue
        v = buckets[b]
        n = v["total"]
        result.append(CalibrationBucket(
            bucket=b,
            total=n,
            hits=v["hits"],
            actual_rate=round(v["hits"] / n, 4) if n else 0.0,
        ))
    return result


@router.get("/weights", response_model=DynamicWeightsResponse)
def get_dynamic_weights(db: Session = Depends(get_db)):
    """Current dynamic agent weights derived from track record."""
    fb = get_agent_feedback(db)
    return DynamicWeightsResponse(
        total_evals=fb["total_evals"],
        dynamic_weights_active=fb["total_evals"] >= MIN_EVALS_FOR_DYNAMIC,
        weights=fb["weights"],
        accuracies=fb["accuracies"],
        prompt_section=fb["prompt_section"],
    )


@router.get("/{prediction_id}", response_model=EvaluationResultResponse)
def get_evaluation(prediction_id: str, db: Session = Depends(get_db)):
    """Full evaluation breakdown for a single prediction."""
    e = db.query(EvaluationResult).filter(
        EvaluationResult.prediction_id == prediction_id
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Evaluation not found — prediction may not be compared yet")
    return e
