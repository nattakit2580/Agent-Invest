import json
import httpx
from config import get_settings

settings = get_settings()


class BaseAgent:
    name: str = "base"

    def _get_model(self) -> str:
        # Runtime override (admin page) → env default → global default.
        from services.agent_config import resolve_model
        return resolve_model(self.name)

    def _call_llm(self, system: str, user: str, max_tokens: int = 1024) -> str:
        from services.agent_config import get_override
        override = get_override(self.name)
        if override.get("max_tokens"):
            max_tokens = override["max_tokens"]
        temperature = override.get("temperature")

        if settings.use_local_model:
            # Phase 5: route to local fine-tuned model (ollama/vllm, OpenAI-compatible)
            url = f"{settings.local_model_url.rstrip('/')}/chat/completions"
            payload = {
                "model": settings.local_model_name,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            headers = {"Content-Type": "application/json"}
        else:
            url = f"{settings.openrouter_base_url}/chat/completions"
            payload = {
                "model": self._get_model(),
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
        if temperature is not None:
            payload["temperature"] = temperature

        response = httpx.post(url, json=payload, headers=headers, timeout=60)
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
