"""OpenClaw engine component (Phase 1 transport implementation)."""

from __future__ import annotations

import json
import logging
import os
from collections import OrderedDict, defaultdict
from contextlib import nullcontext
from datetime import UTC, date, datetime, time
from threading import Lock
from typing import Any, ClassVar, Literal
from uuid import UUID, uuid4

import httpx
from pydantic import Field, ValidationError

from flock.components.agent import EngineComponent
from flock.core.fan_out import FanOutRange
from flock.integrations.openclaw.config import GatewayConfig
from flock.integrations.openclaw.streaming import OpenClawStreamingExecutor
from flock.utils.runtime import EvalResult


logger = logging.getLogger(__name__)


def _default_stream_value() -> bool:
    """Match DSPy default: enable streaming except under pytest."""
    return os.environ.get("PYTEST_CURRENT_TEST") is None


class OpenClawEngine(EngineComponent):
    """Engine delegating execution to an OpenClaw gateway (spawn mode)."""

    alias: str
    gateway: GatewayConfig
    mode: Literal["spawn"] = "spawn"
    timeout: int = Field(default=120, ge=1)
    retries: int = Field(default=1, ge=0)
    response_mode: Literal["json_schema", "prompt_only"] = "json_schema"
    instructions: str | None = None
    stream: bool = Field(
        default_factory=_default_stream_value,
        description="Enable streaming output from OpenClaw. Auto-disables in pytest.",
    )
    stream_vertical_overflow: Literal["crop", "ellipsis", "crop_above", "visible"] = (
        "crop_above"
    )
    status_output_field: str = "_status_output"
    theme: str = "afterglow"

    _RELIABILITY_LOG_EVERY: ClassVar[int] = 25
    _reliability_counter_lock: ClassVar[Lock] = Lock()
    _reliability_counters: ClassVar[dict[str, int]] = {
        "requests_total": 0,
        "attempts_total": 0,
        "attempts_with_text_format": 0,
        "attempts_without_text_format": 0,
        "repair_attempts": 0,
        "runtime_retries": 0,
        "parse_retries": 0,
        "parse_failures": 0,
        "fallback_unsupported_text_format": 0,
        "responses_success": 0,
        "responses_failure": 0,
        "responses_repaired_success": 0,
        "auth_failures": 0,
    }

    @classmethod
    def _bump_counter(cls, key: str, amount: int = 1) -> None:
        with cls._reliability_counter_lock:
            cls._reliability_counters[key] = (
                cls._reliability_counters.get(key, 0) + amount
            )

    @classmethod
    def _get_reliability_counters(cls) -> dict[str, int]:
        with cls._reliability_counter_lock:
            return dict(cls._reliability_counters)

    @classmethod
    def _reset_reliability_counters_for_tests(cls) -> None:
        with cls._reliability_counter_lock:
            for key in cls._reliability_counters:
                cls._reliability_counters[key] = 0

    def _log_reliability_snapshot_if_due(self) -> None:
        snapshot = self._get_reliability_counters()
        total = snapshot.get("requests_total", 0)
        if total <= 0 or total % self._RELIABILITY_LOG_EVERY != 0:
            return

        logger.info(
            "OpenClaw reliability counters: requests=%s success=%s failure=%s repaired_success=%s parse_failures=%s unsupported_text_fallback=%s",
            snapshot.get("requests_total", 0),
            snapshot.get("responses_success", 0),
            snapshot.get("responses_failure", 0),
            snapshot.get("responses_repaired_success", 0),
            snapshot.get("parse_failures", 0),
            snapshot.get("fallback_unsupported_text_format", 0),
        )

    async def evaluate(self, agent, ctx, inputs, output_group) -> EvalResult:
        if self.mode != "spawn":
            raise ValueError(f"Unsupported OpenClaw mode: {self.mode}")

        if not inputs.artifacts:
            return EvalResult.empty(state=dict(inputs.state))

        if not output_group.outputs:
            return EvalResult.empty(state=dict(inputs.state))

        self._resolve_output_decls(output_group)

        self._bump_counter("requests_total")

        endpoint = f"{self.gateway.url.rstrip('/')}/v1/responses"
        headers = {
            "Content-Type": "application/json",
            "x-openclaw-agent-id": self.gateway.agent_id,
        }
        if self.gateway.token is not None:
            headers["Authorization"] = f"Bearer {self.gateway.token.get_secret_value()}"

        base_payload = self._build_responses_payload(
            agent=agent,
            ctx=ctx,
            inputs=inputs,
            output_group=output_group,
        )

        should_stream, is_dashboard_stream, claimed_cli_stream_slot = (
            self._resolve_streaming_mode(ctx)
        )
        pre_generated_artifact_id = uuid4() if should_stream else None

        attempts = max(1, self.retries + 1)
        parse_error: Exception | None = None
        strip_text_format = False

        try:
            for attempt in range(attempts):
                payload = dict(base_payload)

                # If gateway rejected text.format, strip it for all subsequent attempts.
                if strip_text_format:
                    payload.pop("text", None)

                self._bump_counter("attempts_total")
                if "text" in payload:
                    self._bump_counter("attempts_with_text_format")
                else:
                    self._bump_counter("attempts_without_text_format")

                # Single repair attempt (or bounded by retries): re-ask with strict JSON reminder.
                if attempt > 0 and parse_error is not None:
                    self._bump_counter("repair_attempts")
                    payload["input"] = self._build_repair_task(
                        original_task=str(base_payload["input"]),
                        parse_error=str(parse_error),
                    )

                try:
                    if should_stream:
                        data = await self._execute_streaming_attempt(
                            agent=agent,
                            ctx=ctx,
                            output_group=output_group,
                            endpoint=endpoint,
                            headers=headers,
                            payload=payload,
                            pre_generated_artifact_id=pre_generated_artifact_id,
                            is_dashboard_stream=is_dashboard_stream,
                        )
                    else:
                        response_payload = await self._call_responses_api(
                            endpoint=endpoint,
                            headers=headers,
                            payload=payload,
                        )
                        data = self._parse_responses_output(
                            response_payload,
                            output_group=output_group,
                        )

                    metadata: dict[str, Any] = {
                        "correlation_id": getattr(ctx, "correlation_id", None)
                    }
                    if pre_generated_artifact_id is not None:
                        metadata["artifact_id"] = pre_generated_artifact_id

                    artifacts = self._materialize_artifacts_for_output_group(
                        data,
                        output_group=output_group,
                        produced_by=agent.name,
                        metadata=metadata,
                    )
                except RuntimeError as exc:
                    # Gateway doesn't support text.format — strip it and retry.
                    if self._is_unsupported_text_format_error(exc):
                        self._bump_counter("fallback_unsupported_text_format")
                        strip_text_format = True
                        if attempt < attempts - 1:
                            self._bump_counter("runtime_retries")
                            continue

                        # Last attempt: retry once more without text.format.
                        payload = dict(base_payload)
                        payload.pop("text", None)
                        self._bump_counter("attempts_total")
                        self._bump_counter("attempts_without_text_format")
                        try:
                            if should_stream:
                                data = await self._execute_streaming_attempt(
                                    agent=agent,
                                    ctx=ctx,
                                    output_group=output_group,
                                    endpoint=endpoint,
                                    headers=headers,
                                    payload=payload,
                                    pre_generated_artifact_id=pre_generated_artifact_id,
                                    is_dashboard_stream=is_dashboard_stream,
                                )
                            else:
                                response_payload = await self._call_responses_api(
                                    endpoint=endpoint,
                                    headers=headers,
                                    payload=payload,
                                )
                                data = self._parse_responses_output(
                                    response_payload,
                                    output_group=output_group,
                                )

                            metadata = {
                                "correlation_id": getattr(ctx, "correlation_id", None)
                            }
                            if pre_generated_artifact_id is not None:
                                metadata["artifact_id"] = pre_generated_artifact_id
                            artifacts = self._materialize_artifacts_for_output_group(
                                data,
                                output_group=output_group,
                                produced_by=agent.name,
                                metadata=metadata,
                            )
                            self._bump_counter("responses_success")
                            self._bump_counter("responses_repaired_success")
                            self._log_reliability_snapshot_if_due()

                            if (
                                should_stream
                                and is_dashboard_stream
                                and ctx
                                and not getattr(self, "no_output", False)
                            ):
                                ctx.state["_flock_stream_live_active"] = True

                            return EvalResult(
                                artifacts=artifacts, state=dict(inputs.state)
                            )
                        except Exception:
                            self._bump_counter("responses_failure")
                            self._log_reliability_snapshot_if_due()
                            raise exc from None

                    if attempt < attempts - 1 and self._is_retriable_runtime_error(exc):
                        self._bump_counter("runtime_retries")
                        continue

                    self._bump_counter("responses_failure")
                    self._log_reliability_snapshot_if_due()
                    raise
                except ValueError as exc:
                    # Preserve auth/token failures as ValueError (fail-fast contract).
                    if "auth/token failure" in str(exc).lower():
                        self._bump_counter("auth_failures")
                        self._bump_counter("responses_failure")
                        self._log_reliability_snapshot_if_due()
                        raise

                    self._bump_counter("parse_failures")
                    parse_error = exc
                    if attempt < attempts - 1:
                        self._bump_counter("parse_retries")
                        continue

                    self._bump_counter("responses_failure")
                    self._log_reliability_snapshot_if_due()
                    raise RuntimeError(f"OpenClaw response parse error: {exc}") from exc
                except ValidationError as exc:
                    self._bump_counter("parse_failures")
                    parse_error = exc
                    if attempt < attempts - 1:
                        self._bump_counter("parse_retries")
                        continue

                    self._bump_counter("responses_failure")
                    self._log_reliability_snapshot_if_due()
                    raise RuntimeError(f"OpenClaw response parse error: {exc}") from exc

                self._bump_counter("responses_success")
                if attempt > 0 or parse_error is not None or strip_text_format:
                    self._bump_counter("responses_repaired_success")
                self._log_reliability_snapshot_if_due()

                if (
                    should_stream
                    and is_dashboard_stream
                    and ctx
                    and not getattr(self, "no_output", False)
                ):
                    ctx.state["_flock_stream_live_active"] = True

                return EvalResult(artifacts=artifacts, state=dict(inputs.state))

            # Defensive fallback; loop should always return or raise.
            raise RuntimeError("OpenClaw evaluation failed unexpectedly.")
        finally:
            if claimed_cli_stream_slot:
                from flock.core import Agent

                Agent._streaming_counter = max(0, Agent._streaming_counter - 1)

    async def _execute_streaming_attempt(
        self,
        *,
        agent,
        ctx,
        output_group,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        pre_generated_artifact_id,
        is_dashboard_stream: bool,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        live_cm = nullcontext()
        live_ref: dict[str, Any] | None = None

        if is_dashboard_stream:
            sinks = self._build_dashboard_streaming_sinks(
                agent=agent,
                ctx=ctx,
                output_group=output_group,
                artifact_id=pre_generated_artifact_id,
            )
        else:
            sinks, live_cm, live_ref = self._build_cli_streaming_sinks(
                agent=agent,
                ctx=ctx,
                output_group=output_group,
                artifact_id=pre_generated_artifact_id,
            )

        async def _fallback_non_streaming_text() -> str:
            response_payload = await self._call_responses_api(
                endpoint=endpoint,
                headers=headers,
                payload=payload,
            )
            return self._extract_responses_output_text(response_payload)

        executor = OpenClawStreamingExecutor(
            endpoint=endpoint,
            headers=headers,
            payload=payload,
            sinks=sinks,
            output_field="output",
            timeout=self.timeout,
            fallback_non_streaming_factory=_fallback_non_streaming_text,
        )

        with live_cm as live:
            if live_ref is not None:
                live_ref["value"] = live
            stream_result = await executor.execute()

        if live_ref is not None:
            live_ref["value"] = None

        output_text = stream_result.final_text or stream_result.full_text
        return self._parse_output_text_for_output_group(
            output_text,
            output_group=output_group,
        )

    def _resolve_streaming_mode(self, ctx) -> tuple[bool, bool, bool]:
        """Determine streaming mode and claim CLI stream slot when needed.

        Returns:
            (should_stream, is_dashboard_stream, claimed_cli_stream_slot)
        """
        if ctx is None or not self.stream:
            return False, False, False

        from flock.core import Agent

        is_dashboard_stream = Agent._websocket_broadcast_global is not None
        if is_dashboard_stream:
            return True, True, False

        active_streams = Agent._streaming_counter
        if active_streams > 0:
            ctx.state["_flock_output_queued"] = True
            return False, False, False

        Agent._streaming_counter = active_streams + 1
        return True, False, True

    def _build_dashboard_streaming_sinks(
        self, *, agent, ctx, output_group, artifact_id
    ):
        from flock.core import Agent
        from flock.engines.streaming.sinks import WebSocketSink

        ws_broadcast = Agent._websocket_broadcast_global if ctx else None
        if ws_broadcast is None:
            return []

        output_type_name = "output"
        if output_group.outputs:
            output_type_name = (
                getattr(output_group.outputs[0].spec, "type_name", None) or "output"
            )

        def _event_factory(
            output_type: str, content: str, sequence: int, is_final: bool
        ):
            return self._build_streaming_event(
                ctx=ctx,
                agent=agent,
                artifact_id=artifact_id,
                artifact_type=output_type_name,
                output_type=output_type,
                content=content,
                sequence=sequence,
                is_final=is_final,
            )

        return [
            WebSocketSink(
                ws_broadcast=ws_broadcast,
                event_factory=_event_factory,
            )
        ]

    def _resolve_output_utility_theme(self, agent) -> str:
        """Resolve CLI streaming theme from OutputUtility to match final static table."""
        for utility in getattr(agent, "utilities", []) or []:
            if getattr(utility, "name", None) != "output":
                continue
            config = getattr(utility, "config", None)
            if config is None:
                continue
            theme = getattr(config, "theme", None)
            if theme:
                return str(getattr(theme, "value", theme))
        return str(self.theme)

    def _build_cli_streaming_sinks(self, *, agent, ctx, output_group, artifact_id):
        if getattr(self, "no_output", False):
            return [], nullcontext(), None

        from rich.console import Console
        from rich.live import Live

        from flock.engines.dspy.streaming_executor import DSPyStreamingExecutor
        from flock.engines.dspy_engine import _ensure_live_crop_above
        from flock.engines.streaming.sinks import RichSink

        output_type_name = "output"
        if output_group.outputs:
            output_type_name = (
                getattr(output_group.outputs[0].spec, "type_name", None) or "output"
            )

        display_data: OrderedDict[str, Any] = OrderedDict()
        display_data["id"] = str(artifact_id)
        display_data["type"] = output_type_name
        display_data["payload"] = OrderedDict({"output": ""})
        display_data["produced_by"] = getattr(agent, "name", "")
        display_data["correlation_id"] = (
            str(getattr(ctx, "correlation_id", "") or "") if ctx else None
        )
        display_data["partition_key"] = None
        display_data["tags"] = "set()"
        display_data["visibility"] = OrderedDict([("kind", "Public")])
        display_data["created_at"] = "streaming..."
        display_data["version"] = 1
        display_data["status"] = self.status_output_field

        stream_buffers: defaultdict[str, list[str]] = defaultdict(list)

        formatter_helper = DSPyStreamingExecutor(
            status_output_field=self.status_output_field,
            stream_vertical_overflow=self.stream_vertical_overflow,
            theme=self._resolve_output_utility_theme(agent),
            no_output=self.no_output,
        )
        formatter, theme_dict, styles, agent_label = (
            formatter_helper.prepare_stream_formatter(agent)
        )
        # Match OpenClaw static table label in streaming panel.
        agent_label = f"{getattr(agent, 'name', '')} 🦞"

        _ensure_live_crop_above()
        initial_panel = formatter.format_result(
            display_data, agent_label, theme_dict, styles
        )

        live_cm = Live(
            initial_panel,
            console=Console(),
            refresh_per_second=12,
            # CLI stream panel is transient; OutputUtility renders final static table.
            transient=True,
            vertical_overflow=self.stream_vertical_overflow,
        )

        live_ref: dict[str, Any] = {"value": None}

        def refresh_panel() -> None:
            live = live_ref.get("value")
            if live is None:
                return
            live.update(
                formatter.format_result(display_data, agent_label, theme_dict, styles)
            )

        rich_sink = RichSink(
            display_data=display_data,
            stream_buffers=stream_buffers,
            status_field=self.status_output_field,
            signature_order=["output"],
            formatter=formatter,
            theme_dict=theme_dict,
            styles=styles,
            agent_label=agent_label,
            refresh_panel=refresh_panel,
            timestamp_factory=lambda: datetime.now(UTC).isoformat(),
        )

        return [rich_sink], live_cm, live_ref

    def _build_streaming_event(
        self,
        *,
        ctx,
        agent,
        artifact_id,
        artifact_type: str,
        output_type: str,
        content: str,
        sequence: int,
        is_final: bool,
    ):
        from flock.components.server.models.events import StreamingOutputEvent

        correlation_id = ""
        run_id = ""
        if ctx:
            correlation_id = str(getattr(ctx, "correlation_id", "") or "")
            run_id = str(getattr(ctx, "task_id", "") or "")

        return StreamingOutputEvent(
            correlation_id=correlation_id,
            agent_name=getattr(agent, "name", ""),
            run_id=run_id,
            output_type=output_type,
            content=content,
            sequence=sequence,
            is_final=is_final,
            artifact_id=str(artifact_id) if artifact_id is not None else "",
            artifact_type=artifact_type,
        )

    def _build_responses_payload(
        self, *, agent, ctx, inputs, output_group
    ) -> dict[str, Any]:
        output_decls = self._resolve_output_decls(output_group)
        single_output_decl = output_decls[0] if len(output_decls) == 1 else None
        slot_map: OrderedDict[str, Any] | None = None

        if single_output_decl is not None:
            output_schema = single_output_decl.spec.model.model_json_schema()
            schema_contract = self._build_output_schema_contract(
                output_schema,
                output_decl=single_output_decl,
            )
        else:
            slot_map = self._build_multi_output_slot_map(output_group)
            schema_contract = self._build_multi_output_schema_contract(slot_map)

        input_payloads: list[dict[str, Any]] = []
        for artifact in inputs.artifacts:
            payload = artifact.payload
            if isinstance(payload, dict):
                input_payloads.append(self._to_json_safe(dict(payload)))
            else:
                input_payloads.append({"value": self._to_json_safe(payload)})

        description = str(
            self.instructions or getattr(agent, "description", "") or ""
        ).strip()
        if single_output_decl is not None:
            group_description = str(
                getattr(single_output_decl, "group_description", "") or ""
            ).strip()
        else:
            group_description = str(
                getattr(output_group, "group_description", "") or ""
            ).strip()

        context_history = (
            self.get_conversation_context(ctx)
            if ctx is not None and hasattr(ctx, "artifacts")
            else []
        )
        include_context = bool(context_history) and self.should_use_context(inputs)
        batched = bool(getattr(ctx, "is_batch", False)) if ctx else False

        if slot_map is not None:
            task_lines = [
                "Your ENTIRE response must be a single valid JSON object envelope matching the schema below.",
                "Do not include any text, explanation, markdown fences, or commentary — only the raw JSON object.",
                "The response will be parsed directly by a JSON schema validator.",
            ]
            for slot_name, output_decl in slot_map.items():
                fan_out_range = self._get_fan_out_range(output_decl)
                if fan_out_range is None:
                    slot_hint = "one object"
                elif fan_out_range.is_fixed():
                    slot_hint = (
                        f"an array with exactly {fan_out_range.fixed_count()} item(s)"
                    )
                else:
                    slot_hint = (
                        "an array with between "
                        f"{fan_out_range.min} and {fan_out_range.max} item(s)"
                    )
                task_lines.append(
                    f"Slot '{slot_name}': return {slot_hint} matching that slot schema."
                )
        elif self._expects_array_response(single_output_decl):
            fan_out_range = self._get_fan_out_range(single_output_decl)
            assert fan_out_range is not None
            if fan_out_range.is_fixed():
                count_hint = f"exactly {fan_out_range.fixed_count()}"
            else:
                count_hint = f"between {fan_out_range.min} and {fan_out_range.max}"

            task_lines = [
                "Your ENTIRE response must be a single valid JSON array matching the schema below.",
                "Do not include any text, explanation, markdown fences, or commentary — only the raw JSON array.",
                "The response will be parsed directly by a JSON schema validator.",
                f"Return {count_hint} item(s).",
            ]
        else:
            task_lines = [
                "Your ENTIRE response must be a single valid JSON object matching the schema below.",
                "Do not include any text, explanation, markdown fences, or commentary — only the raw JSON object.",
                "The response will be parsed directly by a JSON schema validator.",
            ]

        if batched:
            task_lines.append(
                "Batch mode is active: process the provided batch cohesively and honor batch semantics."
            )

        if group_description:
            task_lines.append(f"Output guidance: {group_description}")

        if include_context:
            task_lines.append(
                f"Context: {json.dumps(self._context_to_prompt_payload(context_history), ensure_ascii=False)}"
            )

        task_lines.append(f"Schema: {json.dumps(schema_contract, ensure_ascii=False)}")

        if len(input_payloads) == 1:
            task_lines.append(
                f"Input: {json.dumps(input_payloads[0], ensure_ascii=False)}"
            )
        else:
            task_lines.append(
                f"Inputs: {json.dumps(input_payloads, ensure_ascii=False)}"
            )

        payload: dict[str, Any] = {
            "model": "openclaw",
            "input": "\n".join(task_lines),
            "stream": False,
        }

        if self.response_mode == "json_schema":
            # Build strict JSON schema for structured output enforcement.
            # This constrains the model at the token level — it cannot produce
            # invalid JSON when the provider supports json_schema response format.
            # If the gateway doesn't support text.format, the schema is still
            # in the prompt text as fallback (belt + suspenders).
            strict_schema = self._make_strict_schema(schema_contract)

            if single_output_decl is None:
                schema_name = "OpenClawMultiOutputEnvelope"
            else:
                schema_name = single_output_decl.spec.model.__name__
                if self._expects_array_response(single_output_decl):
                    schema_name = f"{schema_name}List"

            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": strict_schema,
                    "strict": True,
                }
            }

        if description:
            payload["instructions"] = description

        return payload

    def _make_strict_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Transform a JSON schema into OpenAI strict-mode compatible form.

        Strict mode requires:
        - ``additionalProperties: false`` on every object
        - All properties listed in ``required``
        - No unsupported keywords (``$defs`` renamed, etc.)
        """
        return self._strict_transform(dict(schema))

    def _strict_transform(self, node: dict[str, Any]) -> dict[str, Any]:
        """Recursively apply strict-mode constraints to a schema node."""
        node = dict(node)

        # Recurse into $defs / definitions
        for defs_key in ("$defs", "definitions"):
            if defs_key in node and isinstance(node[defs_key], dict):
                node[defs_key] = {
                    k: self._strict_transform(v) for k, v in node[defs_key].items()
                }

        node_type = node.get("type")

        if node_type == "object" and "properties" in node:
            props = node["properties"]
            # All properties must be required in strict mode
            node["required"] = list(props.keys())
            node["additionalProperties"] = False
            # Recurse into property schemas
            node["properties"] = {
                k: self._strict_transform(v) for k, v in props.items()
            }

        elif node_type == "array":
            items = node.get("items")
            if isinstance(items, dict):
                node["items"] = self._strict_transform(items)

        # Handle anyOf / oneOf / allOf
        for combo_key in ("anyOf", "oneOf", "allOf"):
            if combo_key in node and isinstance(node[combo_key], list):
                node[combo_key] = [
                    self._strict_transform(v) if isinstance(v, dict) else v
                    for v in node[combo_key]
                ]

        return node

    def _to_json_safe(self, value: Any) -> Any:
        """Normalize arbitrary runtime values into JSON-safe structures.

        This is intended for prompt payload serialization where context/input data may
        include Python-native objects (e.g., datetime/UUID).
        """
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, (datetime, date, time)):
            return value.isoformat()

        if isinstance(value, UUID):
            return str(value)

        if isinstance(value, dict):
            return {str(k): self._to_json_safe(v) for k, v in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [self._to_json_safe(v) for v in value]

        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            try:
                return self._to_json_safe(model_dump())
            except Exception:
                pass

        return str(value)

    def _context_to_prompt_payload(self, context_items) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for item in context_items:
            payload = getattr(item, "payload", None)

            serialized.append({
                "type": str(getattr(item, "type", "")),
                "produced_by": str(getattr(item, "produced_by", "")),
                "payload": self._to_json_safe(payload),
            })
        return serialized

    def _resolve_output_decls(self, output_group) -> list:
        outputs = list(getattr(output_group, "outputs", []) or [])
        if not outputs:
            raise ValueError(
                "OpenClaw output group must include at least one output declaration."
            )
        return outputs

    def _build_multi_output_slot_map(self, output_group) -> OrderedDict[str, Any]:
        """Build deterministic slot mapping for multi-output groups.

        Slot key strategy (v1): declaration type name.
        """
        slot_map: OrderedDict[str, Any] = OrderedDict()
        for output_decl in self._resolve_output_decls(output_group):
            slot_name = str(getattr(output_decl.spec, "type_name", "") or "").strip()
            if not slot_name:
                slot_name = str(
                    getattr(output_decl.spec.model, "__name__", "output")
                ).strip()

            if slot_name in slot_map:
                raise ValueError(
                    "OpenClaw multi-output slot collision detected for slot "
                    f"'{slot_name}'. Duplicate/ambiguous slot names require explicit alias support."
                )

            slot_map[slot_name] = output_decl

        return slot_map

    def _resolve_output_decl(self, output_group):
        outputs = self._resolve_output_decls(output_group)
        if len(outputs) != 1:
            # Build slot map first so duplicate-name groups fail with explicit
            # collision/alias guidance instead of a generic unsupported error.
            self._build_multi_output_slot_map(output_group)
            raise ValueError(
                "OpenClaw engine multi-output envelope execution path is not enabled yet. "
                "Use one publishes(...) output type per OpenClaw group until multi-output envelope implementation is complete."
            )
        return outputs[0]

    def _get_fan_out_range(self, output_decl) -> FanOutRange | None:
        fan_out_range = getattr(output_decl, "fan_out", None)
        return fan_out_range if isinstance(fan_out_range, FanOutRange) else None

    def _expects_array_response(self, output_decl) -> bool:
        return self._get_fan_out_range(output_decl) is not None

    def _build_output_schema_contract(
        self,
        output_schema: dict[str, Any],
        *,
        output_decl,
    ) -> dict[str, Any]:
        fan_out_range = self._get_fan_out_range(output_decl)
        if fan_out_range is None:
            return output_schema

        schema_contract: dict[str, Any] = {
            "type": "array",
            "items": output_schema,
        }
        if fan_out_range.is_fixed():
            fixed = fan_out_range.fixed_count()
            assert fixed is not None
            schema_contract["minItems"] = fixed
            schema_contract["maxItems"] = fixed
        else:
            schema_contract["minItems"] = fan_out_range.min
            schema_contract["maxItems"] = fan_out_range.max

        return schema_contract

    def _build_multi_output_schema_contract(
        self,
        slot_map: OrderedDict[str, Any],
    ) -> dict[str, Any]:
        properties: OrderedDict[str, dict[str, Any]] = OrderedDict()
        required: list[str] = []

        for slot_name, output_decl in slot_map.items():
            output_schema = output_decl.spec.model.model_json_schema()
            properties[slot_name] = self._build_output_schema_contract(
                output_schema,
                output_decl=output_decl,
            )
            required.append(slot_name)

        return {
            "type": "object",
            "properties": dict(properties),
            "required": required,
            "additionalProperties": False,
        }

    def _enforce_fan_out_contract(
        self,
        items: list[dict[str, Any]],
        *,
        output_decl,
        agent_name: str,
    ) -> list[dict[str, Any]]:
        fan_out_range = self._get_fan_out_range(output_decl)
        if fan_out_range is None:
            return items

        actual_count = len(items)
        type_name = output_decl.spec.type_name

        if fan_out_range.is_fixed():
            expected = fan_out_range.fixed_count()
            assert expected is not None
            if actual_count != expected:
                raise RuntimeError(
                    "OpenClaw fan-out contract violation "
                    f"in agent '{agent_name}': expected exactly {expected} artifact(s) "
                    f"of type '{type_name}', got {actual_count}."
                )
            return items

        if actual_count < fan_out_range.min:
            raise RuntimeError(
                "OpenClaw fan-out contract violation "
                f"in agent '{agent_name}': expected between {fan_out_range.min} and {fan_out_range.max} "
                f"artifact(s) of type '{type_name}', got {actual_count}."
            )

        if actual_count > fan_out_range.max:
            logger.warning(
                "OpenClaw dynamic fan-out exceeded max in agent '%s': type='%s', range=(%s,%s), actual=%s; truncating to max.",
                agent_name,
                type_name,
                fan_out_range.min,
                fan_out_range.max,
                actual_count,
            )
            return items[: fan_out_range.max]

        return items

    @staticmethod
    def _drop_artifact_id(metadata: dict[str, Any]) -> dict[str, Any]:
        if "artifact_id" not in metadata:
            return metadata
        normalized = dict(metadata)
        normalized.pop("artifact_id", None)
        return normalized

    def _materialize_artifacts_for_output_group(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        *,
        output_group,
        produced_by: str,
        metadata: dict[str, Any],
    ) -> list:
        output_decls = self._resolve_output_decls(output_group)
        if len(output_decls) == 1:
            return self._materialize_artifacts(
                data,
                output_decl=output_decls[0],
                produced_by=produced_by,
                metadata=metadata,
            )

        if not isinstance(data, dict):
            raise ValueError(
                "multi-output envelope must be a JSON object, "
                f"got {type(data).__name__}."
            )

        slot_map = self._build_multi_output_slot_map(output_group)
        expected_slots = set(slot_map.keys())
        actual_slots = set(data.keys())

        unknown_slots = sorted(actual_slots - expected_slots)
        if unknown_slots:
            raise ValueError(
                "multi-output envelope contains unknown slot(s): "
                f"{', '.join(unknown_slots)}"
            )

        missing_slots = sorted(expected_slots - actual_slots)
        if missing_slots:
            raise ValueError(
                "multi-output envelope is missing required slot(s): "
                f"{', '.join(missing_slots)}"
            )

        artifacts: list = []
        shared_multi_output_metadata = self._drop_artifact_id(metadata)
        for slot_name, output_decl in slot_map.items():
            slot_value = data[slot_name]
            if self._expects_array_response(output_decl):
                if not isinstance(slot_value, list):
                    raise ValueError(
                        f"multi-output slot '{slot_name}' must be an array, "
                        f"got {type(slot_value).__name__}."
                    )

                raw_items: list[dict[str, Any]] = []
                for item in slot_value:
                    if not isinstance(item, dict):
                        raise ValueError(
                            f"multi-output slot '{slot_name}' array items must be objects."
                        )
                    raw_items.append(item)

                items = self._enforce_fan_out_contract(
                    raw_items,
                    output_decl=output_decl,
                    agent_name=str(produced_by),
                )

                for item in items:
                    artifacts.append(
                        output_decl.apply(
                            item,
                            produced_by=produced_by,
                            metadata=shared_multi_output_metadata,
                        )
                    )
            else:
                if not isinstance(slot_value, dict):
                    raise ValueError(
                        f"multi-output slot '{slot_name}' must be an object, "
                        f"got {type(slot_value).__name__}."
                    )

                artifacts.append(
                    output_decl.apply(
                        slot_value,
                        produced_by=produced_by,
                        metadata=shared_multi_output_metadata,
                    )
                )

        return artifacts

    def _materialize_artifacts(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        *,
        output_decl,
        produced_by: str,
        metadata: dict[str, Any],
    ) -> list:
        if self._expects_array_response(output_decl):
            if not isinstance(data, list):
                raise ValueError(
                    f"Expected array data for fan-out output, got {type(data).__name__}."
                )
            items = self._enforce_fan_out_contract(
                data,
                output_decl=output_decl,
                agent_name=str(produced_by),
            )
            fan_out_metadata = self._drop_artifact_id(metadata)
            return [
                output_decl.apply(
                    item, produced_by=produced_by, metadata=fan_out_metadata
                )
                for item in items
            ]

        if not isinstance(data, dict):
            raise ValueError(
                f"Expected object data for single output, got {type(data).__name__}."
            )

        return [output_decl.apply(data, produced_by=produced_by, metadata=metadata)]

    def _build_repair_task(self, *, original_task: str, parse_error: str) -> str:
        return (
            f"{original_task}\n\n"
            "Previous response was not valid JSON for the required schema. "
            f"Error: {parse_error}.\n"
            "Respond again with ONLY valid JSON that matches the schema and no extra text."
        )

    async def _call_responses_api(
        self,
        *,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"OpenClaw gateway timeout: {exc}") from exc
        except httpx.ConnectError as exc:
            raise RuntimeError(f"OpenClaw gateway connection error: {exc}") from exc
        except httpx.TransportError as exc:
            raise RuntimeError(f"OpenClaw transport error: {exc}") from exc

        if response.status_code in {401, 403}:
            message = self._extract_error_message(response)
            raise ValueError(
                f"OpenClaw auth/token failure ({response.status_code}): {message}"
            )

        if response.status_code == 400:
            message = self._extract_error_message(response)
            raise RuntimeError(f"OpenClaw bad request (400): {message}")

        if response.status_code == 429:
            message = self._extract_error_message(response)
            raise RuntimeError(f"OpenClaw rate limit (429): {message}")

        if response.status_code >= 500:
            message = self._extract_error_message(response)
            raise RuntimeError(
                f"OpenClaw gateway server error ({response.status_code}): {message}"
            )

        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise RuntimeError(
                f"OpenClaw gateway request failed ({response.status_code}): {message}"
            )

        try:
            payload_json = response.json()
        except ValueError as exc:
            raise RuntimeError("OpenClaw gateway returned non-JSON response") from exc

        if not isinstance(payload_json, dict):
            raise RuntimeError("OpenClaw gateway response must be a JSON object")

        if str(payload_json.get("status", "")).lower() == "failed":
            message = self._extract_error_message(response)
            raise RuntimeError(f"OpenClaw response failed: {message}")

        return payload_json

    def _parse_responses_output(
        self,
        payload: dict[str, Any],
        *,
        output_group,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        text = self._extract_responses_output_text(payload)
        return self._parse_output_text_for_output_group(
            text,
            output_group=output_group,
        )

    def _parse_output_text_for_output_group(
        self,
        text: str,
        *,
        output_group,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        output_decls = self._resolve_output_decls(output_group)
        if len(output_decls) == 1:
            return self._parse_output_text(
                text,
                expects_array=self._expects_array_response(output_decls[0]),
            )

        preview = text[:500] + ("..." if len(text) > 500 else "")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"multi-output envelope is not valid JSON: {exc}. Agent response: {preview}"
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "multi-output envelope JSON must be an object, got "
                f"{type(parsed).__name__}. Agent response: {preview}"
            )

        return parsed

    def _extract_responses_output_text(self, payload: dict[str, Any]) -> str:
        output = payload.get("output")
        if not isinstance(output, list) or not output:
            raise ValueError("missing output text in OpenResponses response")

        text: str | None = None
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") in {"output_text", "text"}:
                        candidate = part.get("text")
                        if isinstance(candidate, str) and candidate.strip():
                            text = candidate
                            break
            if text is not None:
                break

        if not text:
            raise ValueError("missing output text in OpenResponses response")

        return text

    def _parse_output_text(
        self,
        text: str,
        *,
        expects_array: bool = False,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        # Truncate for error messages — enough to diagnose, not flood logs.
        preview = text[:500] + ("..." if len(text) > 500 else "")

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"result is not valid JSON: {exc}. Agent response: {preview}"
            ) from exc

        if expects_array:
            if not isinstance(parsed, list):
                raise ValueError(
                    f"result JSON must be an array, got {type(parsed).__name__}. "
                    f"Agent response: {preview}"
                )
            for idx, item in enumerate(parsed):
                if not isinstance(item, dict):
                    raise ValueError(
                        f"result JSON array items must be objects; item {idx} is {type(item).__name__}. "
                        f"Agent response: {preview}"
                    )
            return parsed

        if not isinstance(parsed, dict):
            raise ValueError(
                f"result JSON must be an object, got {type(parsed).__name__}. "
                f"Agent response: {preview}"
            )

        return parsed

    @staticmethod
    def _is_unsupported_text_format_error(exc: RuntimeError) -> bool:
        """Detect 400 errors caused by gateway not supporting text.format."""
        message = str(exc).lower()
        if "400" not in message:
            return False
        return any(
            marker in message
            for marker in (
                "unrecognized key",
                "text.format",
                '"text"',
                "'text'",
                "unknown parameter",
                "unexpected field",
            )
        )

    def _is_retriable_runtime_error(self, exc: RuntimeError) -> bool:
        message = str(exc).lower()
        return any(
            token in message
            for token in (
                "timeout",
                "timed out",
                "transport",
                "connect",
                "connection",
                "429",
                "rate limit",
                "server error",
                "response failed",
                "fan-out contract violation",
            )
        )

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text or "no error body"

        if isinstance(payload, dict):
            error_obj = payload.get("error")
            if isinstance(error_obj, dict):
                for key in ("message", "detail", "code"):
                    value = error_obj.get(key)
                    if value:
                        return str(value)
            for key in ("message", "detail"):
                value = payload.get(key)
                if value:
                    return str(value)
        return "unknown error"
