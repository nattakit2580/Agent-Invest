from agents.base_agent import BaseAgent


class CriticAgent(BaseAgent):
    name = "critic"

    def critique(
        self,
        symbol: str,
        synthesis: dict,
        agent_outputs: dict,
        market_data: dict,
    ) -> dict:
        direction = synthesis.get("direction", "neutral")
        confidence = synthesis.get("confidence", 0.5)
        reasoning = synthesis.get("reasoning", "")

        dissenting = [
            f"  [{name.upper()}] said {data.get('direction')} (conf {data.get('confidence', 0):.0%})"
            for name, data in agent_outputs.items()
            if data.get("direction") != direction
        ]
        agreeing_count = sum(
            1 for data in agent_outputs.values()
            if data.get("direction") == direction
        )

        system = (
            "You are a critical risk analyst reviewing an investment prediction. "
            "Your job is to find weaknesses and challenge overconfident calls. "
            "Be skeptical but fair — if the case is genuinely strong, say so. "
            "Return ONLY valid JSON. No markdown. Write all text fields (critique, counter_points) in Thai language. Keep JSON keys, agrees_with_direction (true/false), revised_direction enum, and numbers in English."
        )

        user = f"""Review this investment prediction for {symbol}:

SYNTHESIS TO CHALLENGE:
- Direction: {direction}
- Confidence: {confidence:.0%}
- Reasoning: {reasoning}

AGENT CONSENSUS:
- {agreeing_count}/{len(agent_outputs)} agents agree with {direction}
- Dissenting signals:
{chr(10).join(dissenting) if dissenting else "  (none — all agents agree)"}

MARKET CONTEXT:
- Price: {market_data.get("price")}
- RSI-14: {market_data.get("rsi_14")}
- 1d change: {market_data.get("price_change_pct")}%
- Above SMA20: {market_data.get("price", 0) > (market_data.get("sma_20") or 0)}

Find the strongest counter-argument. If the synthesis is well-supported, confirm it but suggest any confidence adjustment.

Return this exact JSON:
{{
  "agrees_with_direction": <true or false>,
  "confidence_adjustment": <float -0.20 to +0.10, negative means reduce confidence>,
  "critique": "<2-3 sentence challenge or validation>",
  "counter_points": ["<risk or weakness 1>", "<risk or weakness 2>"],
  "revised_direction": "<bullish|bearish|neutral — use original if agrees>"
}}"""

        try:
            result = self._parse_json(self._call_llm(system, user, max_tokens=800))
            result.setdefault("agrees_with_direction", True)
            result.setdefault("confidence_adjustment", 0.0)
            result.setdefault("critique", "")
            result.setdefault("counter_points", [])
            result.setdefault("revised_direction", direction)
            # clamp adjustment range
            result["confidence_adjustment"] = max(-0.20, min(0.10, float(result["confidence_adjustment"])))
            return result
        except Exception as e:
            return {
                "agrees_with_direction": True,
                "confidence_adjustment": 0.0,
                "critique": f"ไม่สามารถวิเคราะห์ความเสี่ยงเพิ่มเติมได้: {e}",
                "counter_points": [],
                "revised_direction": direction,
            }
