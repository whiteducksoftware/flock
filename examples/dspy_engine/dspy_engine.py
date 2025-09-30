from __future__ import annotations

"""DSPy-powered engine component that mirrors the design implementation."""

import json
import os
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel

from flock_flow.artifacts import Artifact
from flock_flow.components import EngineComponent
from flock_flow.registry import type_registry
from flock_flow.runtime import EvalInputs, EvalResult


class DSPyEngine(EngineComponent):
    """Execute a minimal DSPy program backed by a hosted LLM.

    Behavior intentionally mirrors ``design/dspy_engine.py`` so that orchestration
    relies on the same model resolution, signature preparation, and result
    normalization logic.
    """

    name: str | None = "dspy"
    model: str | None = None
    instructions: str | None = None
    temperature: float = 1.0
    max_tokens: int = 16000
    max_tool_calls: int = 10

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:  # type: ignore[override]
        if not inputs.artifacts:
            return EvalResult(artifacts=[], state=dict(inputs.state))

        model_name = self._resolve_model_name()
        dspy_mod = self._import_dspy()

        lm = dspy_mod.LM(model_name, temperature=self.temperature, max_tokens=self.max_tokens)

        primary_artifact = self._select_primary_artifact(inputs.artifacts)
        input_model = self._resolve_input_model(primary_artifact)
        validated_input = self._validate_input_payload(input_model, primary_artifact.payload)
        output_model = self._resolve_output_model(agent)

        signature = self._prepare_signature(
            dspy_mod,
            description=self.instructions or agent.description,
            input_schema=input_model,
            output_schema=output_model,
        )

        sys_desc = self._system_description(self.instructions or agent.description)
        stream_queue = self._extract_stream_queue(ctx)
        with dspy_mod.context(lm=lm):
            program = self._choose_program(dspy_mod, signature, agent.tools)
            raw_result = await self._execute_program(
                dspy_mod,
                program,
                description=sys_desc,
                payload=validated_input,
                stream_queue=stream_queue,
            )

        normalized_output = self._normalize_output_payload(getattr(raw_result, "output", None))
        artifacts, errors = self._materialize_artifacts(normalized_output, agent.outputs, agent.name)

        state = dict(inputs.state)
        state.setdefault("dspy", {})
        state["dspy"].update({"model": model_name, "raw": normalized_output})

        logs: list[str] = []
        if normalized_output is not None:
            try:
                logs.append(f"dspy.output={json.dumps(normalized_output)}")
            except TypeError:
                logs.append(f"dspy.output={normalized_output!r}")
        logs.extend(f"dspy.error={message}" for message in errors)

        result_artifacts = artifacts if artifacts else list(inputs.artifacts)
        return EvalResult(artifacts=result_artifacts, state=state, logs=logs)

    # ------------------------------------------------------------------
    # Helpers mirroring the design engine

    def _resolve_model_name(self) -> str:
        model = self.model or os.getenv("TRELLIS_MODEL") or os.getenv("OPENAI_MODEL")
        if not model:
            raise NotImplementedError(
                "DSPyEngine requires a configured model (set TRELLIS_MODEL, OPENAI_MODEL, or pass model=...)."
            )
        return model

    def _import_dspy(self):  # pragma: no cover - import guarded by optional dependency
        try:
            import dspy
        except Exception as exc:  # noqa: BLE001 - bubble as NotImplemented to match design behavior
            raise NotImplementedError("DSPy is not installed or failed to import.") from exc
        return dspy

    def _select_primary_artifact(self, artifacts: Sequence[Artifact]) -> Artifact:
        return artifacts[-1]

    def _resolve_input_model(self, artifact: Artifact) -> type[BaseModel] | None:
        try:
            return type_registry.resolve(artifact.type)
        except KeyError:
            return None

    def _resolve_output_model(self, agent) -> type[BaseModel] | None:
        if not getattr(agent, "outputs", None):
            return None
        return agent.outputs[0].spec.model

    def _validate_input_payload(
        self,
        schema: type[BaseModel] | None,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        data = dict(payload or {})
        if schema is None:
            return data
        try:
            return schema(**data).model_dump()
        except Exception:
            return data

    def _prepare_signature(
        self,
        dspy_mod,
        *,
        description: str | None,
        input_schema: type[BaseModel] | None,
        output_schema: type[BaseModel] | None,
    ):
        fields = {
            "description": (str, dspy_mod.InputField()),
            "input": (input_schema or dict, dspy_mod.InputField()),
            "output": (output_schema or dict, dspy_mod.OutputField()),
        }
        signature = dspy_mod.Signature(fields)
        instruction = description or "Produce a valid output that matches the 'output' schema. Return only JSON."
        return signature.with_instructions(instruction)

    def _choose_program(self, dspy_mod, signature, tools: Iterable[Any]):
        tools_list = list(tools or [])
        try:
            if tools_list:
                return dspy_mod.ReAct(signature, tools=tools_list, max_iters=self.max_tool_calls)
            return dspy_mod.Predict(signature)
        except Exception:
            return dspy_mod.Predict(signature)

    def _system_description(self, description: str | None) -> str:
        if description:
            return description
        return "Produce a valid output that matches the 'output' schema. Return only JSON."

    def _normalize_output_payload(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, BaseModel):
            return raw.model_dump()
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"text": raw}
        if isinstance(raw, Mapping):
            return dict(raw)
        return {"value": raw}

    def _materialize_artifacts(self, payload: dict[str, Any], outputs: Iterable[Any], produced_by: str):
        artifacts: list[Artifact] = []
        errors: list[str] = []
        for output in outputs or []:
            model_cls = output.spec.model
            data = self._select_output_payload(payload, model_cls, output.spec.type_name)
            try:
                instance = model_cls(**data)
            except Exception as exc:  # noqa: BLE001 - collect validation errors for logs
                errors.append(str(exc))
                continue
            artifacts.append(
                Artifact(
                    type=output.spec.type_name,
                    payload=instance.model_dump(),
                    produced_by=produced_by,
                )
            )
        return artifacts, errors

    def _select_output_payload(
        self,
        payload: Mapping[str, Any],
        model_cls: type[BaseModel],
        type_name: str,
    ) -> dict[str, Any]:
        candidates = [
            payload.get(type_name),
            payload.get(model_cls.__name__),
            payload.get(model_cls.__name__.lower()),
        ]
        for candidate in candidates:
            if isinstance(candidate, Mapping):
                return dict(candidate)
        if isinstance(payload, Mapping):
            return dict(payload)
        return {}

    def _extract_stream_queue(self, ctx) -> Any:
        try:
            logging_state = ctx.state.get("_logging")
            if isinstance(logging_state, Mapping):
                return logging_state.get("stream_queue")
        except Exception:  # pragma: no cover - defensive
            return None
        return None

    async def _execute_program(self, dspy_mod, program, *, description: str, payload: dict[str, Any], stream_queue) -> Any:
        if stream_queue and hasattr(stream_queue, "put") and hasattr(dspy_mod, "streamify"):
            try:
                return await self._run_streaming_program(
                    dspy_mod,
                    program,
                    description=description,
                    payload=payload,
                    stream_queue=stream_queue,
                )
            except Exception:
                # Fallback to non-streaming execution if streaming fails for any reason
                pass
        return program(description=description, input=payload)

    async def _run_streaming_program(self, dspy_mod, program, *, description: str, payload: dict[str, Any], stream_queue) -> Any:
        streaming_mod = getattr(dspy_mod, "streaming", None)
        stream_kwargs: dict[str, Any] = {"async_streaming": True}
        listeners = []
        if streaming_mod and hasattr(streaming_mod, "StreamListener"):
            try:
                listeners.append(streaming_mod.StreamListener(signature_field_name="output", allow_reuse=True))
            except Exception:
                listeners = []
        if listeners:
            stream_kwargs["stream_listeners"] = listeners
        streaming_program = dspy_mod.streamify(program, **stream_kwargs)
        prediction = None
        try:
            async for message in streaming_program(description=description, input=payload):
                if stream_queue is not None:
                    serialized = self._serialize_stream_message(message, dspy_mod)
                    await stream_queue.put(serialized)
                PredictionType = getattr(dspy_mod, "Prediction", None)
                if PredictionType and isinstance(message, PredictionType):
                    prediction = message
        finally:
            if stream_queue is not None:
                await stream_queue.put({"kind": "end"})
        if prediction is not None:
            return prediction
        return program(description=description, input=payload)

    def _serialize_stream_message(self, message: Any, dspy_mod) -> dict[str, Any]:
        streaming_mod = getattr(dspy_mod, "streaming", None)
        StreamResponse = getattr(streaming_mod, "StreamResponse", None) if streaming_mod else None
        StatusMessage = getattr(streaming_mod, "StatusMessage", None) if streaming_mod else None
        PredictionType = getattr(dspy_mod, "Prediction", None)

        if StreamResponse and isinstance(message, StreamResponse):
            return {
                "kind": "chunk",
                "chunk": getattr(message, "chunk", ""),
                "field": getattr(message, "signature_field_name", None),
                "predict_name": getattr(message, "predict_name", None),
                "is_last": getattr(message, "is_last_chunk", False),
            }
        if StatusMessage and isinstance(message, StatusMessage):
            return {
                "kind": "status",
                "stage": getattr(message, "stage", None),
                "message": getattr(message, "message", ""),
            }
        if PredictionType and isinstance(message, PredictionType):
            return {
                "kind": "final",
                "output": getattr(message, "output", None),
            }
        return {"kind": "unknown", "value": repr(message)}


__all__ = ["DSPyEngine"]
