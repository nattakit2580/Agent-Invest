from agents.base_agent import BaseAgent


class NewsAgent(BaseAgent):
    name = "news"

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        if not news:
            return {
                "direction": "neutral",
                "confidence": 0.3,
                "summary": "ไม่มีข้อมูลข่าวสำหรับการวิเคราะห์",
                "key_points": ["ข้อมูลข่าวไม่เพียงพอ"],
                "reasoning_trace": "ไม่มีข่าว — ไม่สามารถประเมินผลกระทบได้",
            }

        news_text = "\n".join(
            f"- [{n.get('source', '')}] {n['title']}: {n.get('summary', '')}"
            for n in news[:12]
        )

        system = (
            "You are a financial news analyst using the ReAct reasoning framework. "
            "Think step by step before reaching your conclusion, then output JSON. "
            "Write all Thai text fields (summary, key_points, major_events, reasoning_trace) in Thai. "
            "Keep JSON keys, direction values (bullish/bearish/neutral), and numbers in English. "
            "In your thinking steps, use only plain text — do NOT use curly braces {{ }} until the final JSON."
        )

        user = f"""Analyze these news articles about {symbol} using the ReAct framework:

NEWS ARTICLES:
{news_text}

Follow these reasoning steps before outputting JSON:

1. SCAN — Which 3-5 headlines are most market-moving? What is their individual tone?
2. AGGREGATE — What is the net news sentiment? Are themes consistent or mixed?
3. CHALLENGE — What news headlines could reverse or undermine the dominant view?
4. DECIDE — Overall direction and confidence level

After completing all 4 steps above, output this JSON as the final block:
{{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": <float 0.0-1.0>,
  "summary": "<2-3 sentence Thai summary of news impact>",
  "key_points": ["<Thai point 1>", "<Thai point 2>", "<Thai point 3>"],
  "sentiment_score": <float -1.0 to 1.0>,
  "major_events": ["<Thai event 1>", "<Thai event 2>"],
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
                "summary": f"วิเคราะห์ข่าวไม่สำเร็จ: {str(e)}",
                "key_points": [],
                "reasoning_trace": "",
            }
