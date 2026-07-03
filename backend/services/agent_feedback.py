"""
Compute per-agent accuracy from EvaluationResult history and derive dynamic weights.
Used by orchestrator to adjust agent influence based on real track record.
"""
from sqlalchemy.orm import Session
from models.evaluation import EvaluationResult

AGENT_NAMES = ["news", "fundamental", "technical", "sentiment"]
DEFAULT_WEIGHTS = {"news": 0.20, "fundamental": 0.30, "technical": 0.30, "sentiment": 0.20}

# need at least this many evaluations before trusting dynamic weights
MIN_EVALS_FOR_DYNAMIC = 20
# floor so no agent is completely silenced
WEIGHT_FLOOR = 0.10
# how much to trust dynamic vs. default (0 = always default, 1 = fully dynamic)
BLEND_ALPHA = 0.7


def _query_recent_evals(db: Session, recent_n: int) -> list:
    return (
        db.query(EvaluationResult)
        .order_by(EvaluationResult.evaluated_at.desc())
        .limit(recent_n)
        .all()
    )


def get_recent_agent_accuracies(db: Session, recent_n: int = 100) -> dict[str, float]:
    evals = _query_recent_evals(db, recent_n)
    stats: dict[str, dict] = {n: {"total": 0, "hits": 0} for n in AGENT_NAMES}

    for e in evals:
        for agent_name, correct in (e.agent_directions or {}).items():
            if agent_name in stats:
                stats[agent_name]["total"] += 1
                if correct:
                    stats[agent_name]["hits"] += 1

    return {
        name: round(stats[name]["hits"] / stats[name]["total"], 4)
        if stats[name]["total"] > 0 else 0.5
        for name in AGENT_NAMES
    }


def calc_dynamic_weights(
    agent_accuracies: dict[str, float],
    total_evals: int,
) -> dict[str, float]:
    """
    Blend accuracy-derived weights with defaults.
    Falls back to defaults until MIN_EVALS_FOR_DYNAMIC is reached.
    """
    if total_evals < MIN_EVALS_FOR_DYNAMIC:
        return DEFAULT_WEIGHTS.copy()

    raw = {name: max(agent_accuracies.get(name, 0.5), WEIGHT_FLOOR) for name in AGENT_NAMES}
    total_raw = sum(raw.values())
    dynamic = {name: v / total_raw for name, v in raw.items()}

    blended = {
        name: BLEND_ALPHA * dynamic[name] + (1 - BLEND_ALPHA) * DEFAULT_WEIGHTS[name]
        for name in AGENT_NAMES
    }
    total_blended = sum(blended.values())
    return {name: round(v / total_blended, 4) for name, v in blended.items()}


def format_agent_performance_for_prompt(
    agent_accuracies: dict[str, float], total_evals: int
) -> str:
    if total_evals == 0:
        return ""
    lines = [f"AGENT TRACK RECORD (last {total_evals} evaluated predictions):"]
    for name in AGENT_NAMES:
        acc = agent_accuracies.get(name, 0.5)
        filled = int(acc * 10)
        bar = "▓" * filled + "░" * (10 - filled)
        lines.append(f"  {name:<12} {bar} {acc:.0%} direction accuracy")
    return "\n".join(lines)


def get_agent_feedback(db: Session, recent_n: int = 100) -> dict:
    """
    Main entry point. Returns everything the orchestrator needs:
    {
        "accuracies":    {"news": 0.62, "fundamental": 0.71, ...},
        "weights":       {"news": 0.19, "fundamental": 0.33, ...},
        "total_evals":   50,
        "prompt_section": "AGENT TRACK RECORD..."
    }
    """
    evals = _query_recent_evals(db, recent_n)
    total = len(evals)

    stats: dict[str, dict] = {n: {"total": 0, "hits": 0} for n in AGENT_NAMES}
    for e in evals:
        for agent_name, correct in (e.agent_directions or {}).items():
            if agent_name in stats:
                stats[agent_name]["total"] += 1
                if correct:
                    stats[agent_name]["hits"] += 1

    accuracies = {
        name: round(stats[name]["hits"] / stats[name]["total"], 4)
        if stats[name]["total"] > 0 else 0.5
        for name in AGENT_NAMES
    }
    weights = calc_dynamic_weights(accuracies, total)
    prompt_section = format_agent_performance_for_prompt(accuracies, total)

    return {
        "accuracies": accuracies,
        "weights": weights,
        "total_evals": total,
        "prompt_section": prompt_section,
    }
