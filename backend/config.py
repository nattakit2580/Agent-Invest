from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4-6"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    database_url: str = "postgresql://agent:secret@localhost:5432/agent_invest"
    news_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    fetch_interval_minutes: int = 30
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    telegram_community_chat_id: str = ""
    telegram_paid_chat_id: str = ""
    telegram_webhook_secret_token: str = ""
    telegram_admin_token: str = ""
    telegram_daily_report_enabled: bool = False
    telegram_community_report_enabled: bool = False
    telegram_paid_report_enabled: bool = False
    telegram_daily_report_hour: int = 8
    telegram_daily_report_minute: int = 30
    telegram_timezone: str = "Asia/Bangkok"
    telegram_use_ai_summary: bool = True
    telegram_bot_username: str = ""
    telegram_public_news_limit: int = 3
    telegram_public_watchlist_limit: int = 3
    telegram_private_report_max_assets: int = 8
    telegram_private_report_max_news_items: int = 20

    monitor_watchlist_symbols: str = "AAPL,MSFT,NVDA,TSLA,SPY,QQQ,BTC-USD,ETH-USD"
    monitor_economic_indicators: str = (
        "FOMC,CPI,PCE,NFP,GDP,PMI,Initial Jobless Claims,"
        "Unemployment Rate,Retail Sales,Core Inflation,ECB,BoJ,OPEC"
    )
    monitor_rss_sources: str = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline,"
        "https://www.investing.com/rss/news.rss,"
        "https://cointelegraph.com/rss,"
        "https://coindesk.com/arc/outboundfeeds/rss/"
    )
    monitor_ipo_watchlist_path: str = ""
    monitor_report_max_news_items: int = 30
    monitor_report_max_watchlist_assets: int = 20

    # RAG settings
    rag_enabled: bool = True
    rag_top_k: int = 5
    rag_min_score: float = 0.0
    openrouter_embedding_model: str = "openai/text-embedding-3-small"

    # Dataset collection (Phase 4)
    auto_analyze_enabled: bool = False
    auto_analyze_symbols: str = "AAPL,MSFT,NVDA,TSLA,SPY,QQQ,BTC-USD,ETH-USD"
    auto_analyze_timeframe: str = "1w"
    auto_analyze_interval_hours: int = 24

    # Local fine-tuned model (Phase 5)
    use_local_model: bool = False
    local_model_url: str = "http://localhost:11434/v1"   # ollama or vllm
    local_model_name: str = "agent-invest-7b"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
