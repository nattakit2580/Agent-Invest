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

class EconomicIndicator(Base):
    __tablename__ = "economic_indicators"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(40), nullable=False, unique=True, index=True)  # FRED series id
    label = Column(String(80), nullable=False)
    value = Column(Float, nullable=True)
    previous_value = Column(Float, nullable=True)
    change = Column(Float, nullable=True)
    change_pct = Column(Float, nullable=True)
    unit = Column(String(60), nullable=True)
    observation_date = Column(String(10), nullable=True)   # date of the latest reading
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_type = Column(String(20), nullable=False, index=True)   # earnings / dividend / ipo / economic
    symbol = Column(String(20), nullable=True, index=True)
    title = Column(String(240), nullable=False)
    event_date = Column(String(10), nullable=False, index=True)    # YYYY-MM-DD
    dedupe_key = Column(String(120), nullable=False, unique=True, index=True)
    source = Column(String(60), nullable=True)
    extra = Column(JSON, nullable=True)
    notified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


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
    # หัวข้อหุ้นที่กำลังคุยกับ AI ล่าสุด — จำข้าม restart ให้คำถามต่อเนื่องรู้บริบท
    last_context_symbol = Column(String(20), nullable=True)


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
    reply_status = Column(String(200), nullable=True)   # "sent" or "failed: <up to ~120 char error>"
    message_date = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    raw_update = Column(JSON, nullable=True)


class AgentSetting(Base):
    """Runtime per-agent model overrides, editable from the admin page.

    One row per agent (news/fundamental/technical/sentiment/synthesis/critic).
    A null/blank column means "use the env/global default" for that field.
    """

    __tablename__ = "agent_settings"

    agent = Column(String(30), primary_key=True)
    model = Column(String(160), nullable=True)
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
