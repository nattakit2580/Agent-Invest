from sqlalchemy import Column, String, Float, DateTime, Index
from datetime import datetime, timezone
import uuid
from database import Base


def _uuid():
    return str(uuid.uuid4())


class PriceAlert(Base):
    """A user's price alert. `direction` is fixed at creation from target vs the
    price then: 'above' fires when price >= target, 'below' when price <= target.
    status: active -> triggered (one-shot)."""
    __tablename__ = "price_alerts"

    id = Column(String(36), primary_key=True, default=_uuid)
    telegram_user_id = Column(String(40), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    target_price = Column(Float, nullable=False)
    direction = Column(String(5), nullable=False)   # "above" | "below"
    ref_price = Column(Float, nullable=True)          # price when the alert was set
    status = Column(String(10), nullable=False, default="active")  # active | triggered
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    triggered_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_price_alerts_status", "status"),
    )
