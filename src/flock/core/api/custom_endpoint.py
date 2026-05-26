"""Lightweight helper object for declaring additional REST routes.

Developers can pass instances of :class:`FlockEndpoint` to
``Flock.start_api(custom_endpoints=[...])`` instead of the terse dictionary
syntax.  The class carries optional Pydantic request/response models plus
OpenAPI metadata so the generated docs look perfect.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

__all__ = [
    "FlockEndpoint",
]


class FlockEndpoint(BaseModel):
    """Declarative description of an extra API route."""

    path: str
    methods: list[str] = ["GET"]
    callback: Callable[..., Any]

    # Optional schema models
    request_model: type[BaseModel] | None = None
    response_model: type[BaseModel] | None = None
    # Query-string parameters as a Pydantic model (treated as Depends())
    query_model: type[BaseModel] | None = None

    # OpenAPI / Swagger metadata
    summary: str | None = None
    description: str | None = None
    name: str | None = None  # Route name in FastAPI
    include_in_schema: bool = True

    # FastAPI dependency injections (e.g. security)
    dependencies: list[Any] | None = None

    model_config = {
        "arbitrary_types_allowed": True,
        "validate_default": True,
    }
