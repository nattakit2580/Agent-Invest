from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models.prediction import (  # noqa
        AgentSetting,
        CalendarEvent,
        EconomicIndicator,
        MarketSnapshot,
        MonitorReport,
        Prediction,
        TelegramChat,
        TelegramMessage,
        TelegramUser,
    )
    from models.evaluation import EvaluationResult  # noqa
    from models.embedding import PredictionEmbedding  # noqa
    from models.knowledge import KnowledgeDocument, KnowledgeEmbedding  # noqa
    from models.knowledge_graph import KGEntity, KGRelationship  # noqa
    from models.portfolio import UserPortfolio  # noqa
    from models.watchlist import UserWatchlist  # noqa
    from models.usage import UserDailyUsage  # noqa
    from models.tier import UserTier  # noqa

    # The embedding table has a pgvector column, so the extension must exist first.
    if engine.url.get_backend_name().startswith("postgresql"):
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)

    # create_all() only creates missing tables — it never alters existing ones.
    # These columns were added to tables that already existed in production
    # (predictions, evaluation_results), so patch them in explicitly.
    if engine.url.get_backend_name().startswith("postgresql"):
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS market_regime VARCHAR(20)"
            ))
            conn.execute(text(
                "ALTER TABLE evaluation_results ADD COLUMN IF NOT EXISTS market_regime VARCHAR(20)"
            ))
            # reply_status was VARCHAR(30) but stores "failed: <error>" strings up to
            # ~128 chars; Postgres rejects the overflow (SQLite silently ignores the
            # limit, which is why this only broke in production). Widen it.
            conn.execute(text(
                "ALTER TABLE telegram_messages ALTER COLUMN reply_status TYPE VARCHAR(200)"
            ))
