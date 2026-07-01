from agents.base_agent import BaseAgent


class FundamentalAgent(BaseAgent):
    name = "fundamental"

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        system = (
            "You are a fundamental analysis expert. Analyze financial metrics and return ONLY valid JSON. "
            "No markdown, no explanation outside JSON."
        )

        metrics = {
            "price": market_data.get("price"),
            "pe_ratio": market_data.get("pe_ratio"),
            "eps": market_data.get("eps"),
            "revenue": market_data.get("revenue"),
            "market_cap": market_data.get("market_cap"),
            "profit_margins": market_data.get("profit_margins"),
            "debt_to_equity": market_data.get("debt_to_equity"),
            "sector": market_data.get("sector"),
            "52w_high": market_data.get("high_52w"),
            "52w_low": market_data.get("low_52w"),
        }

        user = f"""Perform fundamental analysis for {symbol}.

FUNDAMENTAL METRICS:
{chr(10).join(f'- {k}: {v}' for k, v in metrics.items() if v is not None)}

Return this exact JSON structure:
{{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": <float 0.0-1.0>,
  "summary": "<2-3 sentence fundamental assessment>",
  "key_points": ["<point 1>", "<point 2>", "<point 3>"],
  "valuation": "overvalued" | "fair" | "undervalued",
  "fair_value_estimate": <float or null>,
  "financial_health": "strong" | "moderate" | "weak"
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
                "summary": f"Fundamental analysis failed: {str(e)}",
                "key_points": [],
            }
