"""JSON serialization helpers for Dapr state values.

Artifact uses Pydantic's built-in serialization.  The dataclass-based
types (ConsumptionRecord, AgentSnapshotRecord) need manual handling for
UUID and datetime fields.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from flock.core.artifacts import Artifact
from flock.core.visibility import PrivateVisibility


if TYPE_CHECKING:
    from flock.core.store import AgentSnapshotRecord, ConsumptionRecord


# -- JSON encoder for dataclass types ----------------------------------------


def _default(obj: Any) -> Any:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# -- Artifact -----------------------------------------------------------------


def serialize_artifact(artifact: Artifact) -> str:
    return artifact.model_dump_json()


def deserialize_artifact(data: str | bytes) -> Artifact:
    payload = json.loads(data)
    visibility = payload.get("visibility")
    # <=0.5.602 persisted only the kind; deny access when policy data is gone.
    if isinstance(visibility, dict) and (
        (
            set(visibility) == {"kind"}
            and visibility["kind"] in {"Private", "Labelled", "Tenant", "After"}
        )
        or visibility == {"kind": "Private", "agents": []}
    ):
        payload["visibility"] = PrivateVisibility()
    return Artifact.model_validate(payload)


# -- ConsumptionRecord -------------------------------------------------------


def serialize_consumption_records(records: list[ConsumptionRecord]) -> str:
    return json.dumps([asdict(r) for r in records], default=_default)


def deserialize_consumption_records(data: str | bytes) -> list[ConsumptionRecord]:
    from flock.core.store import ConsumptionRecord

    items = json.loads(data) if data else []
    return [
        ConsumptionRecord(
            artifact_id=UUID(item["artifact_id"]),
            consumer=item["consumer"],
            run_id=item.get("run_id"),
            correlation_id=item.get("correlation_id"),
            consumed_at=datetime.fromisoformat(item["consumed_at"]),
        )
        for item in items
    ]


# -- AgentSnapshotRecord -----------------------------------------------------


def serialize_agent_snapshot(snapshot: AgentSnapshotRecord) -> str:
    return json.dumps(asdict(snapshot), default=_default)


def deserialize_agent_snapshot(data: str | bytes) -> AgentSnapshotRecord:
    from flock.core.store import AgentSnapshotRecord

    item = json.loads(data) if isinstance(data, (str, bytes)) else data
    return AgentSnapshotRecord(
        agent_name=item["agent_name"],
        description=item["description"],
        subscriptions=item["subscriptions"],
        output_types=item["output_types"],
        labels=item["labels"],
        first_seen=datetime.fromisoformat(item["first_seen"]),
        last_seen=datetime.fromisoformat(item["last_seen"]),
        signature=item["signature"],
    )


# -- Index helpers (JSON lists of strings) ------------------------------------


def serialize_index(keys: list[str]) -> str:
    return json.dumps(keys)


def deserialize_index(data: str | bytes) -> list[str]:
    if not data:
        return []
    return json.loads(data)
