"""Memory + learning helpers.

- get_symbol_history: past compared predictions for a symbol, injected into new analyses
  so the system 'remembers' how it did before.
- get_agent_accuracy / adjust_weights: score each agent against realized outcomes and
  shift blend weights toward the agents that have been more accurate.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from models.prediction import Prediction

# Minimum compared samples before we trust learned signals over the static defaults.
MIN_SAMPLES_HISTORY = 1
MIN_SAMPLES_WEIGHTS = 8
# How strongly realized agent accuracy is allowed to pull the blend weights (0..1).
WEIGHT_LEARNING_STRENGTH = 0.5


def get_symbol_history(db: Session, symbol: str, limit: int = 5) -> dict[str, Any]:
    """Return recent realized (compared) predictions for a symbol plus summary stats."""
    compared = (
        db.query(Prediction)
        .filter(Prediction.symbol == symbol.upper(), Prediction.status == "compared")
        .order_by(Prediction.compared_at.desc())
        .limit(limit)
        .all()
    )

    items: list[dict[str, Any]] = []
    hits = 0
    scores: list[float] = []
    for p in compared:
        correct = p.direction == p.actual_direction
        if correct:
            hits += 1
        if p.accuracy_score is not None:
            scores.append(p.accuracy_score)
        items.append(
            {
                "date": p.created_at.date().isoformat() if p.created_at else None,
                "timeframe": p.timeframe,
                "predicted_direction": p.direction,
                "actual_direction": p.actual_direction,
                "correct": correct,
                "confidence": p.confidence,
                "accuracy_score": p.accuracy_score,
            }
        )

    n = len(items)
    stats = {
        "samples": n,
        "direction_accuracy": round(hits / n, 4) if n else None,
        "avg_accuracy_score": round(sum(scores) / len(scores), 4) if scores else None,
    }
    return {"items": items, "stats": stats}


def summarize_history_for_prompt(history: dict[str, Any], symbol: str) -> str:
    """Render history into a compact text block for the synthesis prompt."""
    items = history.get("items") or []
    stats = history.get("stats") or {}
    if not items:
        return f"No realized prediction history for {symbol} yet. This is an early call; be appropriately cautious."

    acc = stats.get("direction_accuracy")
    acc_text = f"{acc:.0%}" if isinstance(acc, (int, float)) else "n/a"
    lines = [
        f"Realized track record for {symbol}: {stats.get('samples', 0)} past call(s), "
        f"direction accuracy {acc_text}, avg score {stats.get('avg_accuracy_score')}.",
        "Most recent outcomes:",
    ]
    for it in items[:5]:
        verdict = "correct" if it["correct"] else "wrong"
        lines.append(
            f"- {it['date']} [{it['timeframe']}] predicted {it['predicted_direction']} "
            f"-> actual {it['actual_direction']} ({verdict}, score {it['accuracy_score']})"
        )
    return "\n".join(lines)


def get_agent_accuracy(
    db: Session,
    symbol: Optional[str] = None,
    min_samples: int = MIN_SAMPLES_WEIGHTS,
) -> dict[str, Any]:
    """Per-agent direction hit-rate computed from stored agent_outputs vs realized direction."""
    q = db.query(Prediction).filter(Prediction.status == "compared")
    if symbol:
        q = q.filter(Prediction.symbol == symbol.upper())
    compared = q.all()

    totals: dict[str, int] = {}
    hits: dict[str, int] = {}
    for p in compared:
        actual = p.actual_direction
        outputs = p.agent_outputs or {}
        if not isinstance(outputs, dict):
            continue
        for agent_name, output in outputs.items():
            if not isinstance(output, dict):
                continue
            predicted = output.get("direction")
            if predicted is None:
                continue
            totals[agent_name] = totals.get(agent_name, 0) + 1
            if predicted == actual:
                hits[agent_name] = hits.get(agent_name, 0) + 1

    accuracy = {
        name: round(hits.get(name, 0) / totals[name], 4)
        for name in totals
        if totals[name] > 0
    }
    return {
        "samples": len(compared),
        "sufficient": len(compared) >= min_samples,
        "per_agent": accuracy,
        "per_agent_samples": totals,
    }


def adjust_weights(
    base_weights: dict[str, float],
    agent_accuracy: dict[str, Any],
    strength: float = WEIGHT_LEARNING_STRENGTH,
) -> dict[str, float]:
    """Blend base weights with realized per-agent accuracy, then renormalize.

    Falls back to base weights when there is not enough realized data.
    """
    if not agent_accuracy or not agent_accuracy.get("sufficient"):
        return dict(base_weights)

    per_agent = agent_accuracy.get("per_agent") or {}
    if not per_agent:
        return dict(base_weights)

    adjusted: dict[str, float] = {}
    for name, base in base_weights.items():
        acc = per_agent.get(name)
        if acc is None:
            adjusted[name] = base
            continue
        # Center accuracy at 0.5 (chance-ish) -> multiplier in roughly [1-strength, 1+strength].
        multiplier = 1.0 + strength * ((acc - 0.5) * 2.0)
        multiplier = max(0.1, multiplier)
        adjusted[name] = base * multiplier

    total = sum(adjusted.values())
    if total <= 0:
        return dict(base_weights)
    return {name: round(value / total, 4) for name, value in adjusted.items()}
