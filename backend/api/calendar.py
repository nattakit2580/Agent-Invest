from __future__ import annotations

from fastapi import APIRouter, Query

from fetchers.calendar_fetcher import get_upcoming_events, refresh_calendar_events

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events")
def list_events(days_ahead: int = Query(14, ge=1, le=180)):
    events = get_upcoming_events(days_ahead=days_ahead)
    return {"count": len(events), "days_ahead": days_ahead, "events": events}


@router.post("/refresh")
def refresh_events():
    touched = refresh_calendar_events()
    return {"touched": touched, "events": get_upcoming_events()}
