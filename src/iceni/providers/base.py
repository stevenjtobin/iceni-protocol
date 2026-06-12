"""Provider protocol + registry. Adapters lazy-import their SDK so the core
runs (create/list/show/compare --preview) with zero model dependencies."""
from __future__ import annotations

import os
from dataclasses import dataclass


class ProviderUnavailable(Exception):
    """SDK not installed, or API key env var unset. Carries a human-friendly reason."""


@dataclass
class Completion:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0


class Provider:
    name: str = "base"

    def complete(self, prompt: str) -> Completion:  # pragma: no cover - interface
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        # Rough fallback (~4 chars/token); real adapters override per tokenizer.
        return max(1, len(text) // 4)


def _require_key(model_cfg: dict) -> str:
    env = model_cfg.get("api_key_env")
    key = os.environ.get(env) if env else None
    if not key:
        raise ProviderUnavailable(f"set ${env} to call this model (or use --preview)")
    return key


def get_provider(model_key: str, cfg: dict) -> Provider:
    model_cfg = cfg.get("models", {}).get(model_key)
    if not model_cfg:
        raise ProviderUnavailable(f"model '{model_key}' is not defined in config.toml")
    provider = model_cfg.get("provider")
    if provider == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(model_key, model_cfg)
    if provider == "openai_compat":
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(model_key, model_cfg)
    raise ProviderUnavailable(f"unknown provider '{provider}' for model '{model_key}'")
