from agents.base_agent import BaseAgent


class SentimentAgent(BaseAgent):
    name = "sentiment"

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        system = (
            "You are a market sentiment analyst. Analyze overall market mood and return ONLY valid JSON. "
            "No markdown, no explanation outside JSON."
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

        user = f"""Analyze market sentiment for {symbol}.

PRICE POSITION:
- Current: {price}
- Position in 52-week range: {position_vs_52w}% (0=52w low, 100=52w high)
- Above SMA20: {above_sma20}
- Above SMA50: {above_sma50}
- Volume: {market_data.get('volume')}

RECENT NEWS HEADLINES:
{chr(10).join(f'- {t}' for t in news_titles)}

Return this exact JSON structure:
{{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": <float 0.0-1.0>,
  "summary": "<2-3 sentence sentiment assessment>",
  "key_points": ["<point 1>", "<point 2>", "<point 3>"],
  "market_mood": "fear" | "greed" | "neutral",
  "momentum": "strong_up" | "weak_up" | "flat" | "weak_down" | "strong_down",
  "crowd_sentiment": "very_bearish" | "bearish" | "neutral" | "bullish" | "very_bullish"
}}"""

        try:
            result = self._parse_json(self._call_claude(system, user))
            result.setdefault("direction", "neutral")
            result.setdefault("confidence", 0.5)
            result.setdefault("summary", "")
            result.setdefault("key_points", [])
            return result
        except Exception as e:
            return {
                "direction": "neutral",
                "confidence": 0.3,
                "summary": f"Sentiment analysis failed: {str(e)}",
                "key_points": [],
            }
