from agents.base_agent import BaseAgent


class SentimentAgent(BaseAgent):
    name = "sentiment"

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        system = (
            "You are a market sentiment analyst using the ReAct reasoning framework. "
            "Think step by step before reaching your conclusion, then output JSON. "
            "Write all Thai text fields (summary, key_points, reasoning_trace) in Thai. "
            "Keep JSON keys, direction/mood/momentum/crowd_sentiment enum values, and numbers in English. "
            "In your thinking steps, use only plain text — do NOT use curly braces {{ }} until the final JSON."
        )

        price = market_data.get("price", 0)
        sma_20 = market_data.get("sma_20")
        sma_50 = market_data.get("sma_50")
        high_52w = market_data.get("high_52w")
        low_52w = market_data.get("low_52w")

        position_vs_52w = None
        if high_52w and low_52w and high_52w != low_52w:
            position_vs_52w = round((price - low_52w) / (high_52w - low_52w) * 100, 1)

        above_sma20 = price > sma_20 if sma_20 else None
        above_sma50 = price > sma_50 if sma_50 else None

        news_titles = [n.get("title", "") for n in news[:8]]

        user = f"""Analyze market sentiment for {symbol} using the ReAct framework:

PRICE POSITION:
- Current: {price}
- Position in 52-week range: {position_vs_52w}% (0=52w low, 100=52w high)
- Above SMA20: {above_sma20}
- Above SMA50: {above_sma50}
- Volume: {market_data.get('volume')}

RECENT NEWS HEADLINES:
{chr(10).join(f'- {t}' for t in news_titles)}

Follow these reasoning steps before outputting JSON:

1. GAUGE — What does price position (52-week range, vs SMAs) tell you about current market temperature?
2. INTERPRET — Are recent headlines driven by genuine fundamental news or by fear/greed?
3. MOMENTUM — Is sentiment improving (higher lows, positive headlines) or deteriorating?
4. DECIDE — What is the crowd's current mood and where is it likely to push price?

After completing all 4 steps above, output this JSON as the final block:
{{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": <float 0.0-1.0>,
  "summary": "<2-3 sentence Thai sentiment assessment>",
  "key_points": ["<Thai point 1>", "<Thai point 2>", "<Thai point 3>"],
  "market_mood": "fear" | "greed" | "neutral",
  "momentum": "strong_up" | "weak_up" | "flat" | "weak_down" | "strong_down",
  "crowd_sentiment": "very_bearish" | "bearish" | "neutral" | "bullish" | "very_bullish",
  "reasoning_trace": "<1-2 sentence Thai explanation of WHY this direction was chosen>"
}}"""

        try:
            result = self._parse_json(self._call_llm(system, user, max_tokens=1500))
            result.setdefault("direction", "neutral")
            result.setdefault("confidence", 0.5)
            result.setdefault("summary", "")
            result.setdefault("key_points", [])
            result.setdefault("reasoning_trace", "")
            return result
        except Exception as e:
            return {
                "direction": "neutral",
                "confidence": 0.3,
                "summary": f"วิเคราะห์ sentiment ไม่สำเร็จ: {str(e)}",
                "key_points": [],
                "reasoning_trace": "",
            }
