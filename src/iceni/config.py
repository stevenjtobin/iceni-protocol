"""Config + filesystem layout for ICENI.

Everything lives under ~/.iceni (override with $ICENI_HOME):
  config.toml   model definitions, default model, thresholds
  aliases.db    SQLite store
  keys/         Ed25519 private keys, one file per canonical_id
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("ICENI_HOME", str(Path.home() / ".iceni")))


def db_path() -> Path:
    return home() / "aliases.db"


def keys_dir() -> Path:
    return home() / "keys"


def config_path() -> Path:
    return home() / "config.toml"


# Phase-1 model set: Kimi + Claude + GPT. GPT and Kimi share the OpenAI-compatible adapter.
DEFAULT_CONFIG = """\
# ICENI config — edit model ids / endpoints to taste.
default_model = "claude"

[models.claude]
provider = "anthropic"
model = "claude-opus-4-8"
api_key_env = "ANTHROPIC_API_KEY"

[models.gpt]
provider = "openai_compat"
model = "gpt-5"
base_url = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"

[models.kimi]
provider = "openai_compat"
model = "kimi-k2"
base_url = "https://api.moonshot.ai/v1"
api_key_env = "MOONSHOT_API_KEY"

[discovery]
min_cluster_size = 5            # HDBSCAN
suggest_precision_target = 0.70

[drift]
adwin_delta = 0.002
cosine_warn = 0.85             # cheap pre-filter; directional metric is the trigger
cosine_block = 0.75
"""


def ensure_home() -> None:
    home().mkdir(parents=True, exist_ok=True)
    keys_dir().mkdir(parents=True, exist_ok=True)
    if not config_path().exists():
        config_path().write_text(DEFAULT_CONFIG, encoding="utf-8")


def load() -> dict:
    ensure_home()
    with open(config_path(), "rb") as fh:
        return tomllib.load(fh)
