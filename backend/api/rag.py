from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models.prediction import Prediction
from services import rag as rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/similar/{prediction_id}")
def get_similar(
    prediction_id: str,
    k: int = Query(5, le=20),
    db: Session = Depends(get_db),
):
    """Return top-k historical cases similar to a given prediction (debug/UI endpoint)."""
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    cases = rag_service.get_similar_cases(
        prediction.symbol,
        {"price": prediction.current_price},
        prediction.agent_outputs,
        db,
        k=k,
    )
    return {"prediction_id": prediction_id, "similar_cases": cases}


@router.post("/index/{prediction_id}")
def reindex(prediction_id: str, db: Session = Depends(get_db)):
    """Force re-embed and index a prediction (useful for backfilling old records)."""
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    from models.embedding import PredictionEmbedding
    existing = db.query(PredictionEmbedding).filter(
        PredictionEmbedding.prediction_id == prediction_id
    ).first()
    if existing:
        db.delete(existing)
        db.commit()

    market_data = {"price": prediction.current_price}
    rag_service.index_prediction(prediction, market_data, db)
    return {"ok": True, "prediction_id": prediction_id}
