"""Dapr-Backed Blackboard Storage for Flock."""

from importlib import import_module
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.storage.dapr._client import create_dapr_client
    from flock.storage.dapr._serialization import (
        deserialize_agent_snapshot,
        deserialize_artifact,
        deserialize_consumption_records,
        deserialize_index,
        serialize_agent_snapshot,
        serialize_artifact,
        serialize_consumption_records,
        serialize_index,
    )
    from flock.storage.dapr.dapr_state_blackboard_store import (
        DaprStateBlackboardConfig,
        DaprStateBlackboardStore,
        DaprStateBlackboardStoreClientConfig,
    )


_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "DaprStateBlackboardConfig": (
        "flock.storage.dapr.dapr_state_blackboard_store",
        "DaprStateBlackboardConfig",
    ),
    "DaprStateBlackboardStore": (
        "flock.storage.dapr.dapr_state_blackboard_store",
        "DaprStateBlackboardStore",
    ),
    "DaprStateBlackboardStoreClientConfig": (
        "flock.storage.dapr.dapr_state_blackboard_store",
        "DaprStateBlackboardStoreClientConfig",
    ),
    "create_dapr_client": (
        "flock.storage.dapr._client",
        "create_dapr_client",
    ),
    "serialize_agent_snapshot": (
        "flock.storage.dapr._serialization",
        "serialize_agent_snapshot",
    ),
    "serialize_artifact": (
        "flock.storage.dapr._serialization",
        "serialize_artifact",
    ),
    "serialize_consumption_records": (
        "flock.storage.dapr._serialization",
        "serialize_consumption_records",
    ),
    "serialize_index": (
        "flock.storage.dapr._serialization",
        "serialize_index",
    ),
    "deserialize_agent_snapshot": (
        "flock.storage.dapr._serialization",
        "deserialize_agent_snapshot",
    ),
    "deserialize_artifact": (
        "flock.storage.dapr._serialization",
        "deserialize_artifact",
    ),
    "deserialize_consumption_records": (
        "flock.storage.dapr._serialization",
        "deserialize_consumption_records",
    ),
    "deserialize_index": (
        "flock.storage.dapr._serialization",
        "deserialize_index",
    ),
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
    "DaprStateBlackboardConfig",
    "DaprStateBlackboardStore",
    "DaprStateBlackboardStoreClientConfig",
    "create_dapr_client",
    "deserialize_agent_snapshot",
    "deserialize_artifact",
    "deserialize_consumption_records",
    "deserialize_index",
    "serialize_agent_snapshot",
    "serialize_artifact",
    "serialize_consumption_records",
    "serialize_index",
]
