from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    database_url: str = "sqlite:///./agent_invest.db"
    news_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    # Extra allowed CORS origins (comma-separated), e.g. your Cloudflare Workers URL.
    cors_allow_origins: str = ""
    # Regex allowing Cloudflare-hosted frontends (workers.dev / pages.dev) out of the box.
    cors_allow_origin_regex: str = r"https://.*\.(workers|pages)\.dev"
    fetch_interval_minutes: int = 30
    claude_model: str = "claude-sonnet-4-6"
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

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
