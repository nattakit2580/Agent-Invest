import json
import httpx
from config import get_settings

settings = get_settings()


class BaseAgent:
    name: str = "base"

    def _get_model(self) -> str:
        """Return per-agent model override if set, else global openrouter_model."""
        key = f"{self.name}_agent_model"
        override = getattr(settings, key, "") or ""
        return override.strip() or settings.openrouter_model

    def _call_llm(self, system: str, user: str, max_tokens: int = 1024) -> str:
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

        response = httpx.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _parse_json(self, text: str) -> dict:
        # Walk backwards from the last } to find the matching { — handles
        # ReAct preamble text that may contain stray { } characters.
        end = text.rfind("}")
        if end == -1:
            raise ValueError("No JSON found in response")
        depth = 0
        for i in range(end, -1, -1):
            if text[i] == "}":
                depth += 1
            elif text[i] == "{":
                depth -= 1
                if depth == 0:
                    return json.loads(text[i : end + 1])
        raise ValueError("No complete JSON object found in response")

    def analyze(self, symbol: str, market_data: dict, news: list[dict]) -> dict:
        raise NotImplementedError
