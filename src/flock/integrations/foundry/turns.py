"""Map Responses request input and conversation history to a text turn."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal


class UnsupportedRequestError(ValueError):
    """The request uses a feature this adapter does not implement.

    The message is safe to return to the caller.
    """


@dataclass(frozen=True, slots=True)
class TextMessage:
    """One prior message of a conversation, role preserved."""

    role: Literal["user", "assistant", "system", "developer"]
    text: str


@dataclass(frozen=True, slots=True)
class TextTurn:
    """Normalized text turn handed to the application's input mapper.

    Attributes:
        text: The current user input (all input text parts, newline-joined).
        history: Earlier messages of the conversation, oldest first. Excludes
            the current input. Empty in stateless mode.
    """

    text: str
    history: tuple[TextMessage, ...] = ()

    def history_dicts(self) -> list[dict[str, str]]:
        """History as ``[{"role": ..., "content": ...}]`` for typed inputs."""
        return [{"role": m.role, "content": m.text} for m in self.history]


# Request options the adapter cannot honour. Rejected explicitly instead of
# being silently ignored: model settings belong to the Flock application.
_UNSUPPORTED_OPTIONS = (
    "tools",
    "instructions",
    "max_output_tokens",
    "max_tool_calls",
    "temperature",
    "top_p",
    "reasoning",
    "prompt",
)
_TEXT_ROLES = {"user", "assistant", "system", "developer"}


def validate_request_options(request: Mapping[str, Any]) -> None:
    """Reject request options this adapter does not implement."""
    for option in _UNSUPPORTED_OPTIONS:
        value = request.get(option)
        if value not in (None, [], {}, ""):
            raise UnsupportedRequestError(f"The '{option}' option is not supported.")
    tool_choice = request.get("tool_choice")
    if tool_choice not in (None, "auto", "none"):
        raise UnsupportedRequestError("Only tool_choice 'auto' or 'none' is supported.")
    text = request.get("text")
    if isinstance(text, Mapping):
        fmt = text.get("format")
        if isinstance(fmt, Mapping) and fmt.get("type") not in (None, "text"):
            raise UnsupportedRequestError("Only the 'text' output format is supported.")


def _message_text(item: Mapping[str, Any], allowed_parts: set[str]) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    texts: list[str] = []
    for part in content or []:
        if not isinstance(part, Mapping) or part.get("type") not in allowed_parts:
            kind = (
                part.get("type") if isinstance(part, Mapping) else type(part).__name__
            )
            raise UnsupportedRequestError(
                f"Only text content is supported (got '{kind}')."
            )
        texts.append(str(part.get("text") or ""))
    return "\n".join(texts)


def input_text(items: Sequence[Any]) -> str:
    """Current turn text from the request's input items (user text only)."""
    texts: list[str] = []
    for item in items:
        if not isinstance(item, Mapping) or item.get("type", "message") != "message":
            kind = (
                item.get("type") if isinstance(item, Mapping) else type(item).__name__
            )
            raise UnsupportedRequestError(
                f"Only message input is supported (got '{kind}')."
            )
        if item.get("role", "user") != "user":
            raise UnsupportedRequestError("Only user messages are supported as input.")
        texts.append(_message_text(item, {"input_text"}))
    text = "\n".join(t for t in texts if t)
    if not text.strip():
        raise UnsupportedRequestError("The request contains no text input.")
    return text


def history_messages(items: Sequence[Any]) -> tuple[TextMessage, ...]:
    """Text messages from stored conversation history, roles preserved.

    Non-message items (tool calls, reasoning) are not part of a text
    conversation and are skipped.
    """
    messages: list[TextMessage] = []
    for item in items:
        if not isinstance(item, Mapping) or item.get("type", "message") != "message":
            continue
        role = item.get("role", "user")
        if role not in _TEXT_ROLES:
            continue
        try:
            text = _message_text(item, {"input_text", "output_text"})
        except UnsupportedRequestError:
            continue
        messages.append(TextMessage(role=role, text=text))
    return tuple(messages)


__all__ = [
    "TextMessage",
    "TextTurn",
    "UnsupportedRequestError",
    "history_messages",
    "input_text",
    "validate_request_options",
]
