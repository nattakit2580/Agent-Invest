from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from datetime import datetime, timezone
import uuid
from database import Base


def _uuid():
    return str(uuid.uuid4())


class AiChatInteraction(Base):
    """One AI-chat Q&A in a private Telegram chat, kept for statistics and to
    improve the chat logic over time. `rating` is set when the user taps 👍/👎
    (+1 / -1); null = not rated. High-rated answers are good few-shot / training
    material; low-rated ones flag prompts that need work."""
    __tablename__ = "ai_chat_interactions"

    id = Column(String(36), primary_key=True, default=_uuid)
    telegram_user_id = Column(String(40), nullable=False, index=True)
    symbol = Column(String(20), nullable=True)       # context symbol if any
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    rating = Column(Integer, nullable=True)           # +1 / -1 / None
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    rated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_ai_chat_rating", "rating"),
    )
