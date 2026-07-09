from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
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

            # save evaluation breakdown (copy market_regime from prediction)
            eval_data = build_evaluation(p, actual_price)
            eval_data["market_regime"] = p.market_regime
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
    from services.market_regime import detect_regime
    orchestrator = Orchestrator()

    db: Session = SessionLocal()
    try:
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
                regime = detect_regime(market_data, news)
                similar_cases = rag_service.get_similar_cases(symbol, market_data, None, db)
                agent_fb = get_agent_feedback(db, regime=regime)
                result = orchestrator.analyze(symbol, market_data, news, settings.auto_analyze_timeframe, similar_cases, agent_fb, regime=regime)

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
                    market_regime=result.get("market_regime"),
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


def _local_today() -> str:
    try:
        tz = ZoneInfo(settings.telegram_timezone)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).date().isoformat()


def _already_sent_today(db: Session) -> bool:
    """เช็คว่ารายงานประจำวันของวันนี้ (เวลาท้องถิ่น) ถูกส่งสำเร็จไปแล้วหรือยัง"""
    return db.query(MonitorReport).filter(
        MonitorReport.report_date == _local_today(),
        MonitorReport.report_type.in_(["daily_monitor", "bot2_monitor"]),
        MonitorReport.status == "sent",
    ).first() is not None


def send_daily_telegram_monitor(force: bool = False):
    if not _telegram_reporting_enabled():
        return
    if not settings.telegram_bot_token:
        print("[Scheduler] telegram monitor skipped: TELEGRAM_BOT_TOKEN is not configured")
        return

    db: Session = SessionLocal()
    try:
        # dedup — กันส่งซ้ำถ้า cron และ catch-up ยิงทับกัน
        if not force and _already_sent_today(db):
            print("[Scheduler] telegram monitor skipped: today's report already sent")
            return

        report = build_daily_monitor_report()
        message = report["message"]

        # Bot 1 — ส่งแล้ว log ลง DB (ใช้เช็ค dedup/catch-up ได้)
        row = MonitorReport(
            report_date=report["report_date"],
            report_type="daily_monitor",
            channel_id=settings.telegram_channel_id,
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

        results = broadcast_parallel(message, extra_targets=[])
        bot1_ok = results.get("bot1") == "ok"
        row.status = "sent" if bot1_ok else "failed"
        row.sent_at = datetime.now(timezone.utc) if bot1_ok else None
        row.error = None if bot1_ok else results.get("bot1", "no target configured")
        db.commit()
        for label, status in results.items():
            icon = "✓" if status == "ok" else "✗"
            print(f"[Scheduler] {icon} {label}: {status}")

        # Bot 2 — log ลง DB
        _log_and_send_bot2(report, message, db)

    except Exception as e:
        print(f"[Scheduler] telegram monitor error: {e}")
    finally:
        db.close()


def catch_up_daily_monitor():
    """รันหลัง server start — ถ้าเลยเวลาส่งของวันนี้แล้วแต่ยังไม่ได้ส่ง (เช่น
    server restart/deploy คร่อมเวลา cron) ให้ส่งย้อนให้เลย จะได้ไม่หายทั้งวัน"""
    if not _telegram_reporting_enabled() or not settings.telegram_bot_token:
        return

    try:
        tz = ZoneInfo(settings.telegram_timezone)
    except Exception:
        tz = timezone.utc
    now_local = datetime.now(tz)
    scheduled_today = now_local.replace(
        hour=settings.telegram_daily_report_hour,
        minute=settings.telegram_daily_report_minute,
        second=0, microsecond=0,
    )
    if now_local < scheduled_today:
        return  # ยังไม่ถึงเวลา — ปล่อยให้ cron ปกติทำงาน

    db: Session = SessionLocal()
    try:
        if _already_sent_today(db):
            return
    finally:
        db.close()

    print("[Scheduler] catch-up: today's report was missed — sending now")
    send_daily_telegram_monitor()


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
            misfire_grace_time=3600,   # ถ้า scheduler ตื่นช้า (server หลับ/โหลดหนัก) ยังยิงได้ภายใน 1 ชม.
            coalesce=True,
        )

        # catch-up หลัง start 90 วินาที — เผื่อ restart คร่อมเวลาส่งของวันนี้
        scheduler.add_job(
            catch_up_daily_monitor,
            trigger=DateTrigger(run_date=datetime.now(timezone.utc) + timedelta(seconds=90)),
            id="telegram_monitor_catchup",
            replace_existing=True,
        )

    return scheduler
