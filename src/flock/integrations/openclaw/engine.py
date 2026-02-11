"""OpenClaw engine component (Phase 1 transport implementation)."""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

import httpx

from flock.components.agent import EngineComponent
from flock.integrations.openclaw.config import GatewayConfig
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

        endpoint = f"{self.gateway.url.rstrip('/')}/api/sessions/spawn"
        headers = {
            "Content-Type": "application/json",
        }
        if self.gateway.token:
            headers["Authorization"] = f"Bearer {self.gateway.token}"

        base_payload = self._build_spawn_payload(
            ctx=ctx, inputs=inputs, output_group=output_group
        )

        attempts = max(1, self.retries + 1)
        parse_error: ValueError | None = None

        for attempt in range(attempts):
            payload = dict(base_payload)

            # Single repair attempt (or bounded by retries): re-ask with strict JSON reminder.
            if attempt > 0 and parse_error is not None:
                payload["task"] = self._build_repair_task(
                    original_task=base_payload["task"],
                    parse_error=str(parse_error),
                )
                payload["label"] = f"{base_payload['label']}-repair-{attempt}"

            try:
                response_payload = await self._spawn_once(
                    endpoint=endpoint,
                    headers=headers,
                    payload=payload,
                )
            except RuntimeError as exc:
                if attempt < attempts - 1 and self._is_retriable_runtime_error(exc):
                    continue
                raise

            try:
                data = self._parse_result_payload(response_payload)
            except ValueError as exc:
                parse_error = exc
                if attempt < attempts - 1:
                    continue
                raise RuntimeError(f"OpenClaw response parse error: {exc}") from exc

            output_decl = output_group.outputs[0]
            artifact = output_decl.apply(
                data,
                produced_by=agent.name,
                metadata={"correlation_id": ctx.correlation_id},
            )
            return EvalResult(artifacts=[artifact], state=dict(inputs.state))

        # Defensive fallback; loop should always return or raise.
        raise RuntimeError("OpenClaw evaluation failed unexpectedly.")

    def _build_spawn_payload(self, *, ctx, inputs, output_group) -> dict[str, Any]:
        output_decl = output_group.outputs[0]
        input_payload = dict(inputs.artifacts[0].payload)
        output_schema = output_decl.spec.model.model_json_schema()

        task = (
            "Return ONLY valid JSON matching the schema.\n"
            f"Schema: {json.dumps(output_schema, ensure_ascii=False)}\n"
            f"Input: {json.dumps(input_payload, ensure_ascii=False)}"
        )

        correlation = (ctx.correlation_id or uuid4().hex).replace("-", "")
        label = f"flock-{self.alias}-{correlation[:12]}"

        return {
            "task": task,
            "label": label,
            "runTimeoutSeconds": self.timeout,
            "cleanup": "delete",
        }

    def _build_repair_task(self, *, original_task: str, parse_error: str) -> str:
        return (
            f"{original_task}\n\n"
            "Previous response was not valid JSON for the required schema. "
            f"Error: {parse_error}.\n"
            "Respond again with ONLY a valid JSON object and no extra text."
        )

    async def _spawn_once(
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
            raise RuntimeError(  # noqa: TRY004 - Phase 1 maps gateway parse failures to RuntimeError.
                "OpenClaw gateway response must be a JSON object"
            )

        # Handle API-level auth signaling even with 200 (defensive).
        if payload_json.get("ok") is False:
            err = str(payload_json.get("error", "")).lower()
            message = str(
                payload_json.get("message", "OpenClaw gateway rejected request")
            )
            if "auth" in err or "token" in err or "unauth" in err or "forbidden" in err:
                raise ValueError(f"OpenClaw auth/token failure: {message}")

        return payload_json

    def _parse_result_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "result" not in payload:
            raise ValueError("missing 'result' in spawn response")

        raw_result = payload["result"]

        if isinstance(raw_result, dict):
            return raw_result

        if isinstance(raw_result, str):
            try:
                parsed = json.loads(raw_result)
            except json.JSONDecodeError as exc:
                raise ValueError("result is not valid JSON") from exc

            if not isinstance(parsed, dict):
                raise ValueError(  # noqa: TRY004 - Phase 1 treats malformed payload shape as parse ValueError.
                    "result JSON must be an object"
                )
            return parsed

        raise ValueError("result must be a JSON string or object")

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
            )
        )

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text or "no error body"

        if isinstance(payload, dict):
            for key in ("message", "error", "detail"):
                value = payload.get(key)
                if value:
                    return str(value)
        return "unknown error"
