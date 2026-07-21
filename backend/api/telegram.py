from __future__ import annotations

import hashlib
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
from services.telegram_client import TelegramClient, TelegramNotConfiguredError, TelegramSendError, normalize_chat_id

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


def _telegram_safe_secret(raw: str) -> str:
    """Telegram's secret_token only allows [A-Za-z0-9_-], 1-256 chars. Render's
    generateValue (or any operator-typed secret) may contain other characters
    (setWebhook then rejects it outright with 'unallowed characters'), so derive
    a guaranteed-compliant token from whatever raw value is configured. Used
    identically on the register side and the incoming-header check, so they
    always agree regardless of what the raw secret actually looks like."""
    return hashlib.sha256(raw.encode()).hexdigest()


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
    expected = _telegram_safe_secret(settings.telegram_webhook_secret_token)
    if not secret_header or not secrets.compare_digest(secret_header, expected):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret token")


def _chat_id_for_target(req: TelegramBroadcastRequest) -> tuple[str, str]:
    settings = get_settings()
    target = (req.target or "channel").lower()
    if req.chat_id:
        return normalize_chat_id(req.chat_id), target
    if target == "channel":
        return normalize_chat_id(settings.telegram_channel_id), target
    if target == "community":
        return normalize_chat_id(settings.telegram_community_chat_id), target
    if target == "paid":
        return normalize_chat_id(settings.telegram_paid_chat_id), target
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
        bot2_configured=client_status.bot2_configured,
        bot2_channel_id=client_status.bot2_channel_id,
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


@router.post("/monitor/run", dependencies=[Depends(_require_admin)])
def run_daily_monitor(force: bool = False, db: Session = Depends(get_db)):
    """Trigger the scheduled daily monitor on demand — the reliable path for a
    Render free-tier deploy where the web service spins down and the in-process
    cron never fires at 08:30. An external scheduler (Render Cron Job) POSTs here
    daily; the wake-up from this very request boots the service, then the send
    runs. send_daily_telegram_monitor() dedups on today's report, so this is safe
    even if the in-process cron/catch-up also fired.

    Returns whether a send happened this call and today's report status so the
    caller (and logs) can see the outcome."""
    from tasks.scheduler import send_daily_telegram_monitor, _already_sent_today, _local_today

    already = _already_sent_today(db)
    if already and not force:
        return {"ok": True, "sent_now": False, "already_sent_today": True, "report_date": _local_today()}

    send_daily_telegram_monitor(force=force)

    db.expire_all()  # re-read after the send wrote its MonitorReport rows
    today = _local_today()

    def _latest(report_type: str) -> dict | None:
        row = (
            db.query(MonitorReport)
            .filter(MonitorReport.report_date == today, MonitorReport.report_type == report_type)
            .order_by(desc(MonitorReport.created_at))
            .first()
        )
        if not row:
            return None
        return {"status": row.status, "error": row.error, "channel_id": row.channel_id}

    settings = get_settings()
    return {
        "ok": True,
        "sent_now": True,
        "forced": force,
        "report_date": today,
        # per-group outcome so you can see all targets in one call
        "group1_bot1": _latest("daily_monitor"),
        "group2_bot2": _latest("bot2_monitor"),
        "bot2_configured": bool(settings.telegram_bot2_token and settings.telegram_bot2_channel_id),
        "community_enabled": bool(
            settings.telegram_community_report_enabled and settings.telegram_community_chat_id
        ),
    }


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


@router.get("/ai-stats", dependencies=[Depends(require_admin_password)])
def ai_chat_stats(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """AI-chat feedback statistics — how many chats, how they were rated, and a
    sample of the low-rated ones so the chat logic/prompt can be improved."""
    from datetime import timedelta
    from models.chat_feedback import AiChatInteraction

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(AiChatInteraction).filter(AiChatInteraction.created_at >= cutoff).all()
    total = len(rows)
    up = sum(1 for r in rows if r.rating == 1)
    down = sum(1 for r in rows if r.rating == -1)
    rated = up + down
    with_symbol = sum(1 for r in rows if r.symbol)
    low = [
        {"question": r.question[:200], "answer": r.answer[:200], "symbol": r.symbol,
         "created_at": r.created_at}
        for r in sorted(rows, key=lambda x: x.created_at, reverse=True)
        if r.rating == -1
    ][:15]
    return {
        "days": days,
        "total_chats": total,
        "rated": rated,
        "thumbs_up": up,
        "thumbs_down": down,
        "satisfaction_pct": round(up / rated * 100, 1) if rated else None,
        "with_symbol_context": with_symbol,
        "recent_low_rated": low,   # ใช้ปรับปรุง prompt/logic
    }


@router.post("/commands/register", dependencies=[Depends(_require_admin)])
def register_commands():
    """(Re)register the "/" command menu across the scopes that actually govern
    what users see, so a stale/empty specific scope can't hide the menu:
      - default
      - all_private_chats  (governs the "/" popup in DMs)
      - all_group_chats
    Also clears any language-specific overrides (th/en) that would win over the
    default, and sets the private-chat Menu button."""
    from services.telegram_bot import BOT_COMMANDS, GROUP_COMMANDS
    client = TelegramClient()
    if not client.bot_configured:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is required.")

    results: dict[str, Any] = {}
    # default + private = full list; groups = curated subset (report-only commands)
    scope_commands = [
        (None, BOT_COMMANDS),
        ({"type": "all_private_chats"}, BOT_COMMANDS),
        ({"type": "all_group_chats"}, GROUP_COMMANDS),
    ]
    try:
        for scope, cmds in scope_commands:
            client.set_my_commands(cmds, scope=scope)
            results[(scope or {}).get("type", "default")] = f"set {len(cmds)}"
        # remove language-specific lists so everyone falls back to the full set
        for lang in ("th", "en"):
            try:
                client.delete_my_commands(language_code=lang)
                client.delete_my_commands(scope={"type": "all_private_chats"}, language_code=lang)
                results[f"cleared_lang_{lang}"] = "ok"
            except Exception:
                results[f"cleared_lang_{lang}"] = "skip"
    except TelegramSendError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    menu_button_ok = True
    try:
        client.set_chat_menu_button()
    except Exception:
        menu_button_ok = False

    return {
        "ok": True,
        "registered": len(BOT_COMMANDS),
        "scopes": results,
        "menu_button_set": menu_button_ok,
        "commands": [c["command"] for c in BOT_COMMANDS],
    }


@router.get("/commands", dependencies=[Depends(_require_admin)])
def get_commands(scope: Optional[str] = Query(None), language_code: Optional[str] = Query(None)):
    """Read the "/" command menu for a scope/language (verification).
    scope: default | all_private_chats | all_group_chats"""
    client = TelegramClient()
    if not client.bot_configured:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is required.")
    scope_obj = {"type": scope} if scope and scope != "default" else None
    try:
        return client.get_my_commands(scope=scope_obj, language_code=language_code)
    except TelegramSendError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/commands/diagnose", dependencies=[Depends(_require_admin)])
def diagnose_commands():
    """One call to find why "/" shows nothing: which bot this token is, and how
    many commands each scope/language currently resolves to."""
    client = TelegramClient()
    if not client.bot_configured:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is required.")

    def _count(**kw):
        try:
            return len(client.get_my_commands(**kw).get("result", []))
        except Exception as e:
            return f"error: {str(e)[:80]}"

    me = {}
    try:
        me = client.get_me().get("result", {})
    except Exception as e:
        me = {"error": str(e)[:100]}

    return {
        "bot": {"username": me.get("username"), "id": me.get("id"), "name": me.get("first_name")},
        "counts": {
            "default": _count(),
            "all_private_chats": _count(scope={"type": "all_private_chats"}),
            "all_group_chats": _count(scope={"type": "all_group_chats"}),
            "default_th": _count(language_code="th"),
            "all_private_chats_th": _count(scope={"type": "all_private_chats"}, language_code="th"),
        },
    }


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
    secret = _telegram_safe_secret(settings.telegram_webhook_secret_token) if settings.telegram_webhook_secret_token else None
    try:
        return client.set_webhook(
            req.webhook_url,
            secret_token=secret,
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
