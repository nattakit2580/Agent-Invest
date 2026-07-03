from agents.base_agent import BaseAgent


class NewsAgent(BaseAgent):
    name = "news"

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        if not news:
            return {
                "direction": "neutral",
                "confidence": 0.3,
                "summary": "No news data available for analysis.",
                "key_points": ["Insufficient news data"],
            }

        news_text = "\n".join(
            f"- [{n.get('source','')}] {n['title']}: {n.get('summary','')}"
            for n in news[:12]
        )

        system = (
            "You are a financial news analyst. Analyze news articles and return ONLY valid JSON. "
            "No markdown, no explanation outside JSON. "
            "Write all text fields (summary, key_points, major_events) in Thai language. "
            "Keep JSON keys, direction values (bullish/bearish/neutral), and numbers in English."
        )
        user = f"""Analyze these recent news articles about {symbol} and their potential market impact.

NEWS ARTICLES:
{news_text}

Return this exact JSON structure:
{{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": <float 0.0-1.0>,
  "summary": "<2-3 sentence summary of news impact>",
  "key_points": ["<point 1>", "<point 2>", "<point 3>"],
  "sentiment_score": <float -1.0 to 1.0>,
  "major_events": ["<event 1>", "<event 2>"]
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
                "summary": f"News analysis failed: {str(e)}",
                "key_points": [],
            }
