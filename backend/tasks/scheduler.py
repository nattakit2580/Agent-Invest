from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models.prediction import MonitorReport, Prediction
from fetchers.market_fetcher import fetch_actual_price
from services.monitor_report import build_daily_monitor_report, render_public_monitor_message
from services.telegram_client import TelegramClient, TelegramSendError
from utils.accuracy import calc_direction_from_prices, calc_accuracy_score
from config import get_settings

settings = get_settings()

TIMEFRAME_DAYS = {"1d": 1, "1w": 7, "1m": 30, "3m": 90}


def auto_compare_due_predictions():
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        pending = db.query(Prediction).filter(Prediction.status == "pending").all()

        for p in pending:
            days = TIMEFRAME_DAYS.get(p.timeframe, 7)
            due_at = p.created_at.replace(tzinfo=timezone.utc) + timedelta(days=days)
            if now >= due_at:
                actual_price = fetch_actual_price(p.symbol)
                if actual_price is None:
                    continue
                actual_direction = calc_direction_from_prices(p.current_price, actual_price)
                score = calc_accuracy_score(
                    p.direction, actual_direction, p.target_price,
                    actual_price, p.current_price, p.confidence
                )
                p.actual_price = actual_price
                p.actual_direction = actual_direction
                p.accuracy_score = score
                p.compared_at = now
                p.status = "compared"

        db.commit()
    except Exception as e:
        print(f"[Scheduler] auto_compare error: {e}")
    finally:
        db.close()


def _telegram_reporting_enabled() -> bool:
    return any([
        settings.telegram_daily_report_enabled,
        settings.telegram_community_report_enabled,
        settings.telegram_paid_report_enabled,
    ])


def _send_report_to_chat(
    db: Session,
    client: TelegramClient,
    report: dict,
    *,
    chat_id: str,
    report_type: str,
    message: str,
) -> None:
    row = MonitorReport(
        report_date=report["report_date"],
        report_type=report_type,
        channel_id=chat_id,
        title=report["title"],
        categories=report["categories"],
        watchlist=report["watchlist"],
        ipo_agenda=report["ipo_agenda"],
        message=message,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        client.send_message(message, chat_id=chat_id)
        row.status = "sent"
        row.sent_at = datetime.now(timezone.utc)
        row.error = None
    except TelegramSendError as e:
        row.status = "failed"
        row.error = str(e)
        print(f"[Scheduler] {report_type} send error: {e}")
    except Exception as e:
        row.status = "failed"
        row.error = str(e)
        print(f"[Scheduler] {report_type} error: {e}")
    finally:
        db.commit()


def send_daily_telegram_monitor():
    if not _telegram_reporting_enabled():
        return

    client = TelegramClient()
    if not client.bot_configured:
        print("[Scheduler] telegram monitor skipped: TELEGRAM_BOT_TOKEN is not configured")
        return

    targets: list[tuple[str, str, bool]] = []
    if settings.telegram_daily_report_enabled and settings.telegram_channel_id:
        targets.append((settings.telegram_channel_id, "daily_monitor", False))
    if settings.telegram_community_report_enabled and settings.telegram_community_chat_id:
        targets.append((settings.telegram_community_chat_id, "community_monitor", True))
    if settings.telegram_paid_report_enabled and settings.telegram_paid_chat_id:
        targets.append((settings.telegram_paid_chat_id, "paid_monitor", False))

    if not targets:
        print("[Scheduler] telegram monitor skipped: no target chat ids configured")
        return

    db: Session = SessionLocal()
    try:
        report = build_daily_monitor_report()
        for chat_id, report_type, public_preview in targets:
            message = render_public_monitor_message(report) if public_preview else report["message"]
            _send_report_to_chat(
                db,
                client,
                report,
                chat_id=chat_id,
                report_type=report_type,
                message=message,
            )
    except Exception as e:
        print(f"[Scheduler] telegram monitor error: {e}")
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        auto_compare_due_predictions,
        trigger=IntervalTrigger(hours=6),
        id="auto_compare",
        replace_existing=True,
    )

    if _telegram_reporting_enabled():
        try:
            trigger = CronTrigger(
                hour=settings.telegram_daily_report_hour,
                minute=settings.telegram_daily_report_minute,
                timezone=settings.telegram_timezone,
            )
        except Exception as e:
            print(f"[Scheduler] invalid Telegram timezone, falling back to UTC: {e}")
            trigger = CronTrigger(
                hour=settings.telegram_daily_report_hour,
                minute=settings.telegram_daily_report_minute,
                timezone="UTC",
            )

        scheduler.add_job(
            send_daily_telegram_monitor,
            trigger=trigger,
            id="telegram_daily_monitor",
            replace_existing=True,
        )

    return scheduler
