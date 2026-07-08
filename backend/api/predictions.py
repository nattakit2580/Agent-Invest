from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from database import get_db
from models.prediction import Prediction
from models.evaluation import EvaluationResult
from models.schemas import PredictionResponse, CompareRequest
from fetchers.market_fetcher import fetch_actual_price
from utils.accuracy import calc_direction_from_prices, calc_accuracy_score, build_evaluation
from datetime import datetime, timezone

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("", response_model=list[PredictionResponse])
def list_predictions(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(Prediction).order_by(desc(Prediction.created_at))
    if symbol:
        q = q.filter(Prediction.symbol == symbol.upper())
    if timeframe:
        q = q.filter(Prediction.timeframe == timeframe)
    if status:
        q = q.filter(Prediction.status == status)
    return q.offset(offset).limit(limit).all()


@router.get("/{prediction_id}", response_model=PredictionResponse)
def get_prediction(prediction_id: str, db: Session = Depends(get_db)):
    p = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return p


def _apply_compare(p: Prediction, actual_price: float, db: Session) -> Prediction:
    actual_direction = calc_direction_from_prices(p.current_price, actual_price)
    score = calc_accuracy_score(
        p.direction, actual_direction, p.target_price, actual_price, p.current_price, p.confidence
    )

    p.actual_price = actual_price
    p.actual_direction = actual_direction
    p.accuracy_score = score
    p.compared_at = datetime.now(timezone.utc)
    p.status = "compared"

    eval_data = build_evaluation(p, actual_price)
    eval_data["market_regime"] = p.market_regime
    existing = db.query(EvaluationResult).filter(
        EvaluationResult.prediction_id == p.id
    ).first()
    if existing:
        for k, v in eval_data.items():
            if k != "prediction_id":
                setattr(existing, k, v)
    else:
        db.add(EvaluationResult(**eval_data))

    db.commit()
    db.refresh(p)
    return p


@router.post("/{prediction_id}/compare", response_model=PredictionResponse)
def compare_prediction(prediction_id: str, req: CompareRequest, db: Session = Depends(get_db)):
    p = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return _apply_compare(p, req.actual_price, db)


@router.post("/{prediction_id}/auto-compare", response_model=PredictionResponse)
def auto_compare(prediction_id: str, db: Session = Depends(get_db)):
    p = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prediction not found")

    actual_price = fetch_actual_price(p.symbol)
    if actual_price is None:
        raise HTTPException(status_code=400, detail="Cannot fetch current price")
    return _apply_compare(p, actual_price, db)


@router.delete("/{prediction_id}")
def delete_prediction(prediction_id: str, db: Session = Depends(get_db)):
    p = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prediction not found")
    db.delete(p)
    db.commit()
    return {"ok": True}
