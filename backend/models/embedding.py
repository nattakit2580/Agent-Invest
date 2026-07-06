from sqlalchemy import Column, String, DateTime, Text, ForeignKey, text
from datetime import datetime, timezone
import uuid

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    # graceful fallback so app starts without pgvector installed
    from sqlalchemy import JSON as Vector
    PGVECTOR_AVAILABLE = False

from database import Base


def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


from config import get_settings

EMBEDDING_DIM = get_settings().embedding_dim  # Jina=768, OpenAI=1536


class PredictionEmbedding(Base):
    __tablename__ = "prediction_embeddings"

    id = Column(String(36), primary_key=True, default=_uuid)
    prediction_id = Column(
        String(36),
        ForeignKey("predictions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    embedding = Column(Vector(EMBEDDING_DIM) if PGVECTOR_AVAILABLE else Text, nullable=True)
    text_snapshot = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


# ivfflat index — created lazily via init_vector_index()
def init_vector_index(engine):
    """Call once after table creation to add the pgvector similarity index."""
    if not PGVECTOR_AVAILABLE:
        return
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_pred_emb_vector "
            "ON prediction_embeddings USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        ))
        conn.commit()
