"""Claude adapter (Anthropic SDK). Lazy-imported."""
from __future__ import annotations

from .base import Completion, Provider, ProviderUnavailable, _require_key


class AnthropicProvider(Provider):
    def __init__(self, name: str, cfg: dict):
        self.name = name
        self.model = cfg.get("model", "claude-opus-4-8")
        self._key = _require_key(cfg)
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise ProviderUnavailable("pip install 'iceni[models]' (anthropic SDK missing)") from exc
        self._anthropic = anthropic

    def complete(self, prompt: str) -> Completion:
        client = self._anthropic.Anthropic(api_key=self._key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(getattr(b, "text", "") for b in msg.content)
        usage = getattr(msg, "usage", None)
        return Completion(
            text=text,
            tokens_in=getattr(usage, "input_tokens", 0) or 0,
            tokens_out=getattr(usage, "output_tokens", 0) or 0,
        )
