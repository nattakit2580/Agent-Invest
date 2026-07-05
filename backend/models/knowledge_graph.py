"""Knowledge Graph — entities (companies, people, sectors) and relationships."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KGEntity(Base):
    __tablename__ = "kg_entities"
    __table_args__ = (
        UniqueConstraint("entity_type", "name", name="uq_kg_entity_type_name"),
        Index("ix_kg_entity_symbol", "symbol"),
        Index("ix_kg_entity_type", "entity_type"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    # company | person | sector | macro_event | product
    entity_type = Column(String(50), nullable=False)
    name = Column(String(500), nullable=False)
    symbol = Column(String(20), nullable=True)       # ticker for companies
    aliases = Column(JSON, default=list)              # ["NVIDIA", "Nvidia Corp"]
    attributes = Column(JSON, default=dict)           # sector, market_cap, role, etc.
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # outgoing relationships
    relationships_out = relationship(
        "KGRelationship",
        foreign_keys="KGRelationship.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    # incoming relationships
    relationships_in = relationship(
        "KGRelationship",
        foreign_keys="KGRelationship.target_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )


class KGRelationship(Base):
    """
    Directed edge: source --[relation_type]--> target

    Common relation_types:
      competes_with, supplier_of, customer_of, acquired_by,
      ceo_of, cfo_of, board_member_of, partner_with,
      belongs_to_sector, impacts (for macro events → companies/sectors)
    """
    __tablename__ = "kg_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "target_id", "relation_type",
            name="uq_kg_relationship",
        ),
        Index("ix_kg_rel_source", "source_id"),
        Index("ix_kg_rel_target", "target_id"),
        Index("ix_kg_rel_type", "relation_type"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    source_id = Column(String(36), ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(String(36), ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(100), nullable=False)
    strength = Column(Float, default=1.0)             # 0.0-1.0 confidence
    attributes = Column(JSON, default=dict)            # since, notes, source_url
    source_doc_id = Column(String(36), nullable=True)  # which knowledge doc triggered this
    created_at = Column(DateTime, default=_utcnow)

    source = relationship("KGEntity", foreign_keys=[source_id], back_populates="relationships_out")
    target = relationship("KGEntity", foreign_keys=[target_id], back_populates="relationships_in")
