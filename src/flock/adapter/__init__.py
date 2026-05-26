from __future__ import annotations

"""Adapter package for pluggable vector-store back-ends.

Importing the package will NOT import heavy third-party clients by default –
individual adapters are only loaded when referenced explicitly.
"""

from .vector_base import VectorAdapter, VectorHit

__all__ = [
    "VectorAdapter",
    "VectorHit",
]
