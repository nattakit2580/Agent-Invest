import json
import httpx
from config import get_settings

settings = get_settings()


class BaseAgent:
    name: str = "base"

    def _call_llm(self, system: str, user: str, max_tokens: int = 1024) -> str:
        payload = {
            "model": settings.openrouter_model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.frontend_url,
            "X-Title": "Agent-Invest",
        }
        response = httpx.post(
            f"{settings.openrouter_base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _parse_json(self, text: str) -> dict:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")
        return json.loads(text[start:end])

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        raise NotImplementedError
