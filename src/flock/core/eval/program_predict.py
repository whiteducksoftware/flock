"""PredictProgram skeleton — one-shot structured generation (placeholder)."""

from __future__ import annotations

from typing import Any, AsyncIterator
import json

from .lm_client import LMClient, LMRequest
from .prompt_builder import build_prompt

from .program_base import Program
from .stream_adapter import stream_text


class PredictProgram(Program):
    def __init__(self, model: str | None = None, description: str | None = None,
                 input_spec: Any | None = None, output_spec: Any | None = None,
                 **kwargs) -> None:
        self.model = model
        self.description = description
        self.input_spec = input_spec
        self.output_spec = output_spec
        self.options = kwargs

    async def run(self, *, inputs: dict[str, Any]) -> dict[str, Any]:
        # If no model is provided, stay deterministic (used by tests): echo inputs
        if not self.model:
            return {**inputs}

        instruction, json_schema = build_prompt(
            agent_name=self.options.get("agent_name", "agent"),
            description=self.description,
            input_spec=self.input_spec,
            output_spec=self.output_spec,
        )

        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps({"inputs": inputs})},
        ]

        extra: dict[str, Any] | None = {}
        if json_schema:
            # Try to use JSON schema response_format if provider supports it
            extra["response_format"] = {"type": "json_schema", "json_schema": json_schema}
        else:
            # Encourage JSON object outputs
            extra["response_format"] = {"type": "json_object"}

        client = LMClient(model=self.model)
        result, _usage = await client.generate(
            LMRequest(model=self.model, messages=messages, extra=extra)
        )
        text = result.get("text")
        if not text:
            return {"text": None}
        # Try parse JSON
        try:
            return json.loads(text)
        except Exception:
            # Fallback to wrapping raw text
            return {"text": text}

    async def run_stream(self, *, inputs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        # If no model is provided, yield final echo result
        if not self.model:
            yield {"event": "final", "result": await self.run(inputs=inputs)}
            return

        instruction, json_schema = build_prompt(
            agent_name=self.options.get("agent_name", "agent"),
            description=self.description,
            input_spec=self.input_spec,
            output_spec=self.output_spec,
        )
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps({"inputs": inputs})},
        ]
        extra: dict[str, Any] | None = {}
        if json_schema:
            extra["response_format"] = {"type": "json_schema", "json_schema": json_schema}
        else:
            extra["response_format"] = {"type": "json_object"}

        client = LMClient(model=self.model)
        async for ev in stream_text(client, LMRequest(model=self.model, messages=messages, extra=extra)):
            yield ev
        yield {"event": "final", "result": await self.run(inputs=inputs)}
