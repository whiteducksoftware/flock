"""Monkey-patches for DSPy streaming behavior used by Flock.

This module applies two focused patches:
1. Replace DSPy's blocking ``sync_send_to_stream`` with a non-blocking variant
   to avoid event loop deadlocks with MCP tools.
2. Bridge DSPy ``model_type='responses'`` streaming through LiteLLM so
   Responses SSE delta events are forwarded into DSPy's stream channel.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any

from flock.logging.logging import get_logger


logger = get_logger(__name__)

_ORIGINAL_SYNC_SEND_ATTR = "_original_sync_send_to_stream"
_ORIGINAL_RESPONSES_COMPLETION_ATTR = "_flock_original_litellm_responses_completion"
_ORIGINAL_ARESPONSES_COMPLETION_ATTR = "_flock_original_alitellm_responses_completion"
_BACKGROUND_STREAM_TASKS: set[asyncio.Task[Any]] = set()


def patched_sync_send_to_stream(stream, message):
    """Non-blocking replacement for DSPy's ``sync_send_to_stream``."""

    async def _send():
        try:
            await stream.send(message)
        except Exception as e:
            logger.debug(f"DSPy status message send failed (non-critical): {e}")

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_send())
        _BACKGROUND_STREAM_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_STREAM_TASKS.discard)
    except RuntimeError:
        try:
            asyncio.run(_send())
        except Exception as e:
            logger.debug(
                f"DSPy status message send failed in sync context (non-critical): {e}"
            )


def _extract_event_type(event: Any) -> str:
    if isinstance(event, dict):
        value = event.get("type") or event.get("event")
    else:
        value = getattr(event, "type", None) or getattr(event, "event", None)
    return str(value) if value else ""


def _extract_completed_response(event: Any) -> Any | None:
    if event is None:
        return None
    if isinstance(event, dict):
        return event.get("response")
    return getattr(event, "response", None)


def _extract_event_text(event: Any) -> str:
    event_type = _extract_event_type(event)
    extracted = ""

    if isinstance(event, dict):
        delta = event.get("delta")
        text = event.get("text")
        part = event.get("part")
    else:
        delta = getattr(event, "delta", None)
        text = getattr(event, "text", None)
        part = getattr(event, "part", None)

    if event_type == "response.output_text.delta":
        if isinstance(delta, str):
            extracted = delta
        elif isinstance(delta, dict):
            delta_text = delta.get("text")
            if isinstance(delta_text, str):
                extracted = delta_text

    elif event_type == "response.output_text.done":
        if isinstance(text, str):
            extracted = text

    elif event_type in {"response.content_part.added", "response.content_part.done"}:
        if isinstance(part, dict):
            if part.get("type") == "output_text":
                part_text = part.get("text")
                if isinstance(part_text, str):
                    extracted = part_text
        elif getattr(part, "type", None) == "output_text":
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str):
                extracted = part_text

    return extracted


def _extract_response_output_text(response: Any) -> str:
    if response is None:
        return ""

    if isinstance(response, dict):
        output = response.get("output")
    else:
        output = getattr(response, "output", None)

    if not isinstance(output, list):
        return ""

    chunks: list[str] = []
    for item in output:
        if isinstance(item, dict):
            item_type = item.get("type")
            content = item.get("content")
        else:
            item_type = getattr(item, "type", None)
            content = getattr(item, "content", None)

        if item_type != "message" or not isinstance(content, list):
            continue

        for part in content:
            if isinstance(part, dict):
                part_type = part.get("type")
                text = part.get("text")
            else:
                part_type = getattr(part, "type", None)
                text = getattr(part, "text", None)
            if part_type == "output_text" and isinstance(text, str):
                chunks.append(text)

    return "".join(chunks)


def _chunk_text(text: str, chunk_size: int = 24) -> list[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _normalize_completed_response(final_response: Any) -> Any:
    try:
        from litellm.types.llms.openai import ResponsesAPIResponse

        if isinstance(final_response, ResponsesAPIResponse):
            return ResponsesAPIResponse.model_validate(final_response.model_dump())
        if isinstance(final_response, dict):
            return ResponsesAPIResponse.model_validate(final_response)
    except Exception:
        return final_response
    return final_response


def _set_predict_id(event: Any, caller_predict_id: int | None) -> Any:
    if caller_predict_id is None:
        return event
    if isinstance(event, dict):
        if "predict_id" not in event:
            event = dict(event)
            event["predict_id"] = caller_predict_id
        return event
    if getattr(event, "predict_id", None) is None:
        try:
            event.predict_id = caller_predict_id
        except Exception:
            pass
    return event


def _stream_context() -> tuple[Any | None, int | None]:
    import dspy

    stream = dspy.settings.send_stream
    caller_predict = dspy.settings.caller_predict
    caller_predict_id = id(caller_predict) if caller_predict else None
    return stream, caller_predict_id


def _prepare_responses_request(
    dspy_lm: Any,
    request: dict[str, Any],
    cache: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cache_kwargs = cache or {"no-cache": True, "no-store": True}
    prepared_request = dict(request)
    prepared_request.pop("rollout_id", None)
    headers = dspy_lm._add_dspy_identifier_to_headers(  # noqa: SLF001
        prepared_request.pop("headers", None)
    )
    prepared_request = dspy_lm._convert_chat_request_to_responses_request(  # noqa: SLF001
        prepared_request
    )
    prepared_request["stream"] = True
    return prepared_request, headers, cache_kwargs


def _iter_sync_events(response_stream: Any) -> Iterator[Any]:
    if hasattr(response_stream, "__iter__"):
        yield from response_stream
        return
    raise TypeError(
        "Responses streaming bridge expected an iterator for sync responses request."
    )


async def _iter_async_events(response_stream: Any) -> AsyncIterator[Any]:
    if hasattr(response_stream, "__aiter__"):
        async for event in response_stream:
            yield event
        return
    raise TypeError(
        "Responses streaming bridge expected an async iterator for async responses request."
    )


def _send_sync_stream_event(stream: Any, event: Any) -> None:
    import dspy.streaming.messages as dspy_messages

    send_fn = getattr(dspy_messages, "sync_send_to_stream", None)
    if callable(send_fn):
        send_fn(stream, event)
        return
    patched_sync_send_to_stream(stream, event)


def patched_litellm_responses_completion(
    request: dict[str, Any],
    num_retries: int,
    cache: dict[str, Any] | None = None,
):
    """DSPy sync responses completion with streaming bridge support."""
    import dspy.clients.lm as dspy_lm
    import litellm

    stream, caller_predict_id = _stream_context()
    original_completion = getattr(dspy_lm, _ORIGINAL_RESPONSES_COMPLETION_ATTR, None)
    if stream is None:
        if callable(original_completion):
            return original_completion(request=request, num_retries=num_retries, cache=cache)
        return dspy_lm.litellm_responses_completion(  # pragma: no cover - defensive fallback
            request=request, num_retries=num_retries, cache=cache
        )

    prepared_request, headers, cache_kwargs = _prepare_responses_request(
        dspy_lm, request, cache
    )
    model_name = str(prepared_request.get("model", ""))
    provider = model_name.split("/", 1)[0] if "/" in model_name else "unknown"
    logger.debug(
        "Responses stream bridge active: mode=responses provider=%s model=%s",
        provider,
        model_name,
    )

    response_stream = litellm.responses(
        cache=cache_kwargs,
        num_retries=num_retries,
        retry_strategy="exponential_backoff_retry",
        headers=headers,
        **prepared_request,
    )

    if not hasattr(response_stream, "__iter__"):
        logger.debug(
            "Responses stream bridge received non-streaming sync response for model=%s",
            model_name,
        )
        return response_stream

    final_response = None
    token_events = 0
    first_delta_logged = False

    for event in _iter_sync_events(response_stream):
        event = _set_predict_id(event, caller_predict_id)
        event_type = _extract_event_type(event)
        event_text = _extract_event_text(event)

        if event_type in {"response.output_text.delta", "response.output_text.done"} and event_text:
            token_events += 1
            if not first_delta_logged:
                logger.debug(
                    "Responses stream bridge received first delta for model=%s",
                    model_name,
                )
                first_delta_logged = True
        elif event_type == "response.completed":
            final_response = _extract_completed_response(event)

        _send_sync_stream_event(stream, event)

    if final_response is None:
        completed_event = getattr(response_stream, "completed_response", None)
        final_response = _extract_completed_response(completed_event)

    if final_response is None:
        raise RuntimeError(
            f"Responses stream bridge did not receive a response.completed event for model '{model_name}'."
        )

    final_response = _normalize_completed_response(final_response)

    if token_events == 0:
        fallback_text = _extract_response_output_text(final_response)
        if fallback_text:
            for chunk in _chunk_text(fallback_text):
                synthetic_event = _set_predict_id(
                    {"type": "response.output_text.delta", "delta": chunk},
                    caller_predict_id,
                )
                _send_sync_stream_event(stream, synthetic_event)
                token_events += 1
            logger.debug(
                "Responses stream bridge emitted synthetic text deltas: model=%s chunks=%s",
                model_name,
                token_events,
            )

    logger.debug(
        "Responses stream bridge completed: model=%s provider=%s token_events=%s",
        model_name,
        provider,
        token_events,
    )
    return final_response


async def patched_alitellm_responses_completion(
    request: dict[str, Any],
    num_retries: int,
    cache: dict[str, Any] | None = None,
):
    """DSPy async responses completion with streaming bridge support."""
    import dspy.clients.lm as dspy_lm
    import litellm

    stream, caller_predict_id = _stream_context()
    original_completion = getattr(dspy_lm, _ORIGINAL_ARESPONSES_COMPLETION_ATTR, None)
    if stream is None:
        if callable(original_completion):
            return await original_completion(
                request=request, num_retries=num_retries, cache=cache
            )
        return await dspy_lm.alitellm_responses_completion(  # pragma: no cover - defensive fallback
            request=request, num_retries=num_retries, cache=cache
        )

    prepared_request, headers, cache_kwargs = _prepare_responses_request(
        dspy_lm, request, cache
    )
    model_name = str(prepared_request.get("model", ""))
    provider = model_name.split("/", 1)[0] if "/" in model_name else "unknown"
    logger.debug(
        "Responses stream bridge active: mode=responses provider=%s model=%s",
        provider,
        model_name,
    )

    response_stream = await litellm.aresponses(
        cache=cache_kwargs,
        num_retries=num_retries,
        retry_strategy="exponential_backoff_retry",
        headers=headers,
        **prepared_request,
    )

    if not hasattr(response_stream, "__aiter__"):
        logger.debug(
            "Responses stream bridge received non-streaming async response for model=%s",
            model_name,
        )
        return response_stream

    final_response = None
    token_events = 0
    first_delta_logged = False

    async for event in _iter_async_events(response_stream):
        event = _set_predict_id(event, caller_predict_id)
        event_type = _extract_event_type(event)
        event_text = _extract_event_text(event)

        if event_type in {"response.output_text.delta", "response.output_text.done"} and event_text:
            token_events += 1
            if not first_delta_logged:
                logger.debug(
                    "Responses stream bridge received first delta for model=%s",
                    model_name,
                )
                first_delta_logged = True
        elif event_type == "response.completed":
            final_response = _extract_completed_response(event)

        await stream.send(event)

    if final_response is None:
        completed_event = getattr(response_stream, "completed_response", None)
        final_response = _extract_completed_response(completed_event)

    if final_response is None:
        raise RuntimeError(
            f"Responses stream bridge did not receive a response.completed event for model '{model_name}'."
        )

    final_response = _normalize_completed_response(final_response)

    if token_events == 0:
        fallback_text = _extract_response_output_text(final_response)
        if fallback_text:
            for chunk in _chunk_text(fallback_text):
                synthetic_event = _set_predict_id(
                    {"type": "response.output_text.delta", "delta": chunk},
                    caller_predict_id,
                )
                await stream.send(synthetic_event)
                token_events += 1
            logger.debug(
                "Responses stream bridge emitted synthetic text deltas: model=%s chunks=%s",
                model_name,
                token_events,
            )

    logger.debug(
        "Responses stream bridge completed: model=%s provider=%s token_events=%s",
        model_name,
        provider,
        token_events,
    )
    return final_response


def apply_patch():
    """Apply monkey-patches to DSPy streaming and responses completion paths."""
    try:
        import dspy.clients.lm as dspy_lm
        import dspy.streaming.messages as dspy_messages

        if not hasattr(dspy_messages, _ORIGINAL_SYNC_SEND_ATTR):
            setattr(
                dspy_messages,
                _ORIGINAL_SYNC_SEND_ATTR,
                dspy_messages.sync_send_to_stream,
            )
        dspy_messages.sync_send_to_stream = patched_sync_send_to_stream

        if not hasattr(dspy_lm, _ORIGINAL_RESPONSES_COMPLETION_ATTR):
            setattr(
                dspy_lm,
                _ORIGINAL_RESPONSES_COMPLETION_ATTR,
                dspy_lm.litellm_responses_completion,
            )
        if not hasattr(dspy_lm, _ORIGINAL_ARESPONSES_COMPLETION_ATTR):
            setattr(
                dspy_lm,
                _ORIGINAL_ARESPONSES_COMPLETION_ATTR,
                dspy_lm.alitellm_responses_completion,
            )

        dspy_lm.litellm_responses_completion = patched_litellm_responses_completion
        dspy_lm.alitellm_responses_completion = patched_alitellm_responses_completion

        logger.info(
            "Applied DSPy streaming patch: non-blocking status + responses stream bridge"
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to apply DSPy streaming patch: {e}")
        return False


def restore_original():
    """Restore original DSPy functions (for testing/debugging)."""
    try:
        import dspy.clients.lm as dspy_lm
        import dspy.streaming.messages as dspy_messages

        original_sync_send = getattr(dspy_messages, _ORIGINAL_SYNC_SEND_ATTR, None)
        if original_sync_send is not None:
            dspy_messages.sync_send_to_stream = original_sync_send

        original_sync_responses = getattr(dspy_lm, _ORIGINAL_RESPONSES_COMPLETION_ATTR, None)
        if original_sync_responses is not None:
            dspy_lm.litellm_responses_completion = original_sync_responses

        original_async_responses = getattr(
            dspy_lm, _ORIGINAL_ARESPONSES_COMPLETION_ATTR, None
        )
        if original_async_responses is not None:
            dspy_lm.alitellm_responses_completion = original_async_responses

        logger.info("Restored original DSPy streaming functions")
        return True
    except Exception as e:
        logger.warning(f"Failed to restore original DSPy function: {e}")
        return False
