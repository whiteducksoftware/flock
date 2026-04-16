"""ExternalEngineComponent — engine that drives an external CLI agent.

External agents live as subprocesses (Claude Code, Codex, …). This engine
plugs them into the standard ``Agent._run_engines`` pipeline:

    artifact published
      → AgentScheduler.schedule_artifact
        → Agent._run_engines
          → ExternalEngineComponent.evaluate
            → adapter.spawn → adapter.monitor → text
            → JSON parse → Pydantic validate → EvalResult

No separate scheduler, no REST return path, no auth tokens required for the
return path. Internal agent results flow through ``EvalResult`` exactly the
same way ``DSPyEngine`` does — the engine is just a different transducer.
"""

from __future__ import annotations

import inspect
import json
import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

from flock.components.agent.base import EngineComponent
from flock.integrations.external.models import (
    AgentOutcome,
    ExternalSessionStore,
    SpawnConfig,
    SQLiteExternalSessionStore,
)
from flock.integrations.external.runtime import ExternalAgentRuntime
from flock.utils.runtime import Context, EvalInputs, EvalResult

logger = logging.getLogger(__name__)


class ExternalEngineExecutionError(RuntimeError):
    """Raised when the external agent fails to produce a usable result.

    Wraps both subprocess failures (non-zero exit, timeout) and output
    parsing/validation failures so the caller can react uniformly.
    """


class ExternalEngineComponent(EngineComponent):
    """Engine that delegates evaluation to an external CLI agent.

    Composes a prompt that includes the input artifact(s) plus the JSON
    schema(s) of the expected output type(s), spawns the configured
    adapter, awaits the result, parses + validates the JSON response into
    typed Pydantic objects, and returns an ``EvalResult``.

    Session resume is supported when the underlying adapter supports it
    and the agent's subscription declared ``session_mode="resume"`` —
    a missing prior session falls back to ``new`` with a warning.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str | None = "external"
    enable_context: bool = False  # External agents get explicit context in the prompt

    # Adapter is a runtime object, not a serializable field.
    adapter: Any = Field(default=None, exclude=True)
    working_dir: str = "."
    spawn_timeout: float = 1800.0
    session_mode: Literal["new", "resume"] | None = None
    additional_env: dict[str, str] = Field(default_factory=dict)

    # Session store is also a runtime object; default factory creates an
    # in-memory store. Production wiring (Unit 2) overrides with the
    # SQLite-backed variant when the blackboard is SQLite-backed.
    _session_store: Any = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        adapter: ExternalAgentRuntime,
        working_dir: str | Path = ".",
        spawn_timeout: float = 1800.0,
        session_mode: Literal["new", "resume"] | None = None,
        session_store: ExternalSessionStore
        | SQLiteExternalSessionStore
        | None = None,
        additional_env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            adapter=adapter,
            working_dir=str(working_dir),
            spawn_timeout=spawn_timeout,
            session_mode=session_mode,
            additional_env=additional_env or {},
            **kwargs,
        )
        # Bypass Pydantic — PrivateAttr default=None gets re-applied during
        # model finalisation after our assignment, so we use object.__setattr__
        # to install the store after Pydantic is done.
        # NB: do NOT use ``or`` — ExternalSessionStore.__len__ makes empty
        # stores falsy.
        store = session_store if session_store is not None else ExternalSessionStore()
        object.__setattr__(self, "_session_store", store)

    # ------------------------------------------------------------------
    # Public hooks
    # ------------------------------------------------------------------

    @property
    def session_store(
        self,
    ) -> ExternalSessionStore | SQLiteExternalSessionStore:
        return self._session_store

    def set_session_store(
        self, store: ExternalSessionStore | SQLiteExternalSessionStore
    ) -> None:
        """Inject a session store (used by orchestrator auto-wiring)."""
        object.__setattr__(self, "_session_store", store)

    # ------------------------------------------------------------------
    # EngineComponent interface
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        agent: Any,
        ctx: Context,
        inputs: EvalInputs,
        output_group: Any,
    ) -> EvalResult:
        """Spawn the external agent, parse its JSON response into typed artifacts."""
        if self.adapter is None:
            raise ExternalEngineExecutionError(
                f"ExternalEngineComponent for agent '{agent.name}' has no adapter configured"
            )

        # Resolve output types from the OutputGroup. Each AgentOutput.spec.model
        # is the Pydantic class we must validate the agent's response against.
        output_types: list[type[BaseModel]] = [
            out.spec.model for out in (output_group.outputs or [])
        ]

        # Side-effect / no-output agents short-circuit: spawn the agent for its
        # side effects, but return an empty EvalResult.
        if not output_types:
            await self._spawn_and_monitor(agent, ctx, inputs, expect_outputs=False)
            return EvalResult.empty()

        outcome = await self._spawn_and_monitor(
            agent, ctx, inputs, expect_outputs=True
        )

        objects = self._parse_outputs(outcome.stdout, output_types, agent.name)
        return EvalResult.from_objects(*objects, agent=agent)

    # ------------------------------------------------------------------
    # Spawn / monitor
    # ------------------------------------------------------------------

    async def _spawn_and_monitor(
        self,
        agent: Any,
        ctx: Context,
        inputs: EvalInputs,
        *,
        expect_outputs: bool,
    ) -> AgentOutcome:
        """Resolve session, build SpawnConfig, spawn, monitor, persist session."""
        # Determine output types again here for prompt composition; cheap.
        output_types: list[type[BaseModel]] = []
        try:
            for sub in getattr(agent, "subscriptions", []) or []:
                if getattr(sub, "session_mode", None):
                    pass  # session_mode is read below
        except Exception:
            pass

        prompt = self._compose_prompt(agent, ctx, inputs, expect_outputs=expect_outputs)

        # Resolve session_mode: per-subscription overrides engine default.
        resolved_session_mode: Literal["new", "resume"] = "new"
        if self.session_mode is not None:
            resolved_session_mode = self.session_mode
        # If the agent has subscription-level session_mode, it wins.
        for sub in getattr(agent, "subscriptions", []) or []:
            sub_mode = getattr(sub, "session_mode", None)
            if sub_mode:
                resolved_session_mode = sub_mode
                break

        artifact_type_for_session = ""
        if inputs.artifacts:
            artifact_type_for_session = inputs.artifacts[0].type or ""

        session_id: str | None = None
        if resolved_session_mode == "resume":
            stored = await self._session_get(agent.name, artifact_type_for_session)
            if stored:
                session_id = stored
            else:
                logger.warning(
                    "Agent %s: session_mode='resume' but no stored session for "
                    "%r — falling back to 'new'",
                    agent.name,
                    artifact_type_for_session,
                )
                resolved_session_mode = "new"

        config = SpawnConfig(
            prompt=prompt,
            working_dir=Path(self.working_dir),
            env_vars=dict(self.additional_env),
            session_id=session_id,
            session_mode=resolved_session_mode,
            timeout=self.spawn_timeout,
        )

        result = await self.adapter.spawn(config)
        try:
            outcome = await self.adapter.monitor(result)
        except Exception:
            # Monitor failure: try to terminate the process if still alive.
            try:
                await self.adapter.terminate(result)
            except Exception:
                logger.exception(
                    "Adapter terminate failed for agent %s after monitor error",
                    agent.name,
                )
            raise

        # Persist session_id for resume on success.
        if outcome.session_id and resolved_session_mode in ("new", "resume"):
            try:
                await self._session_set(
                    agent.name, artifact_type_for_session, outcome.session_id
                )
            except Exception:
                logger.exception(
                    "Failed to persist session for agent %s — resume may fall back",
                    agent.name,
                )

        if not outcome.success:
            raise ExternalEngineExecutionError(
                f"External agent '{agent.name}' exited with code "
                f"{outcome.returncode}: {outcome.stderr.strip() or 'no stderr'}"
            )

        return outcome

    # ------------------------------------------------------------------
    # Prompt composition
    # ------------------------------------------------------------------

    def _compose_prompt(
        self,
        agent: Any,
        ctx: Context,
        inputs: EvalInputs,
        *,
        expect_outputs: bool,
    ) -> str:
        """Build the prompt sent to the external agent.

        Includes:
          - A trace context block (correlation_id, triggering artifact id/type)
            so the external agent can refer back to the request
          - Agent description (if present) as instructions
          - Each input artifact's payload as JSON
          - JSON schemas for each expected output type
          - Strict instruction to reply with only valid JSON
        """
        sections: list[str] = []

        # Trace context — gives the external agent a handle to refer back
        # to the request (correlation_id, triggering artifact metadata).
        trace_context: dict[str, Any] = {}
        if ctx.correlation_id:
            trace_context["correlation_id"] = ctx.correlation_id
        if inputs.artifacts:
            first = inputs.artifacts[0]
            if getattr(first, "id", None) is not None:
                trace_context["triggering_artifact_id"] = str(first.id)
            if getattr(first, "type", None):
                trace_context["triggering_artifact_type"] = first.type
            if len(inputs.artifacts) > 1:
                trace_context["additional_input_ids"] = [
                    str(getattr(a, "id", "")) for a in inputs.artifacts[1:]
                ]
        if trace_context:
            sections.append(
                "## Trace context\n```json\n"
                + json.dumps(trace_context, indent=2, default=str)
                + "\n```"
            )

        description = getattr(agent, "description", None)
        if description:
            sections.append(f"## Instructions\n{description}")

        # Input artifacts
        if inputs.artifacts:
            input_blocks = []
            for art in inputs.artifacts:
                block = {
                    "type": art.type,
                    "payload": art.payload,
                }
                input_blocks.append(block)
            sections.append(
                "## Input artifacts\n```json\n"
                + json.dumps(input_blocks, indent=2, default=str)
                + "\n```"
            )

        # Output schemas (only when we expect a structured response)
        if expect_outputs:
            output_types: list[type[BaseModel]] = []
            for sub in getattr(agent, "output_groups", []) or []:
                for out in sub.outputs:
                    output_types.append(out.spec.model)
            schemas = [
                {
                    "type": getattr(t, "__flock_type__", t.__name__),
                    "schema": t.model_json_schema(),
                }
                for t in output_types
            ]
            if schemas:
                if len(schemas) == 1:
                    response_template = (
                        '{"type": "<type-name>", "data": <object matching schema>}'
                    )
                else:
                    response_template = (
                        '[{"type": "<type-name>", "data": <object>}, ...]'
                    )
                sections.append(
                    "## Expected output\n"
                    f"Reply with valid JSON in the form:\n`{response_template}`\n\n"
                    "Schemas:\n```json\n"
                    + json.dumps(schemas, indent=2, default=str)
                    + "\n```\n\n"
                    "Reply with ONLY valid JSON. No markdown code fences, no commentary."
                )

        return "\n\n".join(sections) if sections else "(no input)"

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_outputs(
        stdout: str,
        output_types: list[type[BaseModel]],
        agent_name: str,
    ) -> list[BaseModel]:
        """Parse the agent's stdout into typed Pydantic objects.

        Accepts either:
          - A single object: ``{"type": "...", "data": {...}}`` or just ``{...}``
          - A list of objects: ``[{"type": "...", "data": {...}}, ...]``
          - A bare object that matches the (single) expected type
        """
        text = (stdout or "").strip()
        if not text:
            raise ExternalEngineExecutionError(
                f"External agent '{agent_name}' produced no output"
            )

        # Strip common markdown fences if the agent included them.
        text = _strip_code_fences(text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExternalEngineExecutionError(
                f"External agent '{agent_name}' returned non-JSON output: "
                f"{exc.msg} (preview: {text[:200]!r})"
            ) from exc

        items: list[Any]
        if isinstance(data, list):
            items = data
        else:
            items = [data]

        if len(items) != len(output_types):
            raise ExternalEngineExecutionError(
                f"External agent '{agent_name}' returned {len(items)} item(s) "
                f"but {len(output_types)} expected"
            )

        objects: list[BaseModel] = []
        for item, model_cls in zip(items, output_types):
            payload = _extract_payload(item)
            try:
                objects.append(model_cls.model_validate(payload))
            except ValidationError as exc:
                raise ExternalEngineExecutionError(
                    f"External agent '{agent_name}' produced output that does "
                    f"not match {model_cls.__name__}: {exc.errors()[:3]!r}"
                ) from exc
        return objects

    # ------------------------------------------------------------------
    # Session store helpers (unify sync + async stores)
    # ------------------------------------------------------------------

    async def _session_get(
        self, agent_name: str, artifact_type: str
    ) -> str | None:
        result = self._session_store.get(agent_name, artifact_type)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _session_set(
        self, agent_name: str, artifact_type: str, session_id: str
    ) -> None:
        result = self._session_store.set(agent_name, artifact_type, session_id)
        if inspect.isawaitable(result):
            await result


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` fencing if present."""
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    # Drop first line (```lang) and trailing ```
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_payload(item: Any) -> dict[str, Any]:
    """Pull the data dict out of an item.

    Accepts ``{"type": "...", "data": {...}}`` envelopes (preferred) or a
    bare object dict (fallback for agents that ignore the envelope hint).
    """
    if isinstance(item, dict):
        if (
            "data" in item
            and isinstance(item["data"], dict)
            and ("type" in item or len(item) == 2)
        ):
            return item["data"]
        return item
    raise ExternalEngineExecutionError(
        f"Expected JSON object, got {type(item).__name__}"
    )


__all__ = [
    "ExternalEngineComponent",
    "ExternalEngineExecutionError",
]
