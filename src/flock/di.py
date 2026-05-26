from __future__ import annotations

"""Flock – Dependency-Injection helpers.

This module provides a very small façade over the `wd.di` container so that
other parts of the codebase do not need to know where the active container is
stored.  The bootstrap code – usually located in the runner initialisation –
should store the `ServiceProvider` instance (returned by ``ServiceCollection.
build()``) on the `FlockContext` under the key ``di.container``.

Example
-------
>>> from wd.di import ServiceCollection
>>> sc = ServiceCollection()
>>> sc.add_singleton(str, lambda _: "hello")
>>> container = sc.build()
>>> ctx = FlockContext()
>>> ctx.set_variable("di.container", container)
>>> from flock.di import get_current_container
>>> assert get_current_container(ctx).get_service(str) == "hello"
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from wd.di.container import (
        ServiceProvider,  # noqa: F401 – import only for typing
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
