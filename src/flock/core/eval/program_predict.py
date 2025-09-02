"""PredictProgram skeleton — one-shot structured generation (placeholder)."""

from __future__ import annotations

from typing import Any, AsyncIterator

from .program_base import Program


class PredictProgram(Program):
    def __init__(self, **kwargs) -> None:
        self.options = kwargs

    async def run(self, *, inputs: dict[str, Any]) -> dict[str, Any]:
        # Placeholder: echo inputs for now; real impl will call LMClient and
        # enforce JSON schema via PromptBuilder.
        return {**inputs}

    async def run_stream(self, *, inputs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        # Placeholder streaming: yield a single final event.
        yield {"event": "final", "result": await self.run(inputs=inputs)}

