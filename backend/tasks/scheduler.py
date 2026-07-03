from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models.prediction import MonitorReport, Prediction
from models.evaluation import EvaluationResult
from fetchers.market_fetcher import fetch_actual_price, fetch_market_data
from fetchers.news_fetcher import fetch_all_news
from services.monitor_report import build_daily_monitor_report, render_public_monitor_message
from services.telegram_client import TelegramClient, TelegramSendError, broadcast_parallel
from utils.accuracy import calc_direction_from_prices, calc_accuracy_score, build_evaluation
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
            if now < due_at:
                continue
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

            # save evaluation breakdown
            eval_data = build_evaluation(p, actual_price)
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
    except Exception as e:
        print(f"[Scheduler] auto_compare error: {e}")
    finally:
        db.close()


def auto_analyze_watchlist():
    """Automatically run analysis on watchlist symbols to accumulate dataset."""
    if not settings.auto_analyze_enabled:
        return

    symbols = [s.strip() for s in settings.auto_analyze_symbols.split(",") if s.strip()]
    if not symbols:
        return

    from agents.orchestrator import Orchestrator
    from services import rag as rag_service
    from services.agent_feedback import get_agent_feedback
    orchestrator = Orchestrator()

    db: Session = SessionLocal()
    try:
        agent_fb = get_agent_feedback(db)
        for symbol in symbols:
            try:
                # skip if a pending prediction already exists for this symbol + timeframe
                # created within the last interval to avoid duplicates
                recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.auto_analyze_interval_hours)
                already_exists = db.query(Prediction).filter(
                    Prediction.symbol == symbol,
                    Prediction.timeframe == settings.auto_analyze_timeframe,
                    Prediction.status == "pending",
                    Prediction.created_at >= recent_cutoff,
                ).first()
                if already_exists:
                    continue

                market_data = fetch_market_data(symbol)
                news = fetch_all_news(symbol)
                similar_cases = rag_service.get_similar_cases(symbol, market_data, None, db)
                result = orchestrator.analyze(symbol, market_data, news, settings.auto_analyze_timeframe, similar_cases, agent_fb)

                prediction = Prediction(
                    symbol=symbol,
                    timeframe=settings.auto_analyze_timeframe,
                    direction=result["direction"],
                    current_price=result["current_price"],
                    target_price=result.get("target_price"),
                    confidence=result["confidence"],
                    reasoning=result["reasoning"],
                    agent_outputs=result["agent_outputs"],
                    status="pending",
                )
                db.add(prediction)
                db.commit()
                db.refresh(prediction)
                rag_service.index_prediction(prediction, market_data, db)
                print(f"[Scheduler] auto_analyze: {symbol} → {result['direction']} ({result['confidence']:.2f})")
            except Exception as e:
                print(f"[Scheduler] auto_analyze error for {symbol}: {e}")
                db.rollback()
    finally:
        db.close()


def _telegram_reporting_enabled() -> bool:
    return any([
        settings.telegram_daily_report_enabled,
        settings.telegram_community_report_enabled,
        settings.telegram_paid_report_enabled,
    ])


def _log_and_send_bot2(report: dict, message: str, db: Session) -> None:
    """Bot 2 — ส่งพร้อม log ลง DB (MonitorReport)."""
    if not settings.telegram_bot2_token or not settings.telegram_bot2_channel_id:
        return

    client = TelegramClient(
        bot_token=settings.telegram_bot2_token,
        channel_id=settings.telegram_bot2_channel_id,
    )
    row = MonitorReport(
        report_date=report["report_date"],
        report_type="bot2_monitor",
        channel_id=settings.telegram_bot2_channel_id,
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
        client.send_message(message)
        row.status = "sent"
        row.sent_at = datetime.now(timezone.utc)
        row.error = None
    except (TelegramSendError, Exception) as e:
        row.status = "failed"
        row.error = str(e)
        print(f"[Scheduler] bot2 send error: {e}")
    finally:
        db.commit()


def send_daily_telegram_monitor():
    if not _telegram_reporting_enabled():
        return
    if not settings.telegram_bot_token:
        print("[Scheduler] telegram monitor skipped: TELEGRAM_BOT_TOKEN is not configured")
        return

    db: Session = SessionLocal()
    try:
        report = build_daily_monitor_report()
        message = report["message"]

        # Bot 1 — fire-and-forget (ไม่ log DB)
        results = broadcast_parallel(message, extra_targets=[])
        for label, status in results.items():
            icon = "✓" if status == "ok" else "✗"
            print(f"[Scheduler] {icon} {label} (fire-and-forget): {status}")

        # Bot 2 — log ลง DB
        _log_and_send_bot2(report, message, db)

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

    if settings.auto_analyze_enabled:
        scheduler.add_job(
            auto_analyze_watchlist,
            trigger=IntervalTrigger(hours=settings.auto_analyze_interval_hours),
            id="auto_analyze_watchlist",
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
