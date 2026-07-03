from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class AnalyzeRequest(BaseModel):
    symbol: str
    timeframe: str = "1w"   # 1d, 1w, 1m, 3m


class AgentOutput(BaseModel):
    direction: str
    confidence: float
    summary: str
    key_points: list[str]


class PredictionResponse(BaseModel):
    id: str
    symbol: str
    created_at: datetime
    timeframe: str
    direction: str
    current_price: float
    target_price: Optional[float]
    confidence: float
    reasoning: str
    agent_outputs: Optional[dict[str, Any]]
    actual_price: Optional[float]
    actual_direction: Optional[str]
    accuracy_score: Optional[float]
    compared_at: Optional[datetime]
    status: str

    class Config:
        from_attributes = True


class AccuracyStats(BaseModel):
    total: int
    compared: int
    direction_accuracy: float
    avg_confidence: float
    avg_accuracy_score: float
    avg_brier_score: Optional[float] = None
    by_timeframe: dict[str, dict]
    by_symbol: dict[str, dict]


class EvaluationResultResponse(BaseModel):
    id: str
    prediction_id: str
    evaluated_at: datetime
    direction_correct: bool
    agent_directions: Optional[dict[str, bool]]
    price_error_pct: Optional[float]
    price_score: Optional[float]
    brier_score: float
    confidence_bucket: str
    total_score: float

    class Config:
        from_attributes = True


class AgentAccuracyItem(BaseModel):
    agent: str
    total: int
    hits: int
    direction_accuracy: float


class CalibrationBucket(BaseModel):
    bucket: str
    total: int
    hits: int
    actual_rate: float


class DynamicWeightsResponse(BaseModel):
    total_evals: int
    dynamic_weights_active: bool
    weights: dict[str, float]
    accuracies: dict[str, float]
    prompt_section: str


class CompareRequest(BaseModel):
    prediction_id: str
    actual_price: float

class TelegramReportRequest(BaseModel):
    symbols: Optional[list[str]] = None
    max_news_items: Optional[int] = None
    max_assets: Optional[int] = None
    use_ai: Optional[bool] = None


class TelegramStatusResponse(BaseModel):
    configured: bool
    bot_configured: bool = False
    channel_id: Optional[str]
    community_chat_id: Optional[str] = None
    paid_chat_id: Optional[str] = None
    daily_report_enabled: bool
    community_report_enabled: bool = False
    paid_report_enabled: bool = False
    daily_report_time: str
    timezone: str
    watchlist_count: int
    economic_indicator_count: int
    webhook_secret_configured: bool = False
    admin_token_configured: bool = False


class TelegramReportPreviewResponse(BaseModel):
    title: str
    report_date: str
    generated_at: str
    categories: dict[str, Any]
    watchlist: list[dict[str, Any]]
    ipo_agenda: list[dict[str, Any]]
    economic_indicators: list[dict[str, Any]] = []
    upcoming_events: list[dict[str, Any]] = []
    brief: dict[str, Any]
    message: str


class MonitorReportResponse(BaseModel):
    id: str
    created_at: datetime
    report_date: str
    report_type: str
    channel_id: Optional[str]
    title: str
    categories: Optional[dict[str, Any]]
    watchlist: Optional[list[dict[str, Any]]]
    ipo_agenda: Optional[list[dict[str, Any]]]
    message: str
    status: str
    sent_at: Optional[datetime]
    error: Optional[str]

    class Config:
        from_attributes = True

class TelegramWebhookRegisterRequest(BaseModel):
    webhook_url: str
    drop_pending_updates: bool = True


class TelegramBroadcastRequest(BaseModel):
    target: str = "channel"
    chat_id: Optional[str] = None
    message: Optional[str] = None
    public_preview: bool = False
    use_ai: Optional[bool] = None


class TelegramCountItem(BaseModel):
    name: str
    count: int


class TelegramDailyMessageCount(BaseModel):
    date: str
    total: int
    private: int
    group: int


class TelegramRecentMessage(BaseModel):
    created_at: datetime
    chat_id: str
    chat_type: str
    user_id: Optional[str]
    display_name: Optional[str]
    text: Optional[str]
    intent: str
    topic: str


class TelegramAnalyticsResponse(BaseModel):
    days: int
    total_messages: int
    private_messages: int
    group_messages: int
    unique_users: int
    active_chats: int
    top_topics: list[TelegramCountItem]
    top_intents: list[TelegramCountItem]
    top_keywords: list[TelegramCountItem]
    daily_messages: list[TelegramDailyMessageCount]
    recent_messages: list[TelegramRecentMessage]
