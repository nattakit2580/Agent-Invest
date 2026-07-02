"""Format exported predictions into instruction-tuning JSONL for fine-tuning."""
import json


def build_user_prompt(case: dict) -> str:
    market = case.get("market_snapshot", {})
    agents = case.get("agent_outputs", {})

    lines = [f"Analyze {case['symbol']} with a {case['timeframe']} outlook.\n"]
    lines.append("MARKET DATA:")
    for k, v in market.items():
        if v is not None:
            lines.append(f"  {k}: {v}")

    lines.append("\nAGENT ANALYSIS REPORTS:")
    for agent_name, data in agents.items():
        direction = data.get("direction", "?")
        conf = data.get("confidence", 0)
        summary = data.get("summary", "")
        kp = data.get("key_points", [])
        lines.append(f"\n[{agent_name.upper()}] direction={direction}, confidence={conf:.2f}")
        lines.append(f"  Summary: {summary}")
        for point in kp[:2]:
            lines.append(f"  - {point}")

    lines.append("\nReturn a JSON prediction with direction, confidence, reasoning, key_risks, and recommendation.")
    return "\n".join(lines)


def build_assistant_response(case: dict) -> str:
    outcome = case.get("outcome", {})
    prediction = case.get("prediction", {})
    response = {
        "direction": outcome.get("actual_direction", prediction.get("direction")),
        "confidence": round(prediction.get("confidence", 0.5), 3),
        "reasoning": prediction.get("reasoning", ""),
        "key_risks": [],
        "recommendation": f"Based on analysis, the {case['symbol']} outlook for {case['timeframe']} is {outcome.get('actual_direction', 'neutral')}.",
    }
    return json.dumps(response, ensure_ascii=False)


def to_instruction_format(case: dict) -> dict:
    """Convert one exported case into a {"messages": [...]} training record."""
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert investment analysis AI. "
                    "Given market data and agent analysis reports, return a JSON prediction. "
                    "Return ONLY valid JSON with keys: direction, confidence, reasoning, key_risks, recommendation."
                ),
            },
            {
                "role": "user",
                "content": build_user_prompt(case),
            },
            {
                "role": "assistant",
                "content": build_assistant_response(case),
            },
        ]
    }


def format_dataset(
    cases: list[dict],
    min_score: float = 0.0,
    direction_balance: bool = False,
) -> list[dict]:
    """
    Filter and format cases into instruction-tuning format.
    direction_balance: if True, downsample majority class to match minority class count.
    """
    filtered = [c for c in cases if (c.get("outcome", {}).get("accuracy_score") or 0) >= min_score]

    if direction_balance and filtered:
        from collections import Counter
        counts = Counter(c.get("outcome", {}).get("actual_direction") for c in filtered)
        min_count = min(counts.values())
        balanced = []
        seen: dict[str, int] = {}
        for c in filtered:
            d = c.get("outcome", {}).get("actual_direction")
            seen[d] = seen.get(d, 0) + 1
            if seen[d] <= min_count:
                balanced.append(c)
        filtered = balanced

    return [to_instruction_format(c) for c in filtered]
