"""Per-user daily quota for rate-limited Telegram features.

A "feature" is a named bucket ("analyze", "graph", ...). Each user gets `limit`
uses per local day; limit <= 0 means unlimited. Owner/whitelisted user ids
(TELEGRAM_UNLIMITED_USER_IDS) are always unlimited so you can test freely.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from config import get_settings
from fetchers.agenda_fetcher import split_csv
from models.usage import UserDailyUsage


@dataclass
class QuotaResult:
    allowed: bool
    used: int          # uses consumed today AFTER this call (or current, if blocked)
    limit: int         # 0 = unlimited
    unlimited: bool = False


def _local_today() -> str:
    settings = get_settings()
    try:
        tz = ZoneInfo(settings.telegram_timezone)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).date().isoformat()


def _is_unlimited_user(telegram_user_id: str) -> bool:
    ids = {s.strip() for s in split_csv(get_settings().telegram_unlimited_user_ids)}
    return telegram_user_id in ids


def peek_quota(db: Session, telegram_user_id: str, feature: str, limit: int) -> QuotaResult:
    """Read current usage without consuming (for status messages)."""
    if limit <= 0 or _is_unlimited_user(telegram_user_id):
        return QuotaResult(allowed=True, used=0, limit=limit, unlimited=True)
    row = (
        db.query(UserDailyUsage)
        .filter(
            UserDailyUsage.telegram_user_id == telegram_user_id,
            UserDailyUsage.usage_date == _local_today(),
            UserDailyUsage.feature == feature,
        )
        .first()
    )
    used = row.count if row else 0
    return QuotaResult(allowed=used < limit, used=used, limit=limit)


def try_consume(db: Session, telegram_user_id: str, feature: str, limit: int) -> QuotaResult:
    """Atomically check-and-consume one use. Returns allowed=False (without
    incrementing) when the daily limit is already reached."""
    if limit <= 0 or _is_unlimited_user(telegram_user_id):
        return QuotaResult(allowed=True, used=0, limit=limit, unlimited=True)

    today = _local_today()
    row = (
        db.query(UserDailyUsage)
        .filter(
            UserDailyUsage.telegram_user_id == telegram_user_id,
            UserDailyUsage.usage_date == today,
            UserDailyUsage.feature == feature,
        )
        .first()
    )
    if row is None:
        row = UserDailyUsage(telegram_user_id=telegram_user_id, usage_date=today, feature=feature, count=0)
        db.add(row)
        db.flush()  # surface a race as IntegrityError before we increment

    if row.count >= limit:
        return QuotaResult(allowed=False, used=row.count, limit=limit)

    row.count += 1
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return QuotaResult(allowed=True, used=row.count, limit=limit)
