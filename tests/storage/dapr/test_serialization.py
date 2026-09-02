from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from flock.core.artifacts import Artifact
from flock.core.store import AgentSnapshotRecord, ConsumptionRecord
from flock.core.visibility import (
    AfterVisibility,
    AgentIdentity,
    LabelledVisibility,
    PrivateVisibility,
    TenantVisibility,
)
from flock.storage.dapr._serialization import (
    _default,
    deserialize_agent_snapshot,
    deserialize_artifact,
    deserialize_consumption_records,
    deserialize_index,
    serialize_agent_snapshot,
    serialize_artifact,
    serialize_consumption_records,
    serialize_index,
)


def test_default_handles_uuid_datetime_and_set() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    value = {"id": uuid4(), "when": now, "tags": {"b", "a"}}

    payload = json.dumps(value, default=_default)
    decoded = json.loads(payload)

    assert isinstance(decoded["id"], str)
    assert decoded["when"] == now.isoformat()
    assert decoded["tags"] == ["a", "b"]


def test_default_raises_for_unsupported_type() -> None:
    with pytest.raises(TypeError):
        _default(object())


def test_artifact_roundtrip_preserves_visibility_subclass() -> None:
    artifact = Artifact(
        type="demo.Type",
        payload={"value": 1},
        produced_by="writer",
        visibility=PrivateVisibility(agents={"allowed-agent"}),
    )

    encoded = serialize_artifact(artifact)
    decoded = deserialize_artifact(encoded)

    assert isinstance(decoded.visibility, PrivateVisibility)
    assert decoded.visibility.kind == "Private"
    assert decoded.visibility.allows(AgentIdentity(name="allowed-agent"))


def test_artifact_roundtrip_preserves_nested_visibility_policy() -> None:
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    artifact = Artifact(
        type="demo.Type",
        payload={"value": 1},
        produced_by="writer",
        created_at=created_at,
        visibility=AfterVisibility(
            ttl=timedelta(days=1),
            then=PrivateVisibility(agents={"allowed-agent"}),
        ),
    )

    decoded = deserialize_artifact(serialize_artifact(artifact))

    assert isinstance(decoded.visibility, AfterVisibility)
    assert decoded.visibility.ttl == timedelta(days=1)
    assert isinstance(decoded.visibility.then, PrivateVisibility)
    assert decoded.visibility.then.agents == {"allowed-agent"}
    assert decoded.visibility.allows(
        AgentIdentity(name="allowed-agent"), now=created_at + timedelta(days=2)
    )
    assert not decoded.visibility.allows(
        AgentIdentity(name="outsider"), now=created_at + timedelta(days=2)
    )


@pytest.mark.parametrize(
    "visibility",
    [
        PrivateVisibility(),
        LabelledVisibility(),
        TenantVisibility(),
        AfterVisibility(),
        AfterVisibility(then=LabelledVisibility()),
    ],
)
def test_artifact_roundtrip_preserves_core_valid_visibility(visibility) -> None:
    artifact = Artifact(
        type="demo.Type",
        payload={"value": 1},
        produced_by="writer",
        visibility=visibility,
    )

    decoded = deserialize_artifact(serialize_artifact(artifact))

    assert type(decoded.visibility) is type(visibility)
    assert decoded.visibility.model_dump() == visibility.model_dump()


def test_deserialize_artifact_rejects_unknown_visibility_kind() -> None:
    artifact = Artifact(type="demo.Type", payload={"value": 1}, produced_by="writer")
    payload = json.loads(serialize_artifact(artifact))
    payload["visibility"] = {"kind": "Unknown"}

    with pytest.raises(ValidationError):
        deserialize_artifact(json.dumps(payload))


@pytest.mark.parametrize("kind", ["Private", "Labelled", "Tenant", "After"])
def test_deserialize_legacy_restricted_visibility_fails_closed(kind) -> None:
    artifact = Artifact(type="demo.Type", payload={"value": 1}, produced_by="writer")
    payload = json.loads(serialize_artifact(artifact))
    payload["visibility"] = {"kind": kind}

    decoded = deserialize_artifact(json.dumps(payload))
    decoded_again = deserialize_artifact(serialize_artifact(decoded))

    assert isinstance(decoded.visibility, PrivateVisibility)
    assert not decoded.visibility.allows(AgentIdentity(name="anyone"))
    assert isinstance(decoded_again.visibility, PrivateVisibility)
    assert not decoded_again.visibility.allows(AgentIdentity(name="anyone"))


def test_consumption_records_roundtrip_and_empty_decode() -> None:
    record = ConsumptionRecord(
        artifact_id=uuid4(),
        consumer="agent-a",
        run_id="run-1",
        correlation_id="corr-1",
        consumed_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    encoded = serialize_consumption_records([record])
    decoded = deserialize_consumption_records(encoded)

    assert decoded == [record]
    assert deserialize_consumption_records("") == []
    assert deserialize_consumption_records(encoded.encode("utf-8")) == [record]


def test_agent_snapshot_roundtrip_and_dict_input() -> None:
    snapshot = AgentSnapshotRecord(
        agent_name="agent-a",
        description="desc",
        subscriptions=["A"],
        output_types=["B"],
        labels=["l1"],
        first_seen=datetime(2026, 1, 3, tzinfo=UTC),
        last_seen=datetime(2026, 1, 4, tzinfo=UTC),
        signature="sig",
    )

    encoded = serialize_agent_snapshot(snapshot)
    decoded_from_json = deserialize_agent_snapshot(encoded)
    decoded_from_bytes = deserialize_agent_snapshot(encoded.encode("utf-8"))
    decoded_from_dict = deserialize_agent_snapshot(json.loads(encoded))

    assert decoded_from_json == snapshot
    assert decoded_from_bytes == snapshot
    assert decoded_from_dict == snapshot


def test_index_helpers_roundtrip_and_empty_data() -> None:
    keys = ["a", "b"]

    encoded = serialize_index(keys)

    assert deserialize_index(encoded) == keys
    assert deserialize_index(encoded.encode("utf-8")) == keys
    assert deserialize_index("") == []
