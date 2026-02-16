"""OpenClaw engine component (Phase 1 transport implementation)."""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

import httpx
from pydantic import ValidationError

from flock.components.agent import EngineComponent
from flock.integrations.openclaw.config import GatewayConfig
from flock.integrations.openclaw.streaming import OpenClawStreamingExecutor
from flock.utils.runtime import EvalResult


class OpenClawEngine(EngineComponent):
    """Engine delegating execution to an OpenClaw gateway (spawn mode)."""

    alias: str
    gateway: GatewayConfig
    mode: Literal["spawn"] = "spawn"
    timeout: int = 120
    retries: int = 1
    response_mode: Literal["json_schema"] = "json_schema"

    async def evaluate(self, agent, ctx, inputs, output_group) -> EvalResult:
        if self.mode != "spawn":
            raise ValueError(f"Unsupported OpenClaw mode: {self.mode}")

        if not inputs.artifacts:
            return EvalResult.empty(state=dict(inputs.state))

        if not output_group.outputs:
            return EvalResult.empty(state=dict(inputs.state))

        endpoint = f"{self.gateway.url.rstrip('/')}/v1/responses"
        headers = {
            "Content-Type": "application/json",
            "x-openclaw-agent-id": self.gateway.agent_id,
        }
        if self.gateway.token:
            headers["Authorization"] = f"Bearer {self.gateway.token}"

        base_payload = self._build_responses_payload(
            agent=agent,
            ctx=ctx,
            inputs=inputs,
            output_group=output_group,
        )

        should_stream = self._should_stream(ctx)
        pre_generated_artifact_id = uuid4() if should_stream else None

        attempts = max(1, self.retries + 1)
        parse_error: Exception | None = None
        strip_text_format = False

        for attempt in range(attempts):
            payload = dict(base_payload)

            # If gateway rejected text.format, strip it for all subsequent attempts.
            if strip_text_format:
                payload.pop("text", None)

            # Single repair attempt (or bounded by retries): re-ask with strict JSON reminder.
            if attempt > 0 and parse_error is not None:
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
                    )
                else:
                    response_payload = await self._call_responses_api(
                        endpoint=endpoint,
                        headers=headers,
                        payload=payload,
                    )
                    data = self._parse_responses_output(response_payload)

                output_decl = output_group.outputs[0]
                metadata: dict[str, Any] = {"correlation_id": ctx.correlation_id}
                if pre_generated_artifact_id is not None:
                    metadata["artifact_id"] = pre_generated_artifact_id

                artifact = output_decl.apply(
                    data,
                    produced_by=agent.name,
                    metadata=metadata,
                )
            except RuntimeError as exc:
                # Gateway doesn't support text.format — strip it and retry.
                if self._is_unsupported_text_format_error(exc):
                    strip_text_format = True
                    if attempt < attempts - 1:
                        continue
                    # Last attempt: retry once more without text.format.
                    payload = dict(base_payload)
                    payload.pop("text", None)
                    try:
                        if should_stream:
                            data = await self._execute_streaming_attempt(
                                agent=agent, ctx=ctx, output_group=output_group,
                                endpoint=endpoint, headers=headers, payload=payload,
                                pre_generated_artifact_id=pre_generated_artifact_id,
                            )
                        else:
                            response_payload = await self._call_responses_api(
                                endpoint=endpoint, headers=headers, payload=payload,
                            )
                            data = self._parse_responses_output(response_payload)

                        output_decl = output_group.outputs[0]
                        metadata = {"correlation_id": ctx.correlation_id}
                        if pre_generated_artifact_id is not None:
                            metadata["artifact_id"] = pre_generated_artifact_id
                        artifact = output_decl.apply(
                            data, produced_by=agent.name, metadata=metadata,
                        )
                        return EvalResult(artifacts=[artifact], state=dict(inputs.state))
                    except Exception:
                        raise exc from None

                if attempt < attempts - 1 and self._is_retriable_runtime_error(exc):
                    continue
                raise
            except ValueError as exc:
                # Preserve auth/token failures as ValueError (fail-fast contract).
                if "auth/token failure" in str(exc).lower():
                    raise

                parse_error = exc
                if attempt < attempts - 1:
                    continue
                raise RuntimeError(f"OpenClaw response parse error: {exc}") from exc
            except ValidationError as exc:
                parse_error = exc
                if attempt < attempts - 1:
                    continue
                raise RuntimeError(f"OpenClaw response parse error: {exc}") from exc

            if should_stream and ctx and not getattr(self, "no_output", False):
                ctx.state["_flock_stream_live_active"] = True

            return EvalResult(artifacts=[artifact], state=dict(inputs.state))

        # Defensive fallback; loop should always return or raise.
        raise RuntimeError("OpenClaw evaluation failed unexpectedly.")

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
    ) -> dict[str, Any]:
        sinks = self._build_streaming_sinks(
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

        stream_result = await executor.execute()
        output_text = stream_result.final_text or stream_result.full_text
        return self._parse_output_text(output_text)

    def _should_stream(self, ctx) -> bool:
        if ctx is None:
            return False

        from flock.core import Agent

        return Agent._websocket_broadcast_global is not None

    def _build_streaming_sinks(self, *, agent, ctx, output_group, artifact_id):
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

        def _event_factory(output_type: str, content: str, sequence: int, is_final: bool):
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
        output_decl = output_group.outputs[0]
        output_schema = output_decl.spec.model.model_json_schema()

        input_payloads: list[dict[str, Any]] = []
        for artifact in inputs.artifacts:
            payload = artifact.payload
            if isinstance(payload, dict):
                input_payloads.append(dict(payload))
            else:
                input_payloads.append({"value": payload})

        description = str(getattr(agent, "description", "") or "").strip()

        task_lines = ["Return ONLY valid JSON matching the schema."]
        task_lines.append(f"Schema: {json.dumps(output_schema, ensure_ascii=False)}")

        if len(input_payloads) == 1:
            task_lines.append(
                f"Input: {json.dumps(input_payloads[0], ensure_ascii=False)}"
            )
        else:
            task_lines.append(
                f"Inputs: {json.dumps(input_payloads, ensure_ascii=False)}"
            )

        # Build strict JSON schema for structured output enforcement.
        # This constrains the model at the token level — it cannot produce
        # invalid JSON when the provider supports json_schema response format.
        # If the gateway doesn't support text.format, the schema is still
        # in the prompt text as fallback (belt + suspenders).
        strict_schema = self._make_strict_schema(output_schema)

        payload: dict[str, Any] = {
            "model": "openclaw",
            "input": "\n".join(task_lines),
            "stream": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": output_decl.spec.model.__name__,
                    "schema": strict_schema,
                    "strict": True,
                }
            },
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
                    k: self._strict_transform(v)
                    for k, v in node[defs_key].items()
                }

        node_type = node.get("type")

        if node_type == "object":
            props = node.get("properties", {})
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

    def _build_repair_task(self, *, original_task: str, parse_error: str) -> str:
        return (
            f"{original_task}\n\n"
            "Previous response was not valid JSON for the required schema. "
            f"Error: {parse_error}.\n"
            "Respond again with ONLY a valid JSON object and no extra text."
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
            raise RuntimeError(
                f"OpenClaw bad request (400): {message}"
            )

        if response.status_code == 429:
            message = self._extract_error_message(response)
            raise RuntimeError(
                f"OpenClaw rate limit (429): {message}"
            )

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
            raise RuntimeError(
                "OpenClaw gateway response must be a JSON object"
            )

        if str(payload_json.get("status", "")).lower() == "failed":
            message = self._extract_error_message(response)
            raise RuntimeError(f"OpenClaw response failed: {message}")

        return payload_json

    def _parse_responses_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = self._extract_responses_output_text(payload)
        return self._parse_output_text(text)

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

    def _parse_output_text(self, text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("result is not valid JSON") from exc

        if not isinstance(parsed, dict):
            raise ValueError("result JSON must be an object")

        return parsed

    @staticmethod
    def _is_unsupported_text_format_error(exc: RuntimeError) -> bool:
        """Detect 400 errors caused by gateway not supporting text.format."""
        message = str(exc).lower()
        return "400" in message and (
            "unrecognized key" in message
            or '"text"' in message
            or "text.format" in message
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
