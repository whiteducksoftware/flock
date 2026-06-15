"""Storage backends for Flock blackboard."""

from importlib import import_module
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.storage.dapr import (
        DaprStateBlackboardConfig,
        DaprStateBlackboardStore,
        DaprStateBlackboardStoreClientConfig,
        create_dapr_client,
        deserialize_agent_snapshot,
        deserialize_artifact,
        deserialize_consumption_records,
        deserialize_index,
        serialize_agent_snapshot,
        serialize_artifact,
        serialize_consumption_records,
        serialize_index,
    )
    from flock.storage.sqlite.query_builder import SQLiteQueryBuilder
    from flock.storage.sqlite.schema_manager import SQLiteSchemaManager


_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "DaprStateBlackboardConfig": (
        "flock.storage.dapr",
        "DaprStateBlackboardConfig",
    ),
    "DaprStateBlackboardStore": (
        "flock.storage.dapr",
        "DaprStateBlackboardStore",
    ),
    "DaprStateBlackboardStoreClientConfig": (
        "flock.storage.dapr",
        "DaprStateBlackboardStoreClientConfig",
    ),
    "create_dapr_client": (
        "flock.storage.dapr",
        "create_dapr_client",
    ),
    "deserialize_agent_snapshot": (
        "flock.storage.dapr",
        "deserialize_agent_snapshot",
    ),
    "deserialize_artifact": (
        "flock.storage.dapr",
        "deserialize_artifact",
    ),
    "deserialize_consumption_records": (
        "flock.storage.dapr",
        "deserialize_consumption_records",
    ),
    "deserialize_index": (
        "flock.storage.dapr",
        "deserialize_index",
    ),
    "serialize_agent_snapshot": (
        "flock.storage.dapr",
        "serialize_agent_snapshot",
    ),
    "serialize_artifact": (
        "flock.storage.dapr",
        "serialize_artifact",
    ),
    "serialize_consumption_records": (
        "flock.storage.dapr",
        "serialize_consumption_records",
    ),
    "serialize_index": (
        "flock.storage.dapr",
        "serialize_index",
    ),
    "SQLiteQueryBuilder": (
        "flock.storage.sqlite.query_builder",
        "SQLiteQueryBuilder",
    ),
    "SQLiteSchemaManager": (
        "flock.storage.sqlite.schema_manager",
        "SQLiteSchemaManager",
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
    "SQLiteQueryBuilder",
    "SQLiteSchemaManager",
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
