"""ICENI — auto-discovered, cross-model-calibrated, self-evolving prompt aliases.

The load-bearing idea: the human-readable alias name is NOT the trust anchor.
A name resolves locally (petname) to a cryptographic identity, which signs a
content-addressed, model-agnostic intent that is rendered per model.
"""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("iceni")
except PackageNotFoundError:        # running from a source tree that isn't installed
    __version__ = "0.0.0+unknown"
