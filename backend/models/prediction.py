from sqlalchemy import Column, String, Float, DateTime, Text, JSON, Integer, Boolean
from sqlalchemy.dialects.sqlite import TEXT
from datetime import datetime, timezone
import uuid
from database import Base


def _uuid():
    return str(uuid.uuid4())


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(String(36), primary_key=True, default=_uuid)
    symbol = Column(String(20), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    timeframe = Column(String(10), nullable=False)          # '1d','1w','1m','3m'
    direction = Column(String(10), nullable=False)          # 'bullish','bearish','neutral'
    current_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=True)
    confidence = Column(Float, nullable=False)              # 0.0 โ€“ 1.0
    reasoning = Column(Text, nullable=False)
    agent_outputs = Column(JSON, nullable=True)             # raw per-agent JSON
    # filled after timeframe passes
    actual_price = Column(Float, nullable=True)
    actual_direction = Column(String(10), nullable=True)
    accuracy_score = Column(Float, nullable=True)           # 0.0 โ€“ 1.0
    compared_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")          # pending / compared
    market_regime = Column(String(20), nullable=True)        # volatile/trending_up/trending_down/earnings_season/news_driven/sideways


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    price = Column(Float)
    volume = Column(Float)
    market_cap = Column(Float, nullable=True)
    pe_ratio = Column(Float, nullable=True)
    rsi_14 = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    extra = Column(JSON, nullable=True)

class MonitorReport(Base):
    __tablename__ = "monitor_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    report_date = Column(String(10), nullable=False, index=True)
    report_type = Column(String(30), nullable=False, default="daily_monitor")
    channel_id = Column(String(80), nullable=True)
    title = Column(String(200), nullable=False)
    categories = Column(JSON, nullable=True)
    watchlist = Column(JSON, nullable=True)
    ipo_agenda = Column(JSON, nullable=True)
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    sent_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id = Column(String(36), primary_key=True, default=_uuid)
    telegram_user_id = Column(String(40), nullable=False, unique=True, index=True)
    username = Column(String(120), nullable=True, index=True)
    first_name = Column(String(120), nullable=True)
    last_name = Column(String(120), nullable=True)
    language_code = Column(String(20), nullable=True)
    is_bot = Column(Boolean, default=False)
    first_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    message_count = Column(Integer, default=0)


class TelegramChat(Base):
    __tablename__ = "telegram_chats"

    id = Column(String(36), primary_key=True, default=_uuid)
    telegram_chat_id = Column(String(80), nullable=False, unique=True, index=True)
    chat_type = Column(String(30), nullable=False, index=True)
    title = Column(String(240), nullable=True)
    username = Column(String(120), nullable=True, index=True)
    first_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    message_count = Column(Integer, default=0)


class TelegramMessage(Base):
    __tablename__ = "telegram_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    telegram_update_id = Column(String(40), nullable=True, index=True)
    telegram_message_id = Column(String(40), nullable=True, index=True)
    telegram_chat_id = Column(String(80), nullable=False, index=True)
    telegram_user_id = Column(String(40), nullable=True, index=True)
    chat_type = Column(String(30), nullable=False, index=True)
    text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    command = Column(String(80), nullable=True, index=True)
    intent = Column(String(80), nullable=False, default="unknown", index=True)
    topic = Column(String(80), nullable=False, default="unknown", index=True)
    keywords = Column(JSON, nullable=True)
    reply_status = Column(String(30), nullable=True)
    message_date = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    raw_update = Column(JSON, nullable=True)
