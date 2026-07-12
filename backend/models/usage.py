from sqlalchemy import Column, String, Integer, DateTime, UniqueConstraint
from datetime import datetime, timezone
import uuid
from database import Base


def _uuid():
    return str(uuid.uuid4())


class UserDailyUsage(Base):
    """Per-user, per-day usage counter for rate-limited features (e.g. AI analyze,
    graph). One row per (user, local-date, feature); count is incremented on each
    successful use. Cheap to query and self-explanatory — no cron cleanup needed
    (old rows are simply never read again)."""
    __tablename__ = "user_daily_usage"

    id = Column(String(36), primary_key=True, default=_uuid)
    telegram_user_id = Column(String(40), nullable=False, index=True)
    usage_date = Column(String(10), nullable=False)   # local YYYY-MM-DD
    feature = Column(String(30), nullable=False)       # "analyze" | "graph" | ...
    count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("telegram_user_id", "usage_date", "feature", name="uq_usage_user_date_feature"),
    )
