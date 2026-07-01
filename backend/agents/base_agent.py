import json
import anthropic
from config import get_settings

settings = get_settings()
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


class BaseAgent:
    name: str = "base"

    def _call_claude(self, system: str, user: str, max_tokens: int = 1024) -> str:
        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

    def _parse_json(self, text: str) -> dict:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")
        return json.loads(text[start:end])

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        raise NotImplementedError
