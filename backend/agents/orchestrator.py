from concurrent.futures import ThreadPoolExecutor
from agents.news_agent import NewsAgent
from agents.fundamental_agent import FundamentalAgent
from agents.technical_agent import TechnicalAgent
from agents.sentiment_agent import SentimentAgent
from agents.critic_agent import CriticAgent
from agents.base_agent import BaseAgent, settings
from services.agent_feedback import DEFAULT_WEIGHTS

DIRECTION_SCORE = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}


class Orchestrator:
    def __init__(self):
        self.agents: list[BaseAgent] = [
            NewsAgent(),
            FundamentalAgent(),
            TechnicalAgent(),
            SentimentAgent(),
        ]
        self.critic = CriticAgent()

    def run_all_agents(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        results = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(agent.analyze, symbol, market_data, news): agent.name
                for agent in self.agents
            }
            for future, name in futures.items():
                try:
                    results[name] = future.result(timeout=60)
                except Exception as e:
                    results[name] = {
                        "direction": "neutral",
                        "confidence": 0.3,
                        "summary": f"Agent error: {str(e)}",
                        "key_points": [],
                    }
        return results

    def _weighted_direction(
        self, agent_outputs: dict, weights: dict | None = None
    ) -> tuple[str, float]:
        w = weights or DEFAULT_WEIGHTS
        weighted_score = 0.0
        total_weight = 0.0
        weighted_confidence = 0.0

        for name, output in agent_outputs.items():
            weight = w.get(name, 0.25)
            direction = output.get("direction", "neutral")
            confidence = float(output.get("confidence", 0.5))
            score = DIRECTION_SCORE.get(direction, 0.0)
            weighted_score += score * weight * confidence
            weighted_confidence += confidence * weight
            total_weight += weight

        final_score = weighted_score / total_weight if total_weight else 0
        final_confidence = weighted_confidence / total_weight if total_weight else 0.5

        if final_score > 0.15:
            direction = "bullish"
        elif final_score < -0.15:
            direction = "bearish"
        else:
            direction = "neutral"

        return direction, round(min(max(final_confidence, 0.0), 1.0), 3)

    def synthesize(
        self,
        symbol: str,
        market_data: dict,
        agent_outputs: dict,
        timeframe: str,
        similar_cases: list[dict] | None = None,
        agent_feedback: dict | None = None,
    ) -> dict:
        # use dynamic weights from track record if available
        weights = agent_feedback.get("weights") if agent_feedback else None
        direction, confidence = self._weighted_direction(agent_outputs, weights)

        current_price = market_data.get("price", 0)
        target_price = None
        if direction == "bullish":
            target_price = round(current_price * (1 + confidence * 0.1), 4)
        elif direction == "bearish":
            target_price = round(current_price * (1 - confidence * 0.1), 4)

        summaries = "\n".join(
            f"[{name.upper()}] ({data.get('direction','?')} / conf:{data.get('confidence',0):.2f}): {data.get('summary','')}"
            for name, data in agent_outputs.items()
            if name != "_critic"
        )
        all_key_points = []
        for name, data in agent_outputs.items():
            if name != "_critic":
                all_key_points.extend(data.get("key_points", [])[:2])

        system = (
            "You are a senior investment analyst synthesizing multiple analysis reports. "
            "Return ONLY valid JSON. No markdown. "
            "Write all text fields (reasoning, key_risks, catalysts, recommendation) in Thai language. "
            "Keep JSON keys, direction values (bullish/bearish/neutral), and numbers in English."
        )

        # inject similar historical cases
        similar_section = ""
        if similar_cases:
            from services.rag import format_cases_for_prompt
            similar_section = "\n\n" + format_cases_for_prompt(similar_cases)

        # inject agent track record so synthesis is aware of which agents to trust
        track_section = ""
        if agent_feedback and agent_feedback.get("prompt_section"):
            track_section = "\n\n" + agent_feedback["prompt_section"]

        user = f"""Synthesize these analysis reports for {symbol} ({timeframe} outlook):

{summaries}

KEY POINTS FROM ALL AGENTS:
{chr(10).join(f'- {p}' for p in all_key_points)}

MARKET DATA: Price={current_price}, Change={market_data.get('price_change_pct')}%{track_section}{similar_section}

Return this exact JSON:
{{
  "reasoning": "<comprehensive 3-4 sentence synthesis explaining the final prediction and why>",
  "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "catalysts": ["<catalyst 1>", "<catalyst 2>"],
  "recommendation": "<actionable recommendation in 1 sentence>"
}}"""

        try:
            synth = BaseAgent()._parse_json(BaseAgent()._call_llm(system, user, max_tokens=1500))
        except Exception:
            synth = {
                "reasoning": f"จากการวิเคราะห์หลายมิติ {symbol} แสดงสัญญาณ{direction} ด้วยความเชื่อมั่น {confidence:.0%} สำหรับกรอบเวลา {timeframe}",
                "key_risks": ["ความผันผวนของตลาด", "ความไม่แน่นอนเชิงมหภาค"],
                "catalysts": [],
                "recommendation": f"ติดตาม {symbol} อย่างใกล้ชิด",
            }

        # critic pass — challenge the synthesis
        pre_critic_synthesis = {
            "direction": direction,
            "confidence": confidence,
            "reasoning": synth.get("reasoning", ""),
        }
        critic_result = self.critic.critique(symbol, pre_critic_synthesis, agent_outputs, market_data)

        # apply critic's confidence adjustment and optional direction revision
        final_confidence = round(
            min(max(confidence + critic_result["confidence_adjustment"], 0.0), 1.0), 3
        )
        final_direction = direction
        if not critic_result["agrees_with_direction"]:
            final_direction = critic_result.get("revised_direction", direction)

        # store critic output inside agent_outputs for transparency/storage
        agent_outputs_with_critic = {
            **agent_outputs,
            "_critic": critic_result,
        }

        return {
            "direction": final_direction,
            "confidence": final_confidence,
            "current_price": current_price,
            "target_price": target_price,
            "timeframe": timeframe,
            "reasoning": synth.get("reasoning", ""),
            "key_risks": synth.get("key_risks", []),
            "catalysts": synth.get("catalysts", []),
            "recommendation": synth.get("recommendation", ""),
            "critic": critic_result,
            "agent_outputs": agent_outputs_with_critic,
            "weights_used": weights or DEFAULT_WEIGHTS,
        }

    def analyze(
        self,
        symbol: str,
        market_data: dict,
        news: list[dict],
        timeframe: str = "1w",
        similar_cases: list[dict] | None = None,
        agent_feedback: dict | None = None,
    ) -> dict:
        agent_outputs = self.run_all_agents(symbol, market_data, news)
        return self.synthesize(symbol, market_data, agent_outputs, timeframe, similar_cases, agent_feedback)
