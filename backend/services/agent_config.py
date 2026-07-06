"""Runtime per-agent model configuration.

The admin page can override which LLM each agent uses (and a couple of tunables)
without a redeploy. Overrides are persisted in the ``agent_settings`` table and
mirrored into a small in-process cache so the hot path (BaseAgent._call_llm)
never has to touch the database.

Precedence for an agent's model, highest first:
  1. runtime override (admin page → agent_settings table)
  2. env default  ({agent}_agent_model in Settings)
  3. global default (openrouter_model)
"""
from __future__ import annotations

import threading

from config import get_settings

# Canonical agent identities. The four analysts run in parallel; synthesis and
# critic run after. Order here is the order shown in the admin UI.
AGENT_NAMES = ["news", "fundamental", "technical", "sentiment", "synthesis", "critic"]

AGENT_LABELS = {
    "news": "News Agent",
    "fundamental": "Fundamental Agent",
    "technical": "Technical Agent",
    "sentiment": "Sentiment Agent",
    "synthesis": "Synthesis (Orchestrator)",
    "critic": "Risk Critic",
}

# Curated OpenRouter models offered in the admin dropdown. Admins can also type
# any other OpenRouter model id in the custom field, so this is just a shortlist.
# Models whose OpenRouter id ends in ":free" cost nothing (rate-limited free tier).
MODEL_CATALOG = [
    # --- Free tier (no cost, rate-limited) ---
    {"id": "deepseek/deepseek-chat-v3-0324:free", "label": "DeepSeek V3 (free)", "tier": "balanced", "free": True},
    {"id": "deepseek/deepseek-r1:free", "label": "DeepSeek R1 · reasoning (free)", "tier": "strong", "free": True},
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "label": "Llama 3.3 70B (free)", "tier": "balanced", "free": True},
    {"id": "google/gemini-2.0-flash-exp:free", "label": "Gemini 2.0 Flash (free)", "tier": "fast", "free": True},
    {"id": "qwen/qwen-2.5-72b-instruct:free", "label": "Qwen 2.5 72B (free)", "tier": "balanced", "free": True},
    {"id": "qwen/qwq-32b:free", "label": "QwQ 32B · reasoning (free)", "tier": "strong", "free": True},
    {"id": "mistralai/mistral-small-3.1-24b-instruct:free", "label": "Mistral Small 3.1 24B (free)", "tier": "fast", "free": True},
    {"id": "nvidia/llama-3.1-nemotron-70b-instruct:free", "label": "Nemotron 70B (free)", "tier": "balanced", "free": True},
    {"id": "google/gemma-3-27b-it:free", "label": "Gemma 3 27B (free)", "tier": "fast", "free": True},
    # --- Paid tier (needs OpenRouter credit) ---
    {"id": "deepseek/deepseek-v4-flash", "label": "DeepSeek V4 Flash", "tier": "fast", "free": False},
    {"id": "deepseek/deepseek-chat", "label": "DeepSeek Chat", "tier": "balanced", "free": False},
    {"id": "openai/gpt-4o-mini", "label": "GPT-4o mini", "tier": "balanced", "free": False},
    {"id": "openai/gpt-4o", "label": "GPT-4o", "tier": "strong", "free": False},
    {"id": "anthropic/claude-3.5-haiku", "label": "Claude 3.5 Haiku", "tier": "fast", "free": False},
    {"id": "anthropic/claude-3.5-sonnet", "label": "Claude 3.5 Sonnet", "tier": "strong", "free": False},
    {"id": "google/gemini-flash-1.5", "label": "Gemini 1.5 Flash", "tier": "fast", "free": False},
    {"id": "meta-llama/llama-3.3-70b-instruct", "label": "Llama 3.3 70B", "tier": "balanced", "free": False},
    {"id": "qwen/qwen-2.5-72b-instruct", "label": "Qwen 2.5 72B", "tier": "balanced", "free": False},
    {"id": "mistralai/mistral-large", "label": "Mistral Large", "tier": "strong", "free": False},
]

_lock = threading.Lock()
# agent -> {"model": str|None, "temperature": float|None, "max_tokens": int|None}
_overrides: dict[str, dict] = {}
_loaded = False


def _env_default_model(agent: str) -> str:
    settings = get_settings()
    return (getattr(settings, f"{agent}_agent_model", "") or "").strip()


def global_default_model() -> str:
    return get_settings().openrouter_model


def load_overrides() -> None:
    """(Re)load overrides from the DB into the in-process cache."""
    global _loaded
    from database import SessionLocal
    from models.prediction import AgentSetting

    data: dict[str, dict] = {}
    db = SessionLocal()
    try:
        for row in db.query(AgentSetting).all():
            data[row.agent] = {
                "model": (row.model or "").strip() or None,
                "temperature": row.temperature,
                "max_tokens": row.max_tokens,
            }
    except Exception as exc:  # pragma: no cover - defensive; empty cache is fine
        print(f"[agent_config] load_overrides failed: {exc}")
    finally:
        db.close()

    with _lock:
        _overrides.clear()
        _overrides.update(data)
        _loaded = True


def _ensure_loaded() -> None:
    if not _loaded:
        load_overrides()


def get_override(agent: str) -> dict:
    """Runtime override for one agent (may be empty). Never hits the DB directly."""
    _ensure_loaded()
    with _lock:
        return dict(_overrides.get(agent, {}))


def resolve_model(agent: str) -> str:
    """Effective model id for an agent, applying the full precedence chain."""
    override = get_override(agent).get("model")
    if override:
        return override
    return _env_default_model(agent) or global_default_model()


def set_overrides(updates: dict[str, dict]) -> None:
    """Upsert overrides for one or more agents, then refresh the cache.

    ``updates`` maps agent -> {model?, temperature?, max_tokens?}. A blank/None
    model clears the override (agent falls back to the env/global default).
    """
    from database import SessionLocal
    from models.prediction import AgentSetting

    db = SessionLocal()
    try:
        for agent, cfg in updates.items():
            if agent not in AGENT_NAMES:
                continue
            row = db.query(AgentSetting).filter(AgentSetting.agent == agent).first()
            if row is None:
                row = AgentSetting(agent=agent)
                db.add(row)
            if "model" in cfg:
                model = (cfg.get("model") or "").strip()
                row.model = model or None
            if "temperature" in cfg:
                row.temperature = cfg.get("temperature")
            if "max_tokens" in cfg:
                row.max_tokens = cfg.get("max_tokens")
        db.commit()
    finally:
        db.close()

    load_overrides()


def get_effective_config() -> list[dict]:
    """Per-agent view for the admin UI: current override + resolved model."""
    _ensure_loaded()
    rows = []
    for agent in AGENT_NAMES:
        ov = get_override(agent)
        rows.append({
            "agent": agent,
            "label": AGENT_LABELS.get(agent, agent),
            "model": ov.get("model") or "",          # blank = using default
            "resolved_model": resolve_model(agent),   # what actually runs
            "env_default": _env_default_model(agent),
            "temperature": ov.get("temperature"),
            "max_tokens": ov.get("max_tokens"),
        })
    return rows
