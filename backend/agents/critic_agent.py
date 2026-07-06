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

        # Collect reasoning traces from each agent for the Critic to review
        agent_traces = []
        for name, data in agent_outputs.items():
            if name.startswith("_"):
                continue
            trace = data.get("reasoning_trace", "")
            ag_dir = data.get("direction", "?")
            ag_conf = data.get("confidence", 0)
            if trace:
                agent_traces.append(
                    f"  [{name.upper()}] {ag_dir} ({ag_conf:.0%}): {trace}"
                )
            else:
                agent_traces.append(
                    f"  [{name.upper()}] {ag_dir} ({ag_conf:.0%})"
                )

        dissenting = [
            f"  [{name.upper()}] said {data.get('direction')} (conf {data.get('confidence', 0):.0%})"
            for name, data in agent_outputs.items()
            if not name.startswith("_") and data.get("direction") != direction
        ]
        agreeing_count = sum(
            1 for name, data in agent_outputs.items()
            if not name.startswith("_") and data.get("direction") == direction
        )

        system = (
            "You are a critical risk analyst using the ReAct reasoning framework. "
            "Your job is to find weaknesses and challenge overconfident calls. "
            "Be skeptical but fair — if the case is genuinely strong, say so. "
            "Think step by step before reaching your verdict, then output JSON. "
            "Write all Thai text fields (critique, counter_points) in Thai. "
            "Keep JSON keys, agrees_with_direction (true/false), revised_direction enum, and numbers in English. "
            "In your thinking steps, use only plain text — do NOT use curly braces {{ }} until the final JSON."
        )

        user = f"""Review this investment prediction for {symbol} using the ReAct framework:

SYNTHESIS TO CHALLENGE:
- Direction: {direction}
- Confidence: {confidence:.0%}
- Reasoning: {reasoning}

AGENT REASONING TRACES:
{chr(10).join(agent_traces) if agent_traces else '  (no traces available)'}

AGENT CONSENSUS:
- {agreeing_count}/{len([k for k in agent_outputs if not k.startswith('_')])} agents agree with {direction}
- Dissenting signals:
{chr(10).join(dissenting) if dissenting else '  (none — all agents agree)'}

MARKET CONTEXT:
- Price: {market_data.get('price')}
- RSI-14: {market_data.get('rsi_14')}
- 1d change: {market_data.get('price_change_pct')}%
- Above SMA20: {market_data.get('price', 0) > (market_data.get('sma_20') or 0)}

Follow these reasoning steps before outputting JSON:

1. EXAMINE — What is the core bull/bear case being made? Are agent reasoning traces internally consistent?
2. CHALLENGE — What is the single strongest counter-argument? What does the market know that agents might miss?
3. PROBE — Which agent's reasoning is most vulnerable? Are any assuming too much?
4. VERDICT — Does this call hold up to scrutiny? Should confidence be adjusted?

After completing all 4 steps above, output this JSON as the final block:
{{
  "agrees_with_direction": <true or false>,
  "confidence_adjustment": <float -0.20 to +0.10, negative = reduce confidence>,
  "critique": "<2-3 sentence Thai challenge or validation>",
  "counter_points": ["<Thai risk or weakness 1>", "<Thai risk or weakness 2>"],
  "revised_direction": "<bullish|bearish|neutral — use original if agrees>"
}}"""

        try:
            result = self._parse_json(self._call_llm(system, user, max_tokens=1000))
            result.setdefault("agrees_with_direction", True)
            result.setdefault("confidence_adjustment", 0.0)
            result.setdefault("critique", "")
            result.setdefault("counter_points", [])
            result.setdefault("revised_direction", direction)
            result["confidence_adjustment"] = max(
                -0.20, min(0.10, float(result["confidence_adjustment"]))
            )
            return result
        except Exception as e:
            return {
                "agrees_with_direction": True,
                "confidence_adjustment": 0.0,
                "critique": f"ไม่สามารถวิเคราะห์ความเสี่ยงเพิ่มเติมได้: {e}",
                "counter_points": [],
                "revised_direction": direction,
            }
