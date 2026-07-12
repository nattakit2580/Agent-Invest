"""Price alert CRUD + the scheduler check that fires them."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config import get_settings
from models.alert import PriceAlert


def create_alert(db: Session, telegram_user_id: str, symbol: str, target_price: float,
                 ref_price: float | None) -> PriceAlert:
    """Create an active alert. Direction is derived from target vs the current
    (ref) price: target above now -> fire when price rises to it, and vice versa.
    If ref is unknown, default to 'above'."""
    direction = "below" if (ref_price is not None and target_price < ref_price) else "above"
    row = PriceAlert(
        telegram_user_id=telegram_user_id,
        symbol=symbol.upper(),
        target_price=target_price,
        direction=direction,
        ref_price=ref_price,
        status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_alerts(db: Session, telegram_user_id: str, *, active_only: bool = True) -> list[PriceAlert]:
    q = db.query(PriceAlert).filter(PriceAlert.telegram_user_id == telegram_user_id)
    if active_only:
        q = q.filter(PriceAlert.status == "active")
    return q.order_by(PriceAlert.created_at.desc()).all()


def count_active(db: Session, telegram_user_id: str) -> int:
    return (
        db.query(PriceAlert)
        .filter(PriceAlert.telegram_user_id == telegram_user_id, PriceAlert.status == "active")
        .count()
    )


def remove_alerts_for_symbol(db: Session, telegram_user_id: str, symbol: str) -> int:
    rows = (
        db.query(PriceAlert)
        .filter(
            PriceAlert.telegram_user_id == telegram_user_id,
            PriceAlert.symbol == symbol.upper(),
            PriceAlert.status == "active",
        )
        .all()
    )
    for r in rows:
        db.delete(r)
    db.commit()
    return len(rows)


def _crossed(alert: PriceAlert, price: float) -> bool:
    if alert.direction == "above":
        return price >= alert.target_price
    return price <= alert.target_price


def check_price_alerts() -> int:
    """Scheduler entrypoint: check every active alert, notify the user on a
    crossing, and mark it triggered. Returns how many fired. Groups by symbol so
    each symbol's price is fetched once."""
    from database import SessionLocal
    from fetchers.market_fetcher import fetch_actual_price
    from services.telegram_client import TelegramClient

    settings = get_settings()
    if not settings.telegram_bot_token:
        return 0

    db: Session = SessionLocal()
    fired = 0
    try:
        active = db.query(PriceAlert).filter(PriceAlert.status == "active").all()
        if not active:
            return 0

        by_symbol: dict[str, list[PriceAlert]] = {}
        for a in active:
            by_symbol.setdefault(a.symbol, []).append(a)

        client = TelegramClient()
        now = datetime.now(timezone.utc)
        for symbol, alerts in by_symbol.items():
            price = fetch_actual_price(symbol)
            if price is None:
                continue
            for a in alerts:
                if not _crossed(a, price):
                    continue
                arrow = "🔺" if a.direction == "above" else "🔻"
                msg = (
                    f"{arrow} แจ้งเตือนราคา {a.symbol}\n"
                    f"ถึงเป้าแล้ว: ${price:,.2f} "
                    f"({'≥' if a.direction == 'above' else '≤'} ${a.target_price:,.2f})\n"
                    f"(แจ้งเตือนอัตโนมัติ ไม่ใช่คำแนะนำการลงทุน)"
                )
                try:
                    client.send_message(msg, chat_id=a.telegram_user_id)
                    a.status = "triggered"
                    a.triggered_at = now
                    fired += 1
                except Exception as e:
                    print(f"[Scheduler] alert send error ({a.telegram_user_id}/{a.symbol}): {e}")
        db.commit()
    except Exception as e:
        print(f"[Scheduler] check_price_alerts error: {e}")
        db.rollback()
    finally:
        db.close()
    return fired
