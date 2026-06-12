"""OpenAI-compatible adapter — serves BOTH GPT and Kimi/Moonshot.

The only difference between GPT and Kimi is base_url + api key, so one adapter
covers both. This is the concrete payoff of "three models, two SDK shapes."
"""
from __future__ import annotations

from .base import Completion, Provider, ProviderUnavailable, _require_key


class OpenAICompatProvider(Provider):
    def __init__(self, name: str, cfg: dict):
        self.name = name
        self.model = cfg.get("model", "gpt-5")
        self.base_url = cfg.get("base_url", "https://api.openai.com/v1")
        self._key = _require_key(cfg)
        try:
            import openai
        except ImportError as exc:
            raise ProviderUnavailable("pip install 'iceni[models]' (openai SDK missing)") from exc
        self._client = openai.OpenAI(api_key=self._key, base_url=self.base_url)

    def complete(self, prompt: str) -> Completion:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        return Completion(
            text=text,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
        )
