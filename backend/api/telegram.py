from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.admin import require_admin as require_admin_password
from config import get_settings
from database import get_db
from fetchers.agenda_fetcher import split_csv
from models.prediction import MonitorReport
from models.schemas import (
    MonitorReportResponse,
    TelegramAnalyticsResponse,
    TelegramBroadcastRequest,
    TelegramReportPreviewResponse,
    TelegramReportRequest,
    TelegramStatusResponse,
    TelegramWebhookRegisterRequest,
)
from services.monitor_report import build_daily_monitor_report, render_public_monitor_message
from services.telegram_bot import build_telegram_analytics, handle_telegram_update
from services.telegram_client import TelegramClient, TelegramNotConfiguredError, TelegramSendError

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _create_report_row(
    db: Session,
    report: dict,
    *,
    status: str,
    channel_id: str | None,
    report_type: str = "daily_monitor",
    message: str | None = None,
    error: str | None = None,
    sent_at: datetime | None = None,
) -> MonitorReport:
    row = MonitorReport(
        report_date=report["report_date"],
        report_type=report_type,
        channel_id=channel_id,
        title=report["title"],
        categories=report.get("categories"),
        watchlist=report.get("watchlist"),
        ipo_agenda=report.get("ipo_agenda"),
        message=message or report["message"],
        status=status,
        sent_at=sent_at,
        error=error,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _require_admin(x_admin_token: str | None = Header(None, alias="X-Admin-Token")) -> None:
    settings = get_settings()
    # Fail closed: if no admin token is configured, reject every request rather
    # than letting these write/broadcast routes run unauthenticated.
    if not settings.telegram_admin_token:
        raise HTTPException(
            status_code=503,
            detail="X-Admin-Token auth is not configured on the server (set TELEGRAM_ADMIN_TOKEN).",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.telegram_admin_token):
        raise HTTPException(status_code=401, detail="Invalid X-Admin-Token")


def _verify_webhook_secret(secret_header: str | None) -> None:
    settings = get_settings()
    # Fail closed: an unconfigured secret must not mean "accept anything", or an
    # attacker could POST forged Telegram updates with an arbitrary from.id and
    # act as any user (portfolio/watchlist are keyed solely on that id).
    if not settings.telegram_webhook_secret_token:
        raise HTTPException(
            status_code=503,
            detail="Telegram webhook secret is not configured (set TELEGRAM_WEBHOOK_SECRET_TOKEN).",
        )
    if not secret_header or not secrets.compare_digest(secret_header, settings.telegram_webhook_secret_token):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret token")


def _chat_id_for_target(req: TelegramBroadcastRequest) -> tuple[str, str]:
    settings = get_settings()
    target = (req.target or "channel").lower()
    if req.chat_id:
        return req.chat_id, target
    if target == "channel":
        return settings.telegram_channel_id, target
    if target == "community":
        return settings.telegram_community_chat_id, target
    if target == "paid":
        return settings.telegram_paid_chat_id, target
    raise HTTPException(status_code=400, detail="target must be channel, community, or paid")


@router.get("/status", response_model=TelegramStatusResponse)
def telegram_status():
    settings = get_settings()
    client_status = TelegramClient().status()
    watchlist = split_csv(settings.monitor_watchlist_symbols)
    indicators = split_csv(settings.monitor_economic_indicators)
    return TelegramStatusResponse(
        configured=client_status.configured,
        bot_configured=client_status.bot_configured,
        channel_id=client_status.channel_id,
        community_chat_id=client_status.community_chat_id,
        paid_chat_id=client_status.paid_chat_id,
        daily_report_enabled=client_status.daily_report_enabled,
        community_report_enabled=client_status.community_report_enabled,
        paid_report_enabled=client_status.paid_report_enabled,
        daily_report_time=f"{settings.telegram_daily_report_hour:02d}:{settings.telegram_daily_report_minute:02d}",
        timezone=settings.telegram_timezone,
        watchlist_count=len(watchlist),
        economic_indicator_count=len(indicators),
        webhook_secret_configured=bool(settings.telegram_webhook_secret_token),
        admin_token_configured=bool(settings.telegram_admin_token),
    )


@router.post(
    "/reports/preview",
    response_model=TelegramReportPreviewResponse,
    dependencies=[Depends(_require_admin)],
)
def preview_daily_report(req: TelegramReportRequest):
    return build_daily_monitor_report(
        symbols=req.symbols,
        max_news_items=req.max_news_items,
        max_assets=req.max_assets,
        use_ai=req.use_ai,
    )


@router.post(
    "/reports/send",
    response_model=MonitorReportResponse,
    dependencies=[Depends(_require_admin)],
)
def send_daily_report(req: TelegramReportRequest, db: Session = Depends(get_db)):
    client = TelegramClient()
    if not client.configured:
        raise HTTPException(
            status_code=400,
            detail="TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID are required before sending.",
        )

    report = build_daily_monitor_report(
        symbols=req.symbols,
        max_news_items=req.max_news_items,
        max_assets=req.max_assets,
        use_ai=req.use_ai,
    )
    row = _create_report_row(db, report, status="pending", channel_id=client.channel_id)

    try:
        client.send_message(report["message"])
    except TelegramNotConfiguredError as exc:
        row.status = "failed"
        row.error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc))
    except TelegramSendError as exc:
        row.status = "failed"
        row.error = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc))

    row.status = "sent"
    row.sent_at = datetime.now(timezone.utc)
    row.error = None
    db.commit()
    db.refresh(row)
    return row


@router.post("/broadcast", response_model=MonitorReportResponse, dependencies=[Depends(_require_admin)])
def send_broadcast(req: TelegramBroadcastRequest, db: Session = Depends(get_db)):
    client = TelegramClient()
    if not client.bot_configured:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is required before sending.")

    chat_id, target = _chat_id_for_target(req)
    if not chat_id:
        raise HTTPException(status_code=400, detail=f"No Telegram chat id configured for target '{target}'.")

    if req.message:
        message = req.message
        now = datetime.now(timezone.utc)
        report = {
            "report_date": now.date().isoformat(),
            "title": "Telegram Manual Broadcast",
            "categories": {},
            "watchlist": [],
            "ipo_agenda": [],
            "message": message,
        }
    else:
        report = build_daily_monitor_report(use_ai=req.use_ai)
        message = render_public_monitor_message(report) if req.public_preview or target == "community" else report["message"]

    row = _create_report_row(
        db,
        report,
        status="pending",
        channel_id=chat_id,
        report_type=f"{target}_broadcast",
        message=message,
    )
    try:
        client.send_message(message, chat_id=chat_id)
    except TelegramNotConfiguredError as exc:
        row.status = "failed"
        row.error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc))
    except TelegramSendError as exc:
        row.status = "failed"
        row.error = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc))

    row.status = "sent"
    row.sent_at = datetime.now(timezone.utc)
    row.error = None
    db.commit()
    db.refresh(row)
    return row


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_telegram_bot_api_secret_token: str | None = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    _verify_webhook_secret(x_telegram_bot_api_secret_token)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    return handle_telegram_update(payload, db)


@router.post("/webhook/register", dependencies=[Depends(_require_admin)])
def register_webhook(req: TelegramWebhookRegisterRequest):
    settings = get_settings()
    client = TelegramClient()
    if not client.bot_configured:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is required before registering webhook.")
    try:
        return client.set_webhook(
            req.webhook_url,
            secret_token=settings.telegram_webhook_secret_token or None,
            drop_pending_updates=req.drop_pending_updates,
        )
    except TelegramSendError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/webhook/delete", dependencies=[Depends(_require_admin)])
def delete_webhook(drop_pending_updates: bool = False):
    client = TelegramClient()
    if not client.bot_configured:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is required before deleting webhook.")
    try:
        return client.delete_webhook(drop_pending_updates=drop_pending_updates)
    except TelegramSendError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/webhook/info", dependencies=[Depends(_require_admin)])
def webhook_info():
    client = TelegramClient()
    if not client.bot_configured:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is required before reading webhook info.")
    try:
        return client.get_webhook_info()
    except TelegramSendError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get(
    "/analytics",
    response_model=TelegramAnalyticsResponse,
    dependencies=[Depends(require_admin_password)],
)
def telegram_analytics(
    days: int = Query(7, ge=1, le=365),
    chat_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return build_telegram_analytics(db, days=days, chat_id=chat_id, limit=limit)


@router.get(
    "/reports",
    response_model=list[MonitorReportResponse],
    dependencies=[Depends(require_admin_password)],
)
def list_monitor_reports(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    query = db.query(MonitorReport).order_by(desc(MonitorReport.created_at))
    if status:
        query = query.filter(MonitorReport.status == status)
    return query.offset(offset).limit(limit).all()


@router.get(
    "/reports/{report_id}",
    response_model=MonitorReportResponse,
    dependencies=[Depends(require_admin_password)],
)
def get_monitor_report(report_id: str, db: Session = Depends(get_db)):
    row = db.query(MonitorReport).filter(MonitorReport.id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Monitor report not found")
    return row
