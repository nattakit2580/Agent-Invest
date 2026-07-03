from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from config import get_settings

FRED_BASE = "https://api.stlouisfed.org/fred"
_TIMEOUT = 15


def parse_series_map(value: str) -> list[tuple[str, str]]:
    """Parse "Label=SERIES_ID,Label=SERIES_ID" into an ordered list of (label, series_id)."""
    pairs: list[tuple[str, str]] = []
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        label, series_id = chunk.split("=", 1)
        label = label.strip()
        series_id = series_id.strip()
        if label and series_id:
            pairs.append((label, series_id))
    return pairs


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, "", "."):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_series_meta(series_id: str, api_key: str) -> dict[str, Any]:
    try:
        resp = requests.get(
            f"{FRED_BASE}/series",
            params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        series = resp.json().get("seriess", [])
        return series[0] if series else {}
    except Exception:
        return {}


def _fetch_series_observations(series_id: str, api_key: str) -> list[dict[str, Any]]:
    resp = requests.get(
        f"{FRED_BASE}/series/observations",
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("observations", [])


def fetch_one_indicator(label: str, series_id: str, api_key: str) -> dict[str, Any] | None:
    """Fetch the latest two valid readings for a single FRED series."""
    observations = _fetch_series_observations(series_id, api_key)
    valid = [
        (obs.get("date"), _to_float(obs.get("value")))
        for obs in observations
        if _to_float(obs.get("value")) is not None
    ]
    if not valid:
        return None

    latest_date, latest_value = valid[0]
    previous_value = valid[1][1] if len(valid) > 1 else None

    change = None
    change_pct = None
    if latest_value is not None and previous_value is not None:
        change = round(latest_value - previous_value, 4)
        if previous_value != 0:
            change_pct = round((change / abs(previous_value)) * 100, 2)

    meta = _fetch_series_meta(series_id, api_key)
    return {
        "label": label,
        "series_id": series_id,
        "value": latest_value,
        "previous_value": previous_value,
        "change": change,
        "change_pct": change_pct,
        "unit": meta.get("units_short") or meta.get("units"),
        "observation_date": latest_date,
    }


def fetch_economic_indicators(persist: bool = True) -> list[dict[str, Any]]:
    """Fetch all configured FRED series. Falls back to the DB cache when no key or on error."""
    settings = get_settings()
    api_key = settings.fred_api_key.strip()
    series = parse_series_map(settings.monitor_fred_series)

    if not api_key:
        return _load_cached_indicators(series)

    results: list[dict[str, Any]] = []
    for label, series_id in series:
        try:
            indicator = fetch_one_indicator(label, series_id, api_key)
        except Exception:
            indicator = None
        if indicator:
            results.append(indicator)

    if not results:
        return _load_cached_indicators(series)

    if persist:
        _persist_indicators(results)
    return results


def _persist_indicators(indicators: list[dict[str, Any]]) -> None:
    from database import SessionLocal
    from models.prediction import EconomicIndicator

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for item in indicators:
            row = (
                db.query(EconomicIndicator)
                .filter(EconomicIndicator.series_id == item["series_id"])
                .first()
            )
            if row is None:
                row = EconomicIndicator(series_id=item["series_id"])
                db.add(row)
            row.label = item["label"]
            row.value = item["value"]
            row.previous_value = item["previous_value"]
            row.change = item["change"]
            row.change_pct = item["change_pct"]
            row.unit = item["unit"]
            row.observation_date = item["observation_date"]
            row.updated_at = now
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"[economic_fetcher] persist error: {exc}")
    finally:
        db.close()


def _load_cached_indicators(series: list[tuple[str, str]]) -> list[dict[str, Any]]:
    from database import SessionLocal
    from models.prediction import EconomicIndicator

    order = {series_id: idx for idx, (_, series_id) in enumerate(series)}
    db = SessionLocal()
    try:
        rows = db.query(EconomicIndicator).all()
    except Exception:
        return []
    finally:
        db.close()

    items = [
        {
            "label": row.label,
            "series_id": row.series_id,
            "value": row.value,
            "previous_value": row.previous_value,
            "change": row.change,
            "change_pct": row.change_pct,
            "unit": row.unit,
            "observation_date": row.observation_date,
        }
        for row in rows
    ]
    items.sort(key=lambda item: order.get(item["series_id"], 999))
    return items
