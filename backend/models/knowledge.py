"""Knowledge document models — stores ingested papers, filings, and web content."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database import Base
from models.embedding import PGVECTOR_AVAILABLE, EMBEDDING_DIM

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_knowledge_source_id"),
        Index("ix_knowledge_symbols", "symbols", postgresql_using="gin"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    source = Column(String(50), nullable=False, index=True)   # arxiv | sec | web | pdf
    source_id = Column(String(500), nullable=False)           # arXiv ID, URL, accession num
    title = Column(String(1000), nullable=False)
    content = Column(Text, nullable=True)                     # full extracted text (may be long)
    summary = Column(Text, nullable=True)                     # AI-extracted or abstract
    # JSONB on Postgres (required: GIN indexes need jsonb, not plain json).
    # Plain JSON on SQLite (local dev), since JSONB has no SQLite equivalent.
    symbols = Column(JSON().with_variant(JSONB, "postgresql"), default=list)  # ["NVDA", "AMD"]
    tags = Column(JSON, default=list)                         # ["semiconductor", "AI"]
    form_type = Column(String(20), nullable=True)             # 10-K, 10-Q, 8-K (SEC only)
    authors = Column(JSON, default=list)                      # arXiv authors
    link = Column(String(1000), nullable=True)
    published_at = Column(DateTime, nullable=True)
    indexed_at = Column(DateTime, default=_utcnow, index=True)

    embedding = relationship(
        "KnowledgeEmbedding", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )


class KnowledgeEmbedding(Base):
    __tablename__ = "knowledge_embeddings"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(
        String(36),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    embedding = Column(
        Vector(EMBEDDING_DIM) if (PGVECTOR_AVAILABLE and Vector is not None) else Text,
        nullable=True,
    )
    created_at = Column(DateTime, default=_utcnow)

    document = relationship("KnowledgeDocument", back_populates="embedding")
