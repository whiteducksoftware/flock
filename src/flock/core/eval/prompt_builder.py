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

from flock.core.util.splitter import parse_schema


def _json_schema_for_type(type_str: str) -> dict[str, Any]:
    t = type_str.strip()
    # Builtins
    if t in ("str", "string"):
        return {"type": "string"}
    if t in ("int", "integer"):
        return {"type": "integer"}
    if t in ("float", "number"):
        return {"type": "number"}
    if t in ("bool", "boolean"):
        return {"type": "boolean"}

    # Literal[...] -> enum
    if t.startswith("Literal[") and t.endswith("]"):
        inner = t[len("Literal[") : -1]
        # crude split on commas at top-level (no nesting expected here)
        # strip quotes
        def _clean(v: str) -> str:
            v = v.strip()
            if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                return v[1:-1]
            return v

        values = [
            _clean(x)
            for x in _split_commas_top_level(inner)
            if x.strip() != ""
        ]
        return {"type": "string", "enum": values}

    # list[...] -> array
    if t.startswith("list[") and t.endswith("]"):
        inner = t[len("list[") : -1]
        return {"type": "array", "items": _json_schema_for_type(inner)}

    # dict[key, value] or dict[key:value]
    if t.startswith("dict[") and t.endswith("]"):
        inner = t[len("dict[") : -1]
        # Very simple parse: split on first comma or colon
        key_t = "string"
        val_t = "string"
        sep = ":" if ":" in inner else ","
        parts = [p.strip() for p in inner.split(sep, 1)]
        if len(parts) == 2:
            key_t, val_t = parts
        return {
            "type": "object",
            "additionalProperties": _json_schema_for_type(val_t),
        }

    # Fallback
    return {"type": "string"}


def _split_commas_top_level(s: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    buf = []
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


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
    # Instruction
    base_desc = (description or "").strip()
    instruction = (
        (base_desc + "\n\n") if base_desc else ""
    ) + (
        "You are an agent named '" + agent_name + "'. "
        "Return strictly a JSON object that matches the declared output schema."
    )

    # Schema: Pydantic or string spec
    schema: dict[str, Any] | None = None
    try:
        if isinstance(output_spec, type) and issubclass(output_spec, BaseModel):
            # Pydantic v2 JSON schema
            js = output_spec.model_json_schema()
            # Wrap for OpenAI JSON schema response_format
            schema = {
                "name": f"{agent_name}_output",
                "schema": js,
                "strict": True,
            }
        elif isinstance(output_spec, str) and output_spec.strip():
            fields = parse_schema(output_spec)
            properties: dict[str, Any] = {}
            required: list[str] = []
            for name, type_str, desc in fields:
                prop = _json_schema_for_type(type_str)
                if desc:
                    prop["description"] = desc
                properties[name] = prop
                required.append(name)
            js = {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            }
            schema = {"name": f"{agent_name}_output", "schema": js, "strict": True}
    except Exception:
        schema = None

    return instruction, schema
