"""
Market Regime Detection + Regime-Aware Weight Presets.

Regimes:
  volatile        — large daily moves, RSI extremes (fear/greed spikes)
  trending_up     — price > SMA20 > SMA50, MACD bullish
  trending_down   — price < SMA20 < SMA50, MACD bearish
  earnings_season — Jan/Feb/Apr/May/Jul/Aug/Oct/Nov earnings windows
  news_driven     — high news volume or major corporate event detected
  sideways        — default when no strong signal
"""
from __future__ import annotations

from datetime import datetime, timezone

from services.agent_feedback import AGENT_NAMES, DEFAULT_WEIGHTS

# ---------------------------------------------------------------------------
# Regime display labels (Thai)
# ---------------------------------------------------------------------------

REGIME_DISPLAY_TH: dict[str, str] = {
    "volatile":        "⚡ ผันผวนสูง",
    "trending_up":     "📈 เทรนด์ขาขึ้น",
    "trending_down":   "📉 เทรนด์ขาลง",
    "earnings_season": "📊 ฤดูประกาศผล",
    "news_driven":     "📰 ข่าวขับเคลื่อน",
    "sideways":        "↔️ ทรงตัว",
}

# ---------------------------------------------------------------------------
# Preset weights per regime  (hand-tuned financial intuition)
# Will be BLENDED with accuracy-derived weights once enough evaluations exist.
#
# Rationale:
#   volatile        → news/sentiment drive snap moves; TA breaks down
#   trending_up     → follow the trend (TA); quality matters (fundamental)
#   trending_down   → fear sells everything; TA + sentiment dominate
#   earnings_season → reported numbers trump all else (fundamental + news)
#   news_driven     → event-driven; news impact dominates
#   sideways        → value wins range-bound markets; TA support/resistance
# ---------------------------------------------------------------------------

REGIME_WEIGHT_PRESETS: dict[str, dict[str, float]] = {
    "volatile": {
        "news": 0.35,
        "sentiment": 0.35,
        "technical": 0.20,
        "fundamental": 0.10,
    },
    "trending_up": {
        "technical": 0.40,
        "fundamental": 0.30,
        "sentiment": 0.15,
        "news": 0.15,
    },
    "trending_down": {
        "technical": 0.35,
        "sentiment": 0.35,
        "fundamental": 0.20,
        "news": 0.10,
    },
    "earnings_season": {
        "fundamental": 0.50,
        "news": 0.35,
        "technical": 0.10,
        "sentiment": 0.05,
    },
    "news_driven": {
        "news": 0.45,
        "sentiment": 0.25,
        "fundamental": 0.20,
        "technical": 0.10,
    },
    "sideways": {
        "fundamental": 0.40,
        "technical": 0.30,
        "news": 0.20,
        "sentiment": 0.10,
    },
}

# Minimum evaluations for a specific regime before trusting dynamic weights
MIN_REGIME_EVALS = 10
# Blend factor (0 = always preset, 1 = fully dynamic)
REGIME_BLEND_ALPHA = 0.65

# Keywords that trigger "news_driven" regime detection
_NEWS_EVENT_KEYWORDS = frozenset([
    "earnings", "revenue", "profit", "eps", "guidance", "forecast",
    "merger", "acquisition", "buyout", "takeover", "ipo",
    "fda", "approval", "recall", "lawsuit", "settlement",
    "ceo", "cfo", "resign", "appoint", "fired",
    "bankruptcy", "default", "downgrade", "upgrade",
    "dividend", "buyback", "split",
])

# Months that fall within earnings reporting windows
_EARNINGS_MONTHS = frozenset([1, 2, 4, 5, 7, 8, 10, 11])

# Symbols that are crypto — higher volatility threshold
_CRYPTO_SUFFIXES = ("-USD", "USDT", "BTC", "ETH")


# ---------------------------------------------------------------------------
# Regime detection
# ---------------------------------------------------------------------------

def detect_regime(market_data: dict, news: list[dict]) -> str:
    """
    Classify current market conditions for *market_data* + *news* into one
    of six regime strings.  Returns 'sideways' as the safe default.
    """
    price = float(market_data.get("price") or 0)
    price_change = abs(float(market_data.get("price_change_pct") or 0))
    rsi = float(market_data.get("rsi_14") or 50)
    macd = float(market_data.get("macd") or 0)
    macd_signal = float(market_data.get("macd_signal") or 0)
    sma_20 = float(market_data.get("sma_20") or 0)
    sma_50 = float(market_data.get("sma_50") or 0)
    symbol = str(market_data.get("symbol") or "")

    # Crypto gets a higher volatility threshold (normalise for crypto noise)
    is_crypto = any(symbol.upper().endswith(s) for s in _CRYPTO_SUFFIXES) or "BTC" in symbol.upper() or "ETH" in symbol.upper()
    vol_threshold = 5.0 if is_crypto else 2.5
    rsi_high = 78 if is_crypto else 72
    rsi_low = 22 if is_crypto else 28

    month = datetime.now(timezone.utc).month

    # ── Rule 1: Volatile ────────────────────────────────────────────────────
    if price_change > vol_threshold or rsi > rsi_high or rsi < rsi_low:
        return "volatile"

    # ── Rule 2: News-driven (major corporate event in recent headlines) ─────
    event_score = _news_event_score(news)
    if event_score >= 2:
        return "news_driven"

    # ── Rule 3: Earnings season ─────────────────────────────────────────────
    if month in _EARNINGS_MONTHS and not is_crypto:
        return "earnings_season"

    # ── Rule 4: Trend detection (requires meaningful SMA data) ──────────────
    if price > 0 and sma_20 > 0 and sma_50 > 0:
        above_both = price > sma_20 and sma_20 > sma_50
        below_both = price < sma_20 and sma_20 < sma_50
        macd_bull = macd > macd_signal
        macd_bear = macd < macd_signal

        if above_both and macd_bull:
            return "trending_up"
        if below_both and macd_bear:
            return "trending_down"

    return "sideways"


def _news_event_score(news: list[dict]) -> int:
    """Count how many major-event keywords appear across recent headlines."""
    score = 0
    for article in news[:10]:
        text = (
            (article.get("title") or "") + " " +
            (article.get("summary") or "")
        ).lower()
        for kw in _NEWS_EVENT_KEYWORDS:
            if kw in text:
                score += 1
                break  # one keyword per article max
    return score


# ---------------------------------------------------------------------------
# Regime-aware weight computation
# ---------------------------------------------------------------------------

def get_regime_weights(
    regime: str,
    regime_accuracies: dict[str, float],
    regime_eval_count: int,
) -> dict[str, float]:
    """
    Blend regime preset weights with data-driven accuracy for this regime.

    Falls back to preset only if fewer than MIN_REGIME_EVALS evaluations
    exist for the current regime.
    """
    preset = REGIME_WEIGHT_PRESETS.get(regime, DEFAULT_WEIGHTS)

    if regime_eval_count < MIN_REGIME_EVALS:
        return preset.copy()

    # Build accuracy-derived weights (floor at 0.10 so no agent is silenced)
    floor = 0.10
    raw = {n: max(regime_accuracies.get(n, 0.5), floor) for n in AGENT_NAMES}
    total_raw = sum(raw.values())
    dynamic = {n: v / total_raw for n, v in raw.items()}

    blended = {
        n: REGIME_BLEND_ALPHA * dynamic[n] + (1 - REGIME_BLEND_ALPHA) * preset.get(n, 0.25)
        for n in AGENT_NAMES
    }
    total = sum(blended.values())
    return {n: round(v / total, 4) for n, v in blended.items()}


def format_regime_for_prompt(
    regime: str,
    regime_accuracies: dict[str, float],
    regime_eval_count: int,
    weights: dict[str, float],
) -> str:
    """
    Build the regime section injected into synthesis + agent prompts.
    """
    display = REGIME_DISPLAY_TH.get(regime, regime)
    lines = [f"MARKET REGIME: {regime.upper()} ({display})"]

    if regime_eval_count > 0:
        lines.append(
            f"(Based on {regime_eval_count} past evaluations in this regime — "
            "agent weights adjusted accordingly)"
        )
    else:
        lines.append("(Using preset weights for this regime — no historical data yet)")

    lines.append("Effective agent weights for this regime:")
    for name in AGENT_NAMES:
        acc = regime_accuracies.get(name, 0)
        acc_str = f" | regime accuracy {acc:.0%}" if regime_eval_count >= MIN_REGIME_EVALS else ""
        lines.append(f"  {name:<14} weight={weights.get(name, 0.25):.0%}{acc_str}")

    return "\n".join(lines)
