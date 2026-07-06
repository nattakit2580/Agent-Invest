from sqlalchemy import Column, String, Float, DateTime, Boolean, JSON, ForeignKey
from datetime import datetime, timezone
import uuid
from database import Base


def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(String(36), primary_key=True, default=_uuid)
    prediction_id = Column(String(36), ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, index=True)
    evaluated_at = Column(DateTime, default=_utcnow)

    # direction
    direction_correct = Column(Boolean, nullable=False)
    agent_directions = Column(JSON, nullable=True)   # {"news": True, "fundamental": False, ...}

    # price accuracy
    price_error_pct = Column(Float, nullable=True)   # abs((actual - target) / entry) * 100
    price_score = Column(Float, nullable=True)       # 0.0 - 0.3 component

    # calibration
    brier_score = Column(Float, nullable=False)      # (confidence - outcome)^2
    confidence_bucket = Column(String(10), nullable=False)  # "0.5-0.6", etc.

    # composite (denorm from Prediction.accuracy_score for fast querying)
    total_score = Column(Float, nullable=False)
    market_regime = Column(String(20), nullable=True)        # copied from Prediction at eval time
