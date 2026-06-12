"""The model-agnostic intent object (OQ4 = structured JSON, unanimous vote).

This is the canonical, human-editable representation that gets rendered per
model. It is content-addressed: the sha256 of its canonical JSON form IS its
identity in the version DAG.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass
class Intent:
    goal: str
    inputs: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    outputs: dict = field(default_factory=dict)
    style_hints: dict = field(default_factory=dict)  # per-model rendering hints, e.g. {"claude": "XML tags"}

    def to_dict(self) -> dict:
        return asdict(self)

    def canonical_json(self) -> str:
        """Deterministic serialization for hashing + signing (sorted keys, tight separators)."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, d: dict) -> "Intent":
        return cls(
            goal=d.get("goal", ""),
            inputs=list(d.get("inputs", [])),
            constraints=list(d.get("constraints", [])),
            outputs=dict(d.get("outputs", {})),
            style_hints=dict(d.get("style_hints", {})),
        )

    @classmethod
    def from_json(cls, s: str) -> "Intent":
        return cls.from_dict(json.loads(s))
