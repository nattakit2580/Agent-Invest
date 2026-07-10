from sqlalchemy import Column, String, DateTime, UniqueConstraint
from datetime import datetime, timezone
import uuid
from database import Base


def _uuid():
    return str(uuid.uuid4())


class UserWatchlist(Base):
    __tablename__ = "user_watchlists"

    id = Column(String(36), primary_key=True, default=_uuid)
    telegram_user_id = Column(String(40), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    note = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("telegram_user_id", "symbol", name="uq_watchlist_user_symbol"),
    )
