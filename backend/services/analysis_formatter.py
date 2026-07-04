"""Format analysis results into Telegram messages."""

DIRECTION_ICON = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}
DIRECTION_TH = {"bullish": "ขาขึ้น", "bearish": "ขาลง", "neutral": "ทรงตัว"}
TIMEFRAME_TH = {"1d": "1 วัน", "1w": "1 สัปดาห์", "1m": "1 เดือน", "3m": "3 เดือน"}


def format_analysis(symbol: str, result: dict, timeframe: str = "1w") -> str:
    d = result["direction"]
    c = result["confidence"]
    price = result.get("current_price", 0)
    target = result.get("target_price")
    tf_th = TIMEFRAME_TH.get(timeframe, timeframe)

    lines = []

    # Header
    lines.append(f"📊 {symbol} — วิเคราะห์ ({tf_th})")
    lines.append("")

    # Direction + confidence
    icon = DIRECTION_ICON.get(d, "⚪")
    dir_th = DIRECTION_TH.get(d, d)
    lines.append(f"{icon} ทิศทาง: {dir_th.upper()}  |  ความเชื่อมั่น {c:.0%}")

    # Price
    price_line = f"💰 ราคา: ${price:,.2f}"
    if target:
        pct = (target - price) / price * 100
        price_line += f"  →  เป้า: ${target:,.2f}  ({pct:+.1f}%)"
    lines.append(price_line)
    lines.append("")

    # Agent signals
    lines.append("── สัญญาณ Agents ──")
    for name, out in result.get("agent_outputs", {}).items():
        if name == "_critic":
            continue
        ag_d = out.get("direction", "?")
        ag_c = out.get("confidence", 0)
        ag_icon = DIRECTION_ICON.get(ag_d, "⚪")
        summary = out.get("summary", "")
        key_pts = out.get("key_points", [])

        lines.append(f"{ag_icon} {name.capitalize()}: {ag_d} ({ag_c:.0%})")
        if summary:
            lines.append(f"   {summary}")
        for pt in key_pts[:3]:
            lines.append(f"   • {pt}")

    lines.append("")

    # Reasoning
    reasoning = result.get("reasoning", "")
    if reasoning:
        lines.append("── เหตุผล ──")
        lines.append(reasoning)
        lines.append("")

    # Key risks
    risks = result.get("key_risks", [])
    if risks:
        lines.append("⚠️ ความเสี่ยง:")
        for r in risks:
            lines.append(f"  • {r}")

    # Catalysts
    catalysts = result.get("catalysts", [])
    if catalysts:
        lines.append("")
        lines.append("🚀 ปัจจัยหนุน:")
        for cat in catalysts:
            lines.append(f"  • {cat}")

    lines.append("")

    # Critic
    critic = result.get("critic", {})
    if critic:
        agrees = critic.get("agrees_with_direction", True)
        adj = critic.get("confidence_adjustment", 0.0)
        critique = critic.get("critique", "")
        counter = critic.get("counter_points", [])
        critic_icon = "✅" if agrees else "⚠️"
        lines.append(f"{critic_icon} Critic: {'เห็นด้วย' if agrees else 'ไม่เห็นด้วย'}  ({adj:+.0%})")
        if critique:
            lines.append(f"   {critique}")
        for pt in counter:
            lines.append(f"   • {pt}")
        lines.append("")

    # Recommendation
    rec = result.get("recommendation", "")
    if rec:
        lines.append(f"📌 คำแนะนำ: {rec}")

    return "\n".join(lines)
