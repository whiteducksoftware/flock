"""Public package API for flock."""

from __future__ import annotations


# Load environment variables from .env file early
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv not available, environment variables must be set manually
    pass

from flock.cli import main
from flock.core import Flock, start_orchestrator
from flock.registry import flock_tool, flock_type


def _register_optional_providers() -> None:
    """Auto-register optional LiteLLM providers when dependencies are available."""
    try:
        from flock.engines.providers.transformers_provider import (
            register_transformers_provider,
        )

        register_transformers_provider()
    except ImportError:
        pass  # transformers not installed, skip registration


# Register optional providers at import time
_register_optional_providers()


__all__ = [
    "Flock",
    "flock_tool",
    "flock_type",
    "main",
    "start_orchestrator",
]
