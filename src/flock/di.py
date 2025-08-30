"""Flock - Dependency-Injection helpers.

This module provides a small facade over `wd.di` so other parts of the
codebase do not need to know where the active container is stored.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from wd.di.container import (
        ServiceProvider,  # noqa: F401 - import only for typing
    )

    from flock.core.context.context import FlockContext


def get_current_container(context: FlockContext | None = None):
    """Return the active `wd.di` container from *context* if present.

    If *context* is ``None`` or no container has been attached to it the
    function returns ``None``.
    """
    if context is None:
        return None
    return context.get_variable("di.container")
