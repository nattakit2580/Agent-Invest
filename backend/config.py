from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    database_url: str = "postgresql://agent:secret@localhost:5432/agent_invest"
    news_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    # Extra allowed CORS origins (comma-separated), e.g. your Cloudflare Workers URL.
    cors_allow_origins: str = ""
    # Regex allowing Cloudflare-hosted frontends (workers.dev / pages.dev) out of the box.
    cors_allow_origin_regex: str = r"https://.*\.(workers|pages)\.dev"
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
    telegram_private_report_max_assets: int = 20
    telegram_private_report_max_news_items: int = 20

    monitor_watchlist_symbols: str = (
        "AAPL,MSFT,NVDA,GOOGL,AMZN,META,TSLA,AMD,AVGO,JPM,"
        "V,SPY,QQQ,NFLX,COIN,"
        "BTC-USD,ETH-USD,SOL-USD,BNB-USD,XRP-USD"
    )
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

    # Per-agent model overrides. Blank means use openrouter_model.
    # These are the env-level defaults; the admin page can override them at
    # runtime (stored in the agent_settings table, takes precedence over these).
    news_agent_model: str = ""
    sentiment_agent_model: str = ""
    fundamental_agent_model: str = ""
    technical_agent_model: str = ""
    synthesis_agent_model: str = ""
    critic_agent_model: str = ""

    # Password guarding the /admin model-config page (verified server-side).
    admin_password: str = "NiceAgent"

    # Economic indicators (FRED). Register a free key at https://fredaccount.stlouisfed.org/apikeys
    fred_api_key: str = ""
    # Format: "Label=SERIES_ID,Label=SERIES_ID". 15 core US macro series.
    monitor_fred_series: str = (
        "CPI=CPIAUCSL,Core CPI=CPILFESL,PCE=PCEPI,Core PCE=PCEPILFE,"
        "Real GDP=GDPC1,Nonfarm Payrolls=PAYEMS,Unemployment Rate=UNRATE,"
        "Initial Jobless Claims=ICSA,Retail Sales=RSAFS,Fed Funds Rate=FEDFUNDS,"
        "10Y Treasury=DGS10,Yield Curve 10Y-2Y=T10Y2Y,Industrial Production=INDPRO,"
        "Consumer Sentiment=UMCSENT,Housing Starts=HOUST"
    )
    monitor_economic_report_limit: int = 15

    # Advance calendar alerts (earnings / ex-dividend / IPO / economic release)
    calendar_alert_enabled: bool = True
    calendar_alert_days_ahead: int = 3          # notify when an event is within N days
    calendar_report_days_ahead: int = 14        # window shown in the daily report section

    # RAG settings
    rag_enabled: bool = True
    rag_top_k: int = 5
    rag_min_score: float = 0.0
    # Embeddings use a separate provider because OpenRouter does not expose
    # a compatible /embeddings endpoint for this flow.
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.jina.ai/v1"
    embedding_model: str = "jina-embeddings-v2-base-en"
    embedding_dim: int = 768
    # Backward-compatible name. Kept so older env files do not break settings.
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
        extra = "ignore"  # tolerate unrelated env vars (deploy platforms inject their own)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
