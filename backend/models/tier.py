from sqlalchemy import Column, String, DateTime
from datetime import datetime, timezone
from database import Base


class UserTier(Base):
    """Membership tier per Telegram user. Absence of a row means the default
    ('free') tier. Set by an admin via /settier; drives per-feature daily quota."""
    __tablename__ = "user_tiers"

    telegram_user_id = Column(String(40), primary_key=True)
    tier = Column(String(20), nullable=False, default="free")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
