from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import yfinance as yf

from config import get_settings
from fetchers.agenda_fetcher import load_ipo_watchlist, split_csv


def _to_iso_date(value: Any) -> str | None:
    """Normalize a yfinance date-ish value to 'YYYY-MM-DD'."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()[:10]
        try:
            datetime.strptime(text, "%Y-%m-%d")
            return text
        except ValueError:
            return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def _earliest_future(dates: list[str], today: str) -> str | None:
    future = sorted(d for d in dates if d and d >= today)
    return future[0] if future else None


def fetch_symbol_events(symbol: str, today: str) -> list[dict[str, Any]]:
    """Earnings + ex-dividend events for one symbol via yfinance calendar."""
    events: list[dict[str, Any]] = []
    try:
        calendar = yf.Ticker(symbol).calendar or {}
    except Exception:
        return events

    if not isinstance(calendar, dict):
        return events

    earnings_raw = calendar.get("Earnings Date")
    if earnings_raw is not None:
        if not isinstance(earnings_raw, (list, tuple)):
            earnings_raw = [earnings_raw]
        earnings_dates = [d for d in (_to_iso_date(x) for x in earnings_raw) if d]
        next_earnings = _earliest_future(earnings_dates, today)
        if next_earnings:
            events.append(
                {
                    "event_type": "earnings",
                    "symbol": symbol,
                    "title": f"{symbol} earnings release",
                    "event_date": next_earnings,
                    "source": "yfinance",
                    "extra": {"all_dates": earnings_dates},
                }
            )

    ex_div = _to_iso_date(calendar.get("Ex-Dividend Date"))
    if ex_div and ex_div >= today:
        events.append(
            {
                "event_type": "dividend",
                "symbol": symbol,
                "title": f"{symbol} ex-dividend date",
                "event_date": ex_div,
                "source": "yfinance",
                "extra": {"dividend_date": _to_iso_date(calendar.get("Dividend Date"))},
            }
        )

    return events


def fetch_ipo_events(today: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in load_ipo_watchlist():
        event_date = _to_iso_date(item.get("expected_date"))
        if not event_date or event_date < today:
            continue
        company = item.get("company") or "IPO"
        events.append(
            {
                "event_type": "ipo",
                "symbol": item.get("symbol"),
                "title": f"IPO: {company} ({item.get('exchange') or 'exchange n/a'})",
                "event_date": event_date,
                "source": item.get("source", "ipo_watchlist"),
                "extra": {"status": item.get("status"), "link": item.get("link")},
            }
        )
    return events


def fetch_all_calendar_events(symbols: list[str] | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    requested = symbols or split_csv(settings.monitor_watchlist_symbols)
    today = datetime.now(timezone.utc).date().isoformat()

    events: list[dict[str, Any]] = []
    for raw_symbol in requested:
        symbol = raw_symbol.strip().upper()
        if not symbol:
            continue
        events.extend(fetch_symbol_events(symbol, today))
    events.extend(fetch_ipo_events(today))
    # NOTE: economic-release dates (FRED release calendar) are not yet wired in — TODO fill later.
    return events


def _dedupe_key(event: dict[str, Any]) -> str:
    return f"{event['event_type']}:{event.get('symbol') or '-'}:{event['event_date']}"


def refresh_calendar_events(symbols: list[str] | None = None) -> int:
    """Fetch upcoming events and upsert into the DB. Returns number of rows touched."""
    from database import SessionLocal
    from models.prediction import CalendarEvent

    events = fetch_all_calendar_events(symbols)
    if not events:
        return 0

    db = SessionLocal()
    touched = 0
    try:
        now = datetime.now(timezone.utc)
        for event in events:
            key = _dedupe_key(event)
            row = db.query(CalendarEvent).filter(CalendarEvent.dedupe_key == key).first()
            if row is None:
                row = CalendarEvent(dedupe_key=key, event_type=event["event_type"])
                db.add(row)
            row.symbol = event.get("symbol")
            row.title = event["title"]
            row.event_date = event["event_date"]
            row.source = event.get("source")
            row.extra = event.get("extra")
            row.updated_at = now
            touched += 1
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"[calendar_fetcher] refresh error: {exc}")
    finally:
        db.close()
    return touched


def get_upcoming_events(days_ahead: int | None = None) -> list[dict[str, Any]]:
    """Read upcoming events (from today up to N days ahead) from the DB, sorted by date."""
    from database import SessionLocal
    from models.prediction import CalendarEvent

    settings = get_settings()
    window = settings.calendar_report_days_ahead if days_ahead is None else days_ahead
    today = datetime.now(timezone.utc).date()
    limit_date = (today.toordinal() + window)
    today_iso = today.isoformat()

    db = SessionLocal()
    try:
        rows = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.event_date >= today_iso)
            .order_by(CalendarEvent.event_date.asc())
            .all()
        )
    except Exception:
        return []
    finally:
        db.close()

    items: list[dict[str, Any]] = []
    for row in rows:
        try:
            event_ord = datetime.strptime(row.event_date, "%Y-%m-%d").date().toordinal()
        except ValueError:
            continue
        if event_ord > limit_date:
            continue
        items.append(
            {
                "event_type": row.event_type,
                "symbol": row.symbol,
                "title": row.title,
                "event_date": row.event_date,
                "days_until": event_ord - today.toordinal(),
                "source": row.source,
                "notified_at": row.notified_at.isoformat() if row.notified_at else None,
            }
        )
    return items
