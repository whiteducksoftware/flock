"""OpenClaw engine component (Phase 1 transport implementation)."""

from __future__ import annotations

import json
from typing import Any, Literal

import httpx
from pydantic import ValidationError

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

        attempts = max(1, self.retries + 1)
        parse_error: Exception | None = None

        for attempt in range(attempts):
            payload = dict(base_payload)

            # Single repair attempt (or bounded by retries): re-ask with strict JSON reminder.
            if attempt > 0 and parse_error is not None:
                payload["input"] = self._build_repair_task(
                    original_task=str(base_payload["input"]),
                    parse_error=str(parse_error),
                )

            try:
                response_payload = await self._call_responses_api(
                    endpoint=endpoint,
                    headers=headers,
                    payload=payload,
                )
            except RuntimeError as exc:
                if attempt < attempts - 1 and self._is_retriable_runtime_error(exc):
                    continue
                raise

            try:
                data = self._parse_responses_output(response_payload)
                output_decl = output_group.outputs[0]
                artifact = output_decl.apply(
                    data,
                    produced_by=agent.name,
                    metadata={"correlation_id": ctx.correlation_id},
                )
            except (ValueError, ValidationError) as exc:
                parse_error = exc
                if attempt < attempts - 1:
                    continue
                raise RuntimeError(f"OpenClaw response parse error: {exc}") from exc

            return EvalResult(artifacts=[artifact], state=dict(inputs.state))

        # Defensive fallback; loop should always return or raise.
        raise RuntimeError("OpenClaw evaluation failed unexpectedly.")

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

        payload: dict[str, Any] = {
            "model": "openclaw",
            "input": "\n".join(task_lines),
            "stream": False,
        }
        if description:
            payload["instructions"] = description

        return payload

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

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("result is not valid JSON") from exc

        if not isinstance(parsed, dict):
            raise ValueError("result JSON must be an object")

        return parsed

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
