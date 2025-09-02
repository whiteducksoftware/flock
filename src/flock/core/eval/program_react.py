"""ReActProgram — bounded tool-use loop with JSON actions.

This native ReAct implementation asks the model to produce JSON actions or a
final result. At each step:
 - The model emits {"action": name, "args": {...}, "reason": str?}
 - We call the tool, capture the observation, and continue
 - Or the model emits {"final": {...}, "reason": str?} and we return

This avoids third-party libraries and aims to be robust and testable.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping
import json

from .lm_client import LMClient, LMRequest
from .program_base import Program
from .tool_adapter import ToolAdapter


class ReActProgram(Program):
    def __init__(
        self,
        model: str | None = None,
        description: str | None = None,
        input_spec: Any | None = None,
        output_spec: Any | None = None,
        tools: Mapping[str, Any] | None = None,
        max_steps: int = 8,
        agent_name: str = "agent",
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.description = description or "You reason step by step and use tools when helpful."
        self.input_spec = input_spec
        self.output_spec = output_spec
        self.tools = dict(tools or {})
        self.max_steps = max_steps
        self.agent_name = agent_name
        self.options = kwargs
        self._tool_adapter = ToolAdapter()

    def _tool_manifest(self) -> str:
        if not self.tools:
            return "(no tools available)"
        lines = []
        for name, fn in self.tools.items():
            doc = getattr(fn, "__doc__", None) or ""
            doc = " ".join(doc.split()) if isinstance(doc, str) else ""
            lines.append(f"- {name}: {doc}")
        return "\n".join(lines)

    def _response_schema(self) -> dict[str, Any]:
        # JSON schema that allows either an action or a final
        return {
            "name": f"{self.agent_name}_react_step",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "args": {"type": "object", "additionalProperties": True},
                    "final": {"type": "object", "additionalProperties": True},
                    "reason": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }

    def _build_messages(self, inputs: dict[str, Any], scratch: list[dict[str, str]]) -> list[dict[str, str]]:
        sys = (
            f"You are an agent named '{self.agent_name}'.\n"
            f"{self.description}\n\n"
            f"TOOLS:\n{self._tool_manifest()}\n\n"
            "You operate in steps. At each step, output a JSON object.\n"
            "Either propose a tool call: {\"action\": <tool_name>, \"args\": {...}}\n"
            "Or conclude: {\"final\": {...}}. Optionally include a short 'reason'.\n"
            "Do not include any other text besides JSON."
        )
        msgs = [{"role": "system", "content": sys}]
        user = {"role": "user", "content": json.dumps({"inputs": inputs})}
        msgs.append(user)
        # Add scratchpad as alternating assistant/user blocks
        msgs.extend(scratch)
        return msgs

    async def run(self, *, inputs: dict[str, Any]) -> dict[str, Any]:
        # Deterministic stub when no model is configured
        if not self.model:
            return {**inputs}

        client = LMClient(model=self.model)
        scratch: list[dict[str, str]] = []
        for _ in range(max(1, self.max_steps)):
            messages = self._build_messages(inputs, scratch)
            extra = {"response_format": {"type": "json_schema", "json_schema": self._response_schema()}}
            result, _usage = await client.generate(LMRequest(model=self.model, messages=messages, extra=extra))
            text = (result.get("text") or "").strip()
            if not text:
                # backoff: treat as final no content
                return {"text": None}
            try:
                payload = json.loads(text)
            except Exception:
                # Invalid JSON; nudge the model by adding a correction
                scratch.append({"role": "user", "content": "Please return valid JSON only."})
                continue

            # Final?
            if isinstance(payload, dict) and "final" in payload:
                final = payload.get("final")
                if isinstance(final, dict):
                    return final
                return {"text": json.dumps(final)}

            # Tool call?
            action = payload.get("action") if isinstance(payload, dict) else None
            if action and action in self.tools:
                args = payload.get("args") if isinstance(payload, dict) else None
                if not isinstance(args, dict):
                    args = {}
                observation = await self._tool_adapter.call(self.tools[action], **args)
                scratch.append(
                    {
                        "role": "assistant",
                        "content": json.dumps({"action": action, "args": args}),
                    }
                )
                scratch.append(
                    {"role": "user", "content": json.dumps({"observation": observation})}
                )
                continue

            # If unknown tool or malformed, ask the model to correct
            scratch.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {"error": "Unknown or malformed action. Use only the listed tools or provide final."}
                    ),
                }
            )

        # Max steps exhausted
        return {"error": "max_steps_exhausted"}

    async def run_stream(self, *, inputs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        # Simple wrapper: yield events on each step
        if not self.model:
            yield {"event": "final", "result": await self.run(inputs=inputs)}
            return

        client = LMClient(model=self.model)
        scratch: list[dict[str, str]] = []
        yield {"event": "start"}
        for step in range(max(1, self.max_steps)):
            messages = self._build_messages(inputs, scratch)
            extra = {"response_format": {"type": "json_schema", "json_schema": self._response_schema()}}
            yield {"event": "step_start", "step": step + 1}
            result, _usage = await client.generate(LMRequest(model=self.model, messages=messages, extra=extra))
            text = (result.get("text") or "").strip()
            try:
                payload = json.loads(text)
            except Exception:
                yield {"event": "warning", "message": "model returned invalid JSON"}
                scratch.append({"role": "user", "content": "Please return valid JSON only."})
                continue

            if isinstance(payload, dict) and "final" in payload:
                final = payload.get("final")
                if not isinstance(final, dict):
                    final = {"text": json.dumps(final)}
                yield {"event": "final", "result": final}
                return

            action = payload.get("action") if isinstance(payload, dict) else None
            if action and action in self.tools:
                args = payload.get("args") if isinstance(payload, dict) else None
                if not isinstance(args, dict):
                    args = {}
                yield {"event": "tool_call", "name": action, "args": args}
                observation = await self._tool_adapter.call(self.tools[action], **args)
                yield {"event": "tool_result", "name": action, "result": observation}
                scratch.append({"role": "assistant", "content": json.dumps({"action": action, "args": args})})
                scratch.append({"role": "user", "content": json.dumps({"observation": observation})})
                continue

            yield {"event": "warning", "message": "unknown or malformed action"}
            scratch.append({"role": "user", "content": json.dumps({"error": "Unknown or malformed action."})})

        yield {"event": "final", "result": {"error": "max_steps_exhausted"}}


# Register program in the global registry when imported
try:
    from .program_base import ProgramRegistry

    ProgramRegistry.register("react", lambda **kw: ReActProgram(**kw))
except Exception:
    # Safe to ignore during some import orders (e.g., type checking)
    pass
