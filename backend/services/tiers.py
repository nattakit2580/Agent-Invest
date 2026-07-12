"""Membership tiers and their effect on daily quota.

Tiers (low -> high): free, pro, vip.
- free: the base per-feature quota from config (TELEGRAM_DAILY_*_QUOTA)
- pro:  base * TELEGRAM_PRO_MULTIPLIER
- vip:  unlimited
A base of 0 means "unlimited" and stays unlimited for every tier.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config import get_settings
from models.tier import UserTier

DEFAULT_TIER = "free"
TIERS = ("free", "pro", "vip")

# Thai labels for user-facing messages
TIER_LABELS = {"free": "ฟรี", "pro": "Pro", "vip": "VIP (ไม่จำกัด)"}


def get_user_tier(db: Session, telegram_user_id: str) -> str:
    row = db.query(UserTier).filter(UserTier.telegram_user_id == telegram_user_id).first()
    return row.tier if row and row.tier in TIERS else DEFAULT_TIER


def set_user_tier(db: Session, telegram_user_id: str, tier: str) -> str:
    """Upsert a user's tier. Returns the normalized tier. Raises ValueError on
    an unknown tier."""
    tier = tier.strip().lower()
    if tier not in TIERS:
        raise ValueError(f"tier ต้องเป็น {', '.join(TIERS)}")
    row = db.query(UserTier).filter(UserTier.telegram_user_id == telegram_user_id).first()
    if row is None:
        row = UserTier(telegram_user_id=telegram_user_id, tier=tier)
        db.add(row)
    else:
        row.tier = tier
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return tier


def _base_quota(feature: str) -> int:
    s = get_settings()
    return {
        "analyze": s.telegram_daily_analyze_quota,
        "graph": s.telegram_daily_graph_quota,
        "chat": s.telegram_daily_chat_quota,
    }.get(feature, 0)


def quota_for(db: Session, telegram_user_id: str, feature: str) -> int:
    """Effective daily limit for this user+feature (0 = unlimited)."""
    tier = get_user_tier(db, telegram_user_id)
    base = _base_quota(feature)
    if tier == "vip" or base <= 0:
        return 0
    if tier == "pro":
        return base * max(1, get_settings().telegram_pro_multiplier)
    return base
