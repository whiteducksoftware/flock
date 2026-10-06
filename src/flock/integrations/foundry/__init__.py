"""Host Flock applications as Microsoft Foundry hosted agents.

Install with ``flock-core[foundry]``. The adapter maps Foundry's Responses
protocol (via the official ``azure-ai-agentserver-responses`` SDK) onto a
:class:`flock.application.FlockApplication`::

    from flock.integrations.foundry import FoundryResponsesAdapter

    host = FoundryResponsesAdapter(
        application,
        history_mode="conversation",
        input_mapper=lambda turn: IncidentRequest(
            report=turn.text, history=turn.history_dicts()
        ),
        output_mapper=lambda summary: summary.summary,
    )

    if __name__ == "__main__":
        host.run()

Exports resolve lazily, so importing this package never loads the Azure SDK
until an adapter symbol is used.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.integrations.foundry.adapter import (
        ATTR_CALL_ID,
        ATTR_CONVERSATION_ID,
        ATTR_SESSION_ID,
        FOUNDRY_CALL_ID_HEADER,
        FoundryResponsesAdapter,
        foundry_headers,
        json_text,
    )
    from flock.integrations.foundry.identity import (
        IdentityPolicy,
        IdentityRequiredError,
        running_in_foundry,
    )
    from flock.integrations.foundry.turns import (
        TextMessage,
        TextTurn,
        UnsupportedRequestError,
    )


_ADAPTER = "flock.integrations.foundry.adapter"
_IDENTITY = "flock.integrations.foundry.identity"
_TURNS = "flock.integrations.foundry.turns"

_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "ATTR_CALL_ID": (_ADAPTER, "ATTR_CALL_ID"),
    "ATTR_CONVERSATION_ID": (_ADAPTER, "ATTR_CONVERSATION_ID"),
    "ATTR_SESSION_ID": (_ADAPTER, "ATTR_SESSION_ID"),
    "FOUNDRY_CALL_ID_HEADER": (_ADAPTER, "FOUNDRY_CALL_ID_HEADER"),
    "FoundryResponsesAdapter": (_ADAPTER, "FoundryResponsesAdapter"),
    "foundry_headers": (_ADAPTER, "foundry_headers"),
    "json_text": (_ADAPTER, "json_text"),
    "IdentityPolicy": (_IDENTITY, "IdentityPolicy"),
    "IdentityRequiredError": (_IDENTITY, "IdentityRequiredError"),
    "running_in_foundry": (_IDENTITY, "running_in_foundry"),
    "TextMessage": (_TURNS, "TextMessage"),
    "TextTurn": (_TURNS, "TextTurn"),
    "UnsupportedRequestError": (_TURNS, "UnsupportedRequestError"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORT_MAP.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value


__all__ = [
    "ATTR_CALL_ID",
    "ATTR_CONVERSATION_ID",
    "ATTR_SESSION_ID",
    "FOUNDRY_CALL_ID_HEADER",
    "FoundryResponsesAdapter",
    "IdentityPolicy",
    "IdentityRequiredError",
    "TextMessage",
    "TextTurn",
    "UnsupportedRequestError",
    "foundry_headers",
    "json_text",
    "running_in_foundry",
]
