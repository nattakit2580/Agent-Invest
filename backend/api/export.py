import io
import pandas as pd
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models.prediction import Prediction

router = APIRouter(prefix="/export", tags=["export"])


def _predictions_to_df(predictions: list[Prediction]) -> pd.DataFrame:
    rows = []
    for p in predictions:
        rows.append({
            "ID": p.id,
            "Symbol": p.symbol,
            "Created At": p.created_at,
            "Timeframe": p.timeframe,
            "Direction": p.direction,
            "Entry Price": p.current_price,
            "Target Price": p.target_price,
            "Confidence": p.confidence,
            "Reasoning": p.reasoning,
            "Actual Price": p.actual_price,
            "Actual Direction": p.actual_direction,
            "Accuracy Score": p.accuracy_score,
            "Compared At": p.compared_at,
            "Status": p.status,
        })
    return pd.DataFrame(rows)


@router.get("/csv")
def export_csv(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Prediction)
    if symbol:
        q = q.filter(Prediction.symbol == symbol.upper())
    if timeframe:
        q = q.filter(Prediction.timeframe == timeframe)
    if status:
        q = q.filter(Prediction.status == status)
    predictions = q.all()

    df = _predictions_to_df(predictions)
    csv_content = df.to_csv(index=False, encoding="utf-8-sig")

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictions.csv"},
    )


@router.get("/excel")
def export_excel(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Prediction)
    if symbol:
        q = q.filter(Prediction.symbol == symbol.upper())
    if timeframe:
        q = q.filter(Prediction.timeframe == timeframe)
    if status:
        q = q.filter(Prediction.status == status)
    predictions = q.all()

    df = _predictions_to_df(predictions)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Predictions", index=False)

        if predictions:
            compared = [p for p in predictions if p.status == "compared"]
            if compared:
                summary_rows = []
                symbols = set(p.symbol for p in compared)
                for sym in symbols:
                    sym_preds = [p for p in compared if p.symbol == sym]
                    hits = sum(1 for p in sym_preds if p.direction == p.actual_direction)
                    scores = [p.accuracy_score for p in sym_preds if p.accuracy_score]
                    summary_rows.append({
                        "Symbol": sym,
                        "Total Predictions": len(sym_preds),
                        "Direction Accuracy": round(hits / len(sym_preds), 4),
                        "Avg Accuracy Score": round(sum(scores) / len(scores), 4) if scores else 0,
                    })
                pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Accuracy Summary", index=False)

    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=predictions.xlsx"},
    )
