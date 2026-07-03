from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import desc

from config import get_settings
from database import SessionLocal
from fetchers.economic_fetcher import fetch_economic_indicators, parse_series_map
from models.prediction import EconomicIndicator

router = APIRouter(prefix="/economic", tags=["economic"])


def _serialize(row: EconomicIndicator) -> dict:
    return {
        "series_id": row.series_id,
        "label": row.label,
        "value": row.value,
        "previous_value": row.previous_value,
        "change": row.change,
        "change_pct": row.change_pct,
        "unit": row.unit,
        "observation_date": row.observation_date,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/indicators")
def list_indicators():
    settings = get_settings()
    order = {sid: i for i, (_, sid) in enumerate(parse_series_map(settings.monitor_fred_series))}
    db = SessionLocal()
    try:
        rows = db.query(EconomicIndicator).order_by(desc(EconomicIndicator.updated_at)).all()
    finally:
        db.close()
    items = [_serialize(row) for row in rows]
    items.sort(key=lambda item: order.get(item["series_id"], 999))
    return {
        "configured": bool(settings.fred_api_key),
        "count": len(items),
        "indicators": items,
    }


@router.post("/refresh")
def refresh_indicators(limit: int = Query(15, ge=1, le=50)):
    indicators = fetch_economic_indicators()[:limit]
    return {"count": len(indicators), "indicators": indicators}
