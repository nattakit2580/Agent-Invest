"""
Knowledge Graph RAG service.

Provides:
  - upsert_entity / upsert_relationship   — write to graph
  - get_graph_context(symbol, db)          — prompt-ready context string
  - extract_and_ingest(text, symbols, db)  — LLM-based entity extraction
  - seed_watchlist(db)                     — pre-populate known relationships
"""
from __future__ import annotations

import json
from sqlalchemy.orm import Session
from sqlalchemy import text

from models.knowledge_graph import KGEntity, KGRelationship
from config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Relation type display labels (Thai)
# ---------------------------------------------------------------------------

RELATION_TH: dict[str, str] = {
    "competes_with":      "แข่งขันกับ",
    "supplier_of":        "ซัพพลายเออร์ของ",
    "customer_of":        "ลูกค้าของ",
    "acquired_by":        "ถูกซื้อกิจการโดย",
    "acquires":           "ซื้อกิจการ",
    "partner_with":       "พันธมิตรกับ",
    "ceo_of":             "CEO ของ",
    "cfo_of":             "CFO ของ",
    "board_member_of":    "กรรมการของ",
    "belongs_to_sector":  "อยู่ในกลุ่ม",
    "impacts":            "ส่งผลกระทบต่อ",
    "invests_in":         "ลงทุนใน",
}


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def upsert_entity(
    entity_type: str,
    name: str,
    symbol: str | None = None,
    aliases: list[str] | None = None,
    attributes: dict | None = None,
    db: Session = None,
) -> KGEntity | None:
    if db is None:
        return None
    try:
        existing = (
            db.query(KGEntity)
            .filter_by(entity_type=entity_type, name=name)
            .first()
        )
        if existing:
            # update symbol / aliases if newly provided
            if symbol and not existing.symbol:
                existing.symbol = symbol
            if aliases:
                merged = list(set((existing.aliases or []) + aliases))
                existing.aliases = merged
            if attributes:
                merged_attr = {**(existing.attributes or {}), **attributes}
                existing.attributes = merged_attr
            db.commit()
            return existing

        entity = KGEntity(
            entity_type=entity_type,
            name=name,
            symbol=symbol,
            aliases=aliases or [],
            attributes=attributes or {},
        )
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return entity
    except Exception as e:
        db.rollback()
        print(f"[kg_rag] upsert_entity error ({name}): {e}")
        return None


def upsert_relationship(
    source: KGEntity,
    target: KGEntity,
    relation_type: str,
    strength: float = 1.0,
    attributes: dict | None = None,
    source_doc_id: str | None = None,
    db: Session = None,
) -> KGRelationship | None:
    if db is None or source is None or target is None:
        return None
    try:
        existing = (
            db.query(KGRelationship)
            .filter_by(source_id=source.id, target_id=target.id, relation_type=relation_type)
            .first()
        )
        if existing:
            if attributes:
                existing.attributes = {**(existing.attributes or {}), **attributes}
            db.commit()
            return existing

        rel = KGRelationship(
            source_id=source.id,
            target_id=target.id,
            relation_type=relation_type,
            strength=strength,
            attributes=attributes or {},
            source_doc_id=source_doc_id,
        )
        db.add(rel)
        db.commit()
        db.refresh(rel)
        return rel
    except Exception as e:
        db.rollback()
        print(f"[kg_rag] upsert_relationship error ({source.name} → {target.name}): {e}")
        return None


# ---------------------------------------------------------------------------
# Graph traversal — build context for LLM prompt
# ---------------------------------------------------------------------------

def get_graph_context(symbol: str, db: Session, depth: int = 2) -> str:
    """
    Return formatted entity graph context for *symbol* up to *depth* hops.
    Empty string when graph is empty or DB unavailable.
    """
    if db is None:
        return ""

    try:
        entity = (
            db.query(KGEntity)
            .filter(
                (KGEntity.symbol == symbol.upper()) |
                (KGEntity.entity_type == "company")
            )
            .filter(KGEntity.symbol == symbol.upper())
            .first()
        )
        if not entity:
            return ""

        lines = [f"ENTITY GRAPH — {entity.name} ({symbol}):"]
        visited: set[str] = {entity.id}
        _traverse(entity, db, lines, visited, current_depth=0, max_depth=depth, indent=0)

        if len(lines) <= 1:
            return ""
        return "\n".join(lines)
    except Exception as e:
        print(f"[kg_rag] get_graph_context error: {e}")
        return ""


def _traverse(
    entity: KGEntity,
    db: Session,
    lines: list[str],
    visited: set[str],
    current_depth: int,
    max_depth: int,
    indent: int,
) -> None:
    if current_depth >= max_depth:
        return

    prefix = "  " * indent

    # outgoing: entity --[rel]--> target
    for rel in entity.relationships_out:
        target = rel.target
        rel_label = RELATION_TH.get(rel.relation_type, rel.relation_type)
        target_symbol = f" ({target.symbol})" if target.symbol else ""
        lines.append(f"{prefix}• {rel_label} {target.name}{target_symbol}")

        if target.id not in visited and current_depth + 1 < max_depth:
            visited.add(target.id)
            _traverse(target, db, lines, visited, current_depth + 1, max_depth, indent + 1)

    # incoming (show only direct, not deep)
    if current_depth == 0:
        for rel in entity.relationships_in:
            source = rel.source
            if rel.relation_type in ("supplier_of", "customer_of", "ceo_of", "cfo_of", "board_member_of"):
                rel_label = RELATION_TH.get(rel.relation_type, rel.relation_type)
                src_symbol = f" ({source.symbol})" if source.symbol else ""
                lines.append(f"{prefix}• {source.name}{src_symbol} {rel_label} {entity.name}")


# ---------------------------------------------------------------------------
# LLM-based entity extraction
# ---------------------------------------------------------------------------

def extract_and_ingest(
    text: str,
    symbols: list[str],
    db: Session,
    source_doc_id: str | None = None,
) -> int:
    """
    Use LLM to extract entities and relationships from *text*.
    Inserts new findings into the graph. Returns count of new relationships.
    """
    if not settings.rag_enabled or not text.strip():
        return 0

    from agents.base_agent import BaseAgent

    system = (
        "You are an entity extraction specialist. "
        "Extract named entities and relationships from financial text. "
        "Return ONLY valid JSON. No markdown."
    )
    user = f"""Extract entities and relationships from this financial text.

TEXT:
{text[:2000]}

SYMBOLS CONTEXT: {', '.join(symbols)}

Return this exact JSON (use English for all values):
{{
  "entities": [
    {{"entity_type": "company|person|sector|macro_event", "name": "<name>", "symbol": "<ticker or null>", "aliases": []}}
  ],
  "relationships": [
    {{"source_name": "<name>", "target_name": "<name>", "relation_type": "competes_with|supplier_of|customer_of|acquired_by|acquires|partner_with|ceo_of|cfo_of|board_member_of|belongs_to_sector|impacts|invests_in", "strength": 0.8, "notes": ""}}
  ]
}}"""

    try:
        agent = BaseAgent()
        agent.name = "kg_extractor"
        raw = agent._call_llm(system, user, max_tokens=1000)
        data = agent._parse_json(raw)
    except Exception as e:
        print(f"[kg_rag] extraction LLM error: {e}")
        return 0

    # Upsert entities first, build name → entity map
    entity_map: dict[str, KGEntity] = {}
    for e_data in data.get("entities", []):
        name = (e_data.get("name") or "").strip()
        etype = (e_data.get("entity_type") or "company").strip()
        sym = (e_data.get("symbol") or None)
        if not name:
            continue
        ent = upsert_entity(
            entity_type=etype,
            name=name,
            symbol=sym,
            aliases=e_data.get("aliases", []),
            db=db,
        )
        if ent:
            entity_map[name.lower()] = ent

    # Upsert relationships
    count = 0
    for r_data in data.get("relationships", []):
        src_name = (r_data.get("source_name") or "").strip().lower()
        tgt_name = (r_data.get("target_name") or "").strip().lower()
        rel_type = (r_data.get("relation_type") or "").strip()

        src = entity_map.get(src_name)
        tgt = entity_map.get(tgt_name)
        if not src or not tgt or not rel_type:
            continue

        rel = upsert_relationship(
            source=src,
            target=tgt,
            relation_type=rel_type,
            strength=float(r_data.get("strength", 1.0)),
            attributes={"notes": r_data.get("notes", "")},
            source_doc_id=source_doc_id,
            db=db,
        )
        if rel:
            count += 1

    return count


# ---------------------------------------------------------------------------
# Seed known relationships for default watchlist symbols
# ---------------------------------------------------------------------------

_SEED_DATA: list[dict] = [
    # ── NVDA ──────────────────────────────────────────────────────────────
    {"type": "company", "name": "NVIDIA", "symbol": "NVDA", "sector": "Technology", "subsector": "Semiconductor"},
    {"type": "company", "name": "AMD", "symbol": "AMD", "sector": "Technology", "subsector": "Semiconductor"},
    {"type": "company", "name": "Intel", "symbol": "INTC", "sector": "Technology", "subsector": "Semiconductor"},
    {"type": "company", "name": "TSMC", "symbol": "TSM", "sector": "Technology", "subsector": "Semiconductor Foundry"},
    {"type": "company", "name": "Microsoft", "symbol": "MSFT", "sector": "Technology"},
    {"type": "company", "name": "Apple", "symbol": "AAPL", "sector": "Technology"},
    {"type": "company", "name": "Tesla", "symbol": "TSLA", "sector": "Consumer Discretionary"},
    {"type": "company", "name": "Meta", "symbol": "META", "sector": "Technology"},
    {"type": "company", "name": "Google", "symbol": "GOOGL", "sector": "Technology"},
    {"type": "company", "name": "Amazon", "symbol": "AMZN", "sector": "Technology"},
    {"type": "company", "name": "Samsung", "symbol": "005930.KS", "sector": "Technology"},
    {"type": "company", "name": "SK Hynix", "symbol": None, "sector": "Technology", "subsector": "Memory"},
    {"type": "person", "name": "Jensen Huang", "symbol": None, "role": "CEO", "company": "NVDA"},
    {"type": "person", "name": "Tim Cook", "symbol": None, "role": "CEO", "company": "AAPL"},
    {"type": "person", "name": "Satya Nadella", "symbol": None, "role": "CEO", "company": "MSFT"},
    {"type": "person", "name": "Elon Musk", "symbol": None, "role": "CEO", "company": "TSLA"},
    {"type": "sector", "name": "Technology", "symbol": None},
    {"type": "sector", "name": "Semiconductor", "symbol": None},
    {"type": "sector", "name": "AI Infrastructure", "symbol": None},
    {"type": "sector", "name": "Consumer Discretionary", "symbol": None},
    {"type": "macro_event", "name": "FOMC Interest Rate Decision", "symbol": None},
    {"type": "macro_event", "name": "CPI Inflation Report", "symbol": None},
]

_SEED_RELATIONSHIPS: list[tuple[str, str, str, float]] = [
    # (source_name, target_name, relation_type, strength)
    # NVDA
    ("NVIDIA", "AMD", "competes_with", 0.95),
    ("NVIDIA", "Intel", "competes_with", 0.80),
    ("TSMC", "NVIDIA", "supplier_of", 0.99),
    ("SK Hynix", "NVIDIA", "supplier_of", 0.90),
    ("Jensen Huang", "NVIDIA", "ceo_of", 1.0),
    ("NVIDIA", "Technology", "belongs_to_sector", 1.0),
    ("NVIDIA", "AI Infrastructure", "belongs_to_sector", 0.95),
    ("Microsoft", "NVIDIA", "customer_of", 0.85),
    ("Google", "NVIDIA", "customer_of", 0.85),
    ("Amazon", "NVIDIA", "customer_of", 0.80),
    # AAPL
    ("Apple", "Samsung", "competes_with", 0.80),
    ("Apple", "Google", "competes_with", 0.70),
    ("TSMC", "Apple", "supplier_of", 0.99),
    ("Samsung", "Apple", "supplier_of", 0.60),
    ("Tim Cook", "Apple", "ceo_of", 1.0),
    ("Apple", "Technology", "belongs_to_sector", 1.0),
    # MSFT
    ("Microsoft", "Apple", "competes_with", 0.60),
    ("Microsoft", "Google", "competes_with", 0.75),
    ("Satya Nadella", "Microsoft", "ceo_of", 1.0),
    ("Microsoft", "AI Infrastructure", "belongs_to_sector", 0.90),
    # TSLA
    ("Tesla", "Consumer Discretionary", "belongs_to_sector", 1.0),
    ("Elon Musk", "Tesla", "ceo_of", 1.0),
    ("NVIDIA", "Tesla", "supplier_of", 0.70),
    # Macro
    ("FOMC Interest Rate Decision", "Technology", "impacts", 0.85),
    ("FOMC Interest Rate Decision", "Consumer Discretionary", "impacts", 0.80),
    ("CPI Inflation Report", "Technology", "impacts", 0.70),
]


def seed_watchlist(db: Session) -> int:
    """
    Pre-populate the entity graph with known relationships for default watchlist.
    Safe to call multiple times (upserts).
    Returns number of new relationships created.
    """
    entity_map: dict[str, KGEntity] = {}

    for e_data in _SEED_DATA:
        attrs = {k: v for k, v in e_data.items()
                 if k not in ("type", "name", "symbol")}
        ent = upsert_entity(
            entity_type=e_data["type"],
            name=e_data["name"],
            symbol=e_data.get("symbol"),
            attributes=attrs,
            db=db,
        )
        if ent:
            entity_map[e_data["name"].lower()] = ent

    count = 0
    for src_name, tgt_name, rel_type, strength in _SEED_RELATIONSHIPS:
        src = entity_map.get(src_name.lower())
        tgt = entity_map.get(tgt_name.lower())
        if not src or not tgt:
            continue
        rel = upsert_relationship(src, tgt, rel_type, strength=strength, db=db)
        if rel:
            count += 1

    return count


def get_graph_stats(db: Session) -> dict:
    """Return entity and relationship counts."""
    try:
        rows = db.execute(
            text("SELECT entity_type, COUNT(*) AS cnt FROM kg_entities GROUP BY entity_type")
        ).fetchall()
        rel_count = db.execute(
            text("SELECT COUNT(*) FROM kg_relationships")
        ).scalar()
        return {
            "entities": {row.entity_type: row.cnt for row in rows},
            "relationships": rel_count or 0,
        }
    except Exception:
        return {"entities": {}, "relationships": 0}
