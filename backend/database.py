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

    # The embedding table has a pgvector column, so the extension must exist first.
    if engine.url.get_backend_name().startswith("postgresql"):
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
