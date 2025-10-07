"""Helper functions for Flock MCP Functionality."""

import hashlib
import json

from mcp.client.stdio import get_default_environment


def get_default_env() -> dict[str, str]:
    """Returns a default environment object.

    Including only environment-variables
    deemed safe to inherit.
    """
    return get_default_environment()


def cache_key_generator(agent_id: str, run_id: str, *args, **kwargs) -> str:
    """Helper function to generate cache keys for Flock MCP caches."""
    # merge args and kwargs into a single string
    merged = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    args_digest = hashlib.md5(merged.encode(), usedforsecurity=False).hexdigest()
    return f"{agent_id}:{run_id}:{args_digest}"
