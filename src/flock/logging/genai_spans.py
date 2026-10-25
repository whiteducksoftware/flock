"""A span per model call in the OpenTelemetry GenAI semantic conventions (#680).

Observability tools such as Langfuse, Opik and Phoenix recognise a model call by
its ``gen_ai.*`` attributes; Flock's own run totals (``flock.usage.*``, #571) are
not among them. :class:`GenAISpans` is a DSPy callback that opens a
``LM.chat`` span around every LM call an engine makes, under the span that
is current at the call, and records the model, the provider, the tokens and the
Flock agent.

Message content is recorded only with
``OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true``, each side capped by
``FLOCK_TRACE_MAX_ATTRIBUTE_BYTES``. ``FLOCK_TRACE_IGNORE='["LM.chat"]'`` switches
the spans off.
"""

from __future__ import annotations

import json
import os
from typing import Any

from dspy.utils.callback import BaseCallback
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from flock.logging.trace_and_logged import _trace_filter_config, capped


tracer = trace.get_tracer(__name__)

# The span's name. The conventions suggest "chat {model}", but Flock's span names
# are "Service.operation": the trace viewer and the DuckDB exporter split them at
# the first dot, and model names have dots ("gpt-4.1"). The model is in
# gen_ai.request.model, where the tools read it.
OPERATION = "LM.chat"

# LiteLLM's provider names -> the well-known values of gen_ai.provider.name
_PROVIDERS = {
    "openai": "openai",
    "azure": "azure.ai.openai",
    "azure_ai": "azure.ai.inference",
    "anthropic": "anthropic",
    "bedrock": "aws.bedrock",
    "gemini": "gcp.gemini",
    "vertex_ai": "gcp.vertex_ai",
    "mistral": "mistral_ai",
    "groq": "groq",
    "deepseek": "deepseek",
    "xai": "x_ai",
    "cohere": "cohere",
    "perplexity": "perplexity",
}


def provider_name(model: str) -> str:
    """``gen_ai.provider.name`` for a LiteLLM model name."""
    try:
        import litellm

        provider = litellm.get_llm_provider(model)[1]
    except Exception:  # noqa: BLE001 - LiteLLM raises for models it does not map
        provider = model.split("/", 1)[0] if "/" in model else "openai"
    return _PROVIDERS.get(provider, provider)


def capture_content() -> bool:
    """Whether message content goes on the spans (off by default, as the conventions say)."""
    value = os.getenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "")
    return value.strip().lower() in {"true", "1", "yes", "on"}


def _json(value: Any) -> str:
    return capped(json.dumps(value, default=str, ensure_ascii=False))


def _history_entry(lm: Any, outputs: Any) -> dict[str, Any] | None:
    """The LM history entry of this call: DSPy stores the outputs it returns in it."""
    for entry in reversed(getattr(lm, "history", None) or []):
        if isinstance(entry, dict) and entry.get("outputs") is outputs:
            return entry
    return None


class GenAISpans(BaseCallback):
    """DSPy callback: one ``LM.chat`` span per LM call, for one agent."""

    def __init__(self, agent_name: str | None = None) -> None:
        self.agent_name = agent_name
        self._calls: dict[str, tuple[Any, Any]] = {}

    def on_lm_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        if not _trace_filter_config.should_trace("LM", OPERATION):
            return
        model = str(getattr(instance, "model", None) or "unknown")
        request = {
            **(getattr(instance, "kwargs", None) or {}),
            **(inputs.get("kwargs") or {}),
        }
        attributes: dict[str, Any] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": provider_name(model),
            "gen_ai.request.model": model,
        }
        if self.agent_name:
            attributes["gen_ai.agent.name"] = self.agent_name
        for key, attribute in (
            ("temperature", "gen_ai.request.temperature"),
            ("max_tokens", "gen_ai.request.max_tokens"),
            ("max_completion_tokens", "gen_ai.request.max_tokens"),
            ("top_p", "gen_ai.request.top_p"),
        ):
            if isinstance(request.get(key), int | float):
                attributes[attribute] = request[key]
        span = tracer.start_span(OPERATION, kind=SpanKind.CLIENT, attributes=attributes)
        if capture_content():
            messages = inputs.get("messages") or [
                {"role": "user", "content": inputs.get("prompt")}
            ]
            span.set_attribute("gen_ai.input.messages", _json(messages))
        self._calls[call_id] = (span, instance)

    def on_lm_end(
        self, call_id: str, outputs: Any, exception: Exception | None = None
    ) -> None:
        call = self._calls.pop(call_id, None)
        if call is None:
            return
        span, lm = call
        try:
            if exception is not None:
                span.record_exception(exception)
                span.set_attribute("error.type", type(exception).__qualname__)
                span.set_status(Status(StatusCode.ERROR, str(exception)))
                return
            entry = _history_entry(lm, outputs)
            if entry is not None:
                self._record_response(span, entry)
            if capture_content():
                span.set_attribute("gen_ai.output.messages", _json(outputs))
        finally:
            span.end()

    @staticmethod
    def _record_response(span: Any, entry: dict[str, Any]) -> None:
        usage = entry.get("usage") or {}
        if entry.get("response_model"):
            span.set_attribute("gen_ai.response.model", str(entry["response_model"]))
        for key, attribute in (
            ("prompt_tokens", "gen_ai.usage.input_tokens"),
            ("completion_tokens", "gen_ai.usage.output_tokens"),
        ):
            if isinstance(usage.get(key), int):
                span.set_attribute(attribute, usage[key])
        response = entry.get("response")
        response_id = getattr(response, "id", None)
        if response_id:
            span.set_attribute("gen_ai.response.id", str(response_id))
        reasons = [
            str(choice.finish_reason)
            for choice in getattr(response, "choices", None) or []
            if getattr(choice, "finish_reason", None)
        ]
        if reasons:
            span.set_attribute("gen_ai.response.finish_reasons", reasons)
