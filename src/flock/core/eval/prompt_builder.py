"""PromptBuilder skeleton — build instruction + JSON schema from contracts.

The PromptBuilder converts Flock agent contracts (string or Pydantic models)
into a stable instruction text and, when supported by the provider, a JSON
schema for structured outputs.
"""

from __future__ import annotations

from typing import Any, Tuple

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover - optional at import time
    BaseModel = object  # type: ignore


def build_prompt(
    agent_name: str,
    description: str | None,
    input_spec: str | type[BaseModel] | None,
    output_spec: str | type[BaseModel] | None,
) -> Tuple[str, dict[str, Any] | None]:
    """Return (instruction_text, json_schema_or_none).

    This is a scaffold; the final implementation will derive JSON schema from
    Pydantic models and generate a compact instruction for string-based specs.
    """
    instruction = f"Agent {agent_name}: produce the declared outputs strictly as JSON."
    schema: dict[str, Any] | None = None
    # TODO: implement Pydantic schema extraction and string-spec parsing.
    return instruction, schema

