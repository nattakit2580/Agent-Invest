from agents.base_agent import BaseAgent


class FundamentalAgent(BaseAgent):
    name = "fundamental"

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        system = (
            "You are a fundamental analysis expert using the ReAct reasoning framework. "
            "Think step by step before reaching your conclusion, then output JSON. "
            "Write all Thai text fields (summary, key_points, reasoning_trace) in Thai. "
            "Keep JSON keys, direction values (bullish/bearish/neutral), valuation/health enums, and numbers in English. "
            "In your thinking steps, use only plain text — do NOT use curly braces {{ }} until the final JSON."
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

        extra_sections = ""
        research_context = market_data.get("research_context", "")
        if research_context:
            extra_sections += f"\n\nRESEARCH CONTEXT (from papers & SEC filings):\n{research_context}"
        graph_context = market_data.get("graph_context", "")
        if graph_context:
            extra_sections += f"\n\n{graph_context}"

        user = f"""Perform fundamental analysis for {symbol} using the ReAct framework:

FUNDAMENTAL METRICS:
{chr(10).join(f'- {k}: {v}' for k, v in metrics.items() if v is not None)}{extra_sections}

Follow these reasoning steps before outputting JSON:

1. MEASURE — Extract and state the 3-4 most important metrics (P/E vs sector norm, debt level, margins)
2. EVALUATE — Are these metrics healthy or concerning for this type of company/sector?
3. COMPARE — Does current valuation look expensive, fair, or cheap vs fundamentals?
4. DECIDE — What is the fundamental investment case and confidence?

After completing all 4 steps above, output this JSON as the final block:
{{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": <float 0.0-1.0>,
  "summary": "<2-3 sentence Thai fundamental assessment>",
  "key_points": ["<Thai point 1>", "<Thai point 2>", "<Thai point 3>"],
  "valuation": "overvalued" | "fair" | "undervalued",
  "fair_value_estimate": <float or null>,
  "financial_health": "strong" | "moderate" | "weak",
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
                "summary": f"วิเคราะห์ fundamental ไม่สำเร็จ: {str(e)}",
                "key_points": [],
                "reasoning_trace": "",
            }
