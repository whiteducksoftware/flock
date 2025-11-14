"""Flock re-exports for common DSPy adapters.

This module exposes the most commonly used DSPy adapters through the Flock
namespace so users don't need to import directly from ``dspy.adapters``.
"""

from __future__ import annotations

from dspy.adapters import ChatAdapter, JSONAdapter, TwoStepAdapter, XMLAdapter
from dspy.adapters.baml_adapter import BAMLAdapter


__all__ = [
    "BAMLAdapter",
    "ChatAdapter",
    "JSONAdapter",
    "TwoStepAdapter",
    "XMLAdapter",
]
