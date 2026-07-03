from agents.base_agent import BaseAgent


class TechnicalAgent(BaseAgent):
    name = "technical"

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        system = (
            "You are a technical analysis expert. Analyze chart indicators and return ONLY valid JSON. "
            "No markdown, no explanation outside JSON."
        )

        indicators = {
            "current_price": market_data.get("price"),
            "price_change_pct_1d": market_data.get("price_change_pct"),
            "rsi_14": market_data.get("rsi_14"),
            "macd": market_data.get("macd"),
            "macd_signal": market_data.get("macd_signal"),
            "macd_diff": market_data.get("macd_diff"),
            "sma_20": market_data.get("sma_20"),
            "sma_50": market_data.get("sma_50"),
            "bb_upper": market_data.get("bb_upper"),
            "bb_lower": market_data.get("bb_lower"),
            "52w_high": market_data.get("high_52w"),
            "52w_low": market_data.get("low_52w"),
        }

        history = market_data.get("price_history", [])
        price_trend = ""
        if len(history) >= 5:
            prices = [h["close"] for h in history[-5:]]
            price_trend = f"Last 5 days: {' -> '.join(str(p) for p in prices)}"

        user = f"""Perform technical analysis for {symbol}.

TECHNICAL INDICATORS:
{chr(10).join(f'- {k}: {v}' for k, v in indicators.items() if v is not None)}

PRICE TREND:
{price_trend}

Return this exact JSON structure:
{{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": <float 0.0-1.0>,
  "summary": "<2-3 sentence technical assessment>",
  "key_points": ["<point 1>", "<point 2>", "<point 3>"],
  "trend": "uptrend" | "downtrend" | "sideways",
  "support_level": <float or null>,
  "resistance_level": <float or null>,
  "rsi_signal": "overbought" | "oversold" | "neutral",
  "macd_signal": "bullish_crossover" | "bearish_crossover" | "neutral"
}}"""

        try:
            result = self._parse_json(self._call_llm(system, user))
            result.setdefault("direction", "neutral")
            result.setdefault("confidence", 0.5)
            result.setdefault("summary", "")
            result.setdefault("key_points", [])
            return result
        except Exception as e:
            return {
                "direction": "neutral",
                "confidence": 0.3,
                "summary": f"Technical analysis failed: {str(e)}",
                "key_points": [],
            }
