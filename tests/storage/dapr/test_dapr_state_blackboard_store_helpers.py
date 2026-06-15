from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from dapr.clients.retry import RetryPolicy
from grpc import StatusCode
from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.store import (
    AgentSnapshotRecord,
    ArtifactEnvelope,
    ConsumptionRecord,
    FilterConfig,
)
from flock.storage.dapr._serialization import serialize_agent_snapshot
from flock.storage.dapr.dapr_state_blackboard_store import (
    DaprStateBlackboardConfig,
    DaprStateBlackboardStoreClientConfig,
    DaprStateBlackboardStore,
    _artifact_key,
    _build_dapr_query,
    _consumptions_key,
    _snapshot_key,
    _type_index_key,
)


DaprStateBlackboardStoreClientConfig.model_rebuild(
    _types_namespace={"RetryPolicy": RetryPolicy}
)
DaprStateBlackboardConfig.model_rebuild(
    _types_namespace={
        "DaprStateBlackboardStoreClientConfig": DaprStateBlackboardStoreClientConfig,
    }
)


class _DummyClient:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeError(Exception):
    def __init__(self, code: StatusCode, details: str = "") -> None:
        self._code = code
        self._details = details

    def code(self) -> StatusCode:
        return self._code

    def details(self) -> str:
        return self._details


class _FakeStateResponse:
    def __init__(self, data: str = "", etag: str | None = None) -> None:
        self._data = data
        self.etag = etag

    def text(self) -> str:
        return self._data


class _FakeBulkItem:
    def __init__(self, key: str, data: str = "", error: str | None = None) -> None:
        self.key = key
        self._data = data
        self.error = error

    def text(self) -> str:
        return self._data


def _make_store(
    monkeypatch, **config_overrides
) -> tuple[DaprStateBlackboardStore, _DummyClient]:
    dummy_client = _DummyClient()
    monkeypatch.setattr(
        "flock.storage.dapr.dapr_state_blackboard_store.create_dapr_client",
        lambda _cfg: dummy_client,
    )
    monkeypatch.setattr(
        "flock.storage.dapr.dapr_state_blackboard_store.atexit.register",
        lambda *_: None,
    )

    config = DaprStateBlackboardConfig(
        store_name="test-store",
        **config_overrides,
    )
    return DaprStateBlackboardStore(config), dummy_client


def test_key_helpers_build_expected_prefixes() -> None:
    artifact_id = uuid4()

    assert _artifact_key(artifact_id) == f"artifact:{artifact_id}"
    assert _type_index_key("demo.Type") == "idx:type:demo.Type"
    assert _consumptions_key(artifact_id) == f"consumptions:{artifact_id}"
    assert _snapshot_key("agent-a") == "snapshot:agent-a"


def test_build_dapr_query_without_filters_has_only_sort() -> None:
    query = json.loads(_build_dapr_query(None))

    assert query == {"sort": [{"key": "created_at", "order": "ASC"}]}


def test_build_dapr_query_with_single_and_multiple_filters() -> None:
    single = json.loads(_build_dapr_query(FilterConfig(type_names={"A"}, tags={"x"})))
    assert single["filter"] == {"EQ": {"type": "A"}}
    assert single["sort"] == [{"key": "created_at", "order": "ASC"}]

    filters = FilterConfig(
        type_names={"B", "A"},
        produced_by={"writer", "reviewer"},
        correlation_id="corr-1",
        visibility={"Public", "Private"},
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 31, tzinfo=UTC),
        tags={"ignored-in-query"},
    )
    multiple = json.loads(_build_dapr_query(filters))

    assert "AND" in multiple["filter"]
    and_conditions = multiple["filter"]["AND"]
    assert {"IN": {"type": ["A", "B"]}} in and_conditions
    assert {"IN": {"produced_by": ["reviewer", "writer"]}} in and_conditions
    assert {"EQ": {"correlation_id": "corr-1"}} in and_conditions
    assert {"IN": {"visibility.kind": ["Private", "Public"]}} in and_conditions
    assert {"GTE": {"created_at": "2026-01-01T00:00:00+00:00"}} in and_conditions
    assert {"LTE": {"created_at": "2026-01-31T00:00:00+00:00"}} in and_conditions
    assert "tags" not in json.dumps(multiple)


def test_config_validator_warns_for_ttl_without_support(capsys) -> None:
    _ = DaprStateBlackboardConfig(supports_ttl=False, entries_ttl_seconds=30)

    assert (
        "entries_ttl_seconds is set but supports_ttl is False"
        in capsys.readouterr().out
    )


def test_config_validator_disables_transactions_for_encrypted_backend(capsys) -> None:
    config = DaprStateBlackboardConfig(
        encrypted_backend=True,
        supports_transactions=True,
    )

    assert config.supports_transactions is False
    assert (
        "Encrypted backend with transactions is not supported"
        in capsys.readouterr().out
    )


def test_store_metadata_and_close(monkeypatch) -> None:
    store, dummy_client = _make_store(
        monkeypatch,
        supports_ttl=True,
        entries_ttl_seconds=60,
    )

    assert store._create_state_metadata_for_save("k", ttl=60) == {"ttlInSeconds": "60"}
    assert store._create_state_metadata_for_save("k", ttl=0) == {}
    assert store._create_state_metadata_for_save("k", ttl=None) == {}

    store.close()
    assert dummy_client.closed


def test_build_state_options_respects_etag_and_consistency(monkeypatch) -> None:
    etag_store, _ = _make_store(monkeypatch, supports_etag=True)
    strong_store, _ = _make_store(monkeypatch, consistency="strong")
    default_store, _ = _make_store(monkeypatch)

    etag_options = etag_store._build_state_options()
    strong_options = strong_store._build_state_options()

    assert etag_options is not None
    assert etag_options.concurrency.name == "first_write"
    assert strong_options is not None
    assert strong_options.concurrency.name == "unspecified"
    assert strong_options.consistency.name == "strong"
    assert default_store._build_state_options() is None


def test_is_etag_mismatch_handles_expected_grpc_variants() -> None:
    assert DaprStateBlackboardStore._is_etag_mismatch(_FakeError(StatusCode.ABORTED))
    assert DaprStateBlackboardStore._is_etag_mismatch(
        _FakeError(StatusCode.FAILED_PRECONDITION, details="ETag conflict")
    )
    assert not DaprStateBlackboardStore._is_etag_mismatch(
        _FakeError(StatusCode.FAILED_PRECONDITION, details="other")
    )
    assert not DaprStateBlackboardStore._is_etag_mismatch(RuntimeError("boom"))


async def test_retry_on_etag_conflict_retries_then_succeeds(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch, supports_etag=True, etag_max_retries=3)

    attempts = {"count": 0}

    def _operation() -> None:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise _FakeError(StatusCode.ABORTED)

    sleeps: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(
        "flock.storage.dapr.dapr_state_blackboard_store.asyncio.sleep", _fake_sleep
    )

    await store._retry_on_etag_conflict(_operation)

    assert attempts["count"] == 3
    assert sleeps == [0.1, 0.2]


async def test_retry_on_etag_conflict_raises_after_max_retries(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch, supports_etag=True, etag_max_retries=2)

    def _operation() -> None:
        raise _FakeError(StatusCode.ABORTED)

    async def _fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        "flock.storage.dapr.dapr_state_blackboard_store.asyncio.sleep", _fake_sleep
    )

    try:
        await store._retry_on_etag_conflict(_operation)
    except _FakeError as err:
        assert err.code() == StatusCode.ABORTED
    else:
        raise AssertionError("Expected _FakeError to be raised")


def test_exported_package_lazy_getattr_and_missing_symbol() -> None:
    import flock.storage.dapr as dapr_pkg

    assert dapr_pkg.serialize_index(["a"]) == '["a"]'

    try:
        _ = dapr_pkg.DOES_NOT_EXIST
    except AttributeError as err:
        assert "has no attribute" in str(err)
    else:
        raise AssertionError("Expected AttributeError for unknown export")


async def test_publish_dispatches_by_transaction_flag(monkeypatch) -> None:
    tx_store, _ = _make_store(monkeypatch, supports_transactions=True)
    non_tx_store, _ = _make_store(monkeypatch, supports_transactions=False)

    calls: list[str] = []

    async def _tx(_artifact: Artifact) -> None:
        calls.append("tx")

    async def _non_tx(_artifact: Artifact) -> None:
        calls.append("non-tx")

    monkeypatch.setattr(tx_store, "_publish_transactional", _tx)
    monkeypatch.setattr(tx_store, "_publish_non_transactional", _non_tx)
    monkeypatch.setattr(non_tx_store, "_publish_transactional", _tx)
    monkeypatch.setattr(non_tx_store, "_publish_non_transactional", _non_tx)

    artifact = Artifact(type="demo.Type", payload={"v": 1}, produced_by="agent")
    await tx_store.publish(artifact)
    await non_tx_store.publish(artifact)

    assert calls == ["tx", "non-tx"]


async def test_query_backend_dispatches_to_expected_strategy(monkeypatch) -> None:
    query_store, _ = _make_store(monkeypatch, supports_dapr_query_lang=True)
    scan_store, _ = _make_store(monkeypatch, supports_dapr_query_lang=False)
    encrypted_store, _ = _make_store(
        monkeypatch,
        supports_dapr_query_lang=True,
        encrypted_backend=True,
    )

    async def _query(_filters):
        return [Artifact(type="from-query", payload={}, produced_by="q")]

    def _scan(_filters):
        return [Artifact(type="from-scan", payload={}, produced_by="s")]

    monkeypatch.setattr(query_store, "_query_via_dapr_api", _query)
    monkeypatch.setattr(query_store, "_query_via_index_scan", _scan)
    monkeypatch.setattr(scan_store, "_query_via_dapr_api", _query)
    monkeypatch.setattr(scan_store, "_query_via_index_scan", _scan)
    monkeypatch.setattr(encrypted_store, "_query_via_dapr_api", _query)
    monkeypatch.setattr(encrypted_store, "_query_via_index_scan", _scan)

    assert (await query_store._query_backend())[0].type == "from-query"
    assert (await scan_store._query_backend())[0].type == "from-scan"
    assert (await encrypted_store._query_backend())[0].type == "from-scan"


async def test_query_artifacts_paginates_and_embeds_meta(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    artifacts = [
        Artifact(
            type="T",
            payload={"i": 2},
            produced_by="a",
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        Artifact(
            type="T",
            payload={"i": 1},
            produced_by="a",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    ]
    first_page_id = artifacts[1].id
    rec = ConsumptionRecord(
        artifact_id=first_page_id,
        consumer="consumer",
        consumed_at=datetime(2026, 1, 5, tzinfo=UTC),
    )

    async def _backend(_filters):
        return artifacts

    async def _consumptions(*, artifact_ids):
        assert artifact_ids
        return {str(artifact_ids[0]): [rec]}

    monkeypatch.setattr(store, "_query_backend", _backend)
    monkeypatch.setattr(store, "_get_consumptions_by_artifact_ids", _consumptions)

    page, total = await store.query_artifacts(limit=1, offset=0, embed_meta=True)

    assert total == 2
    assert len(page) == 1
    assert isinstance(page[0], ArtifactEnvelope)
    assert page[0].artifact.payload["i"] == 1
    assert page[0].consumptions == [rec]


async def test_fetch_graph_artifacts_wraps_plain_artifacts(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    artifact = Artifact(type="T", payload={"x": 1}, produced_by="agent")

    async def _query(**_kwargs):
        return ([artifact], 1)

    monkeypatch.setattr(store, "query_artifacts", _query)

    envelopes, total = await store.fetch_graph_artifacts()

    assert total == 1
    assert len(envelopes) == 1
    assert envelopes[0].artifact == artifact


async def test_summarize_artifacts_delegates_to_aggregator(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    artifact = Artifact(type="T", payload={"x": 1}, produced_by="agent")

    async def _query(**_kwargs):
        return ([artifact], 1)

    monkeypatch.setattr(store, "query_artifacts", _query)
    monkeypatch.setattr(
        store._aggregator,
        "build_summary",
        lambda artifacts, total, full_window: {
            "total": total,
            "full_window": full_window,
            "types": [a.type for a in artifacts],
        },
    )

    result = await store.summarize_artifacts()

    assert result == {"total": 1, "full_window": True, "types": ["T"]}


async def test_agent_history_summary_delegates_to_history_aggregator(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch)
    envelope = ArtifactEnvelope(
        artifact=Artifact(type="T", payload={}, produced_by="agent"),
    )

    async def _query(**_kwargs):
        return ([envelope], 1)

    monkeypatch.setattr(store, "query_artifacts", _query)
    monkeypatch.setattr(
        store._history_aggregator,
        "aggregate",
        lambda envelopes, agent_id: {
            "agent_id": agent_id,
            "count": len(envelopes),
        },
    )

    result = await store.agent_history_summary("agent-1")

    assert result == {"agent_id": "agent-1", "count": 1}


async def test_get_returns_none_for_missing_artifact(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    missing_id = uuid4()
    monkeypatch.setattr(
        store._client,
        "get_state",
        lambda _store, _key: _FakeStateResponse(""),
        raising=False,
    )

    result = await store.get(missing_id)

    assert result is None


async def test_get_returns_deserialized_artifact(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    artifact = Artifact(type="T", payload={"a": 1}, produced_by="agent")
    monkeypatch.setattr(
        store._client,
        "get_state",
        lambda _store, _key: _FakeStateResponse(artifact.model_dump_json()),
        raising=False,
    )

    result = await store.get(artifact.id)

    assert result is not None
    assert result.id == artifact.id
    assert result.payload == {"a": 1}


async def test_list_reads_bulk_and_reconciles_index(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    artifact = Artifact(type="T", payload={"x": 1}, produced_by="agent")
    stale_id = str(uuid4())
    monkeypatch.setattr(
        store, "_read_index", lambda _k: ([str(artifact.id), stale_id], "etag-1")
    )

    calls: dict[str, object] = {}

    def _reconcile(index_key, index_ids, live_keys, *, etag=None):
        calls["index_key"] = index_key
        calls["index_ids"] = index_ids
        calls["live_keys"] = live_keys
        calls["etag"] = etag
        return [str(artifact.id)]

    monkeypatch.setattr(store, "_reconcile_index", _reconcile)
    monkeypatch.setattr(
        store._client,
        "get_bulk_state",
        lambda _store, _keys: SimpleNamespace(
            items=[
                _FakeBulkItem(f"artifact:{artifact.id}", artifact.model_dump_json()),
                _FakeBulkItem(f"artifact:{stale_id}", ""),
            ]
        ),
        raising=False,
    )

    result = await store.list()

    assert [a.id for a in result] == [artifact.id]
    assert calls["etag"] == "etag-1"
    assert calls["live_keys"] == {str(artifact.id)}


async def test_list_by_type_returns_empty_when_index_empty(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    monkeypatch.setattr(store, "_read_index", lambda _k: ([], "etag-0"))

    result = await store.list_by_type("T")

    assert result == []


async def test_get_by_type_casts_and_filters_correlation(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)

    class DemoModel(BaseModel):
        value: int

    matching = Artifact(
        type="DemoModel",
        payload={"value": 10},
        produced_by="agent",
        correlation_id="corr-1",
    )
    other = Artifact(
        type="DemoModel",
        payload={"value": 20},
        produced_by="agent",
        correlation_id="corr-2",
    )

    async def _list_by_type(_type):
        return [matching, other]

    monkeypatch.setattr(store, "list_by_type", _list_by_type)

    result = await store.get_by_type(DemoModel, correlation_id="corr-1")

    assert len(result) == 1
    assert isinstance(result[0], DemoModel)
    assert result[0].value == 10


async def test_record_consumptions_dispatches_by_transaction_flag(monkeypatch) -> None:
    tx_store, _ = _make_store(monkeypatch, supports_transactions=True)
    non_tx_store, _ = _make_store(monkeypatch, supports_transactions=False)
    calls: list[str] = []

    async def _tx(*, records):
        assert records
        calls.append("tx")

    async def _non_tx(*, records):
        assert records
        calls.append("non-tx")

    monkeypatch.setattr(tx_store, "_record_consumptions_transactional", _tx)
    monkeypatch.setattr(tx_store, "_record_consumptions_non_transactional", _non_tx)
    monkeypatch.setattr(non_tx_store, "_record_consumptions_transactional", _tx)
    monkeypatch.setattr(non_tx_store, "_record_consumptions_non_transactional", _non_tx)

    rec = ConsumptionRecord(artifact_id=uuid4(), consumer="agent")
    await tx_store.record_consumptions([rec])
    await non_tx_store.record_consumptions([rec])

    assert calls == ["tx", "non-tx"]


async def test_upsert_and_clear_snapshot_dispatches(monkeypatch) -> None:
    tx_store, _ = _make_store(monkeypatch, supports_transactions=True)
    non_tx_store, _ = _make_store(monkeypatch, supports_transactions=False)
    calls: list[str] = []

    async def _tx_upsert(_snapshot):
        calls.append("tx-upsert")

    async def _non_tx_upsert(_snapshot):
        calls.append("non-tx-upsert")

    async def _tx_clear():
        calls.append("tx-clear")

    async def _non_tx_clear():
        calls.append("non-tx-clear")

    monkeypatch.setattr(tx_store, "_upsert_agent_snapshot_transactional", _tx_upsert)
    monkeypatch.setattr(
        tx_store, "_upsert_agent_snapshot_non_transactional", _non_tx_upsert
    )
    monkeypatch.setattr(
        non_tx_store, "_upsert_agent_snapshot_transactional", _tx_upsert
    )
    monkeypatch.setattr(
        non_tx_store, "_upsert_agent_snapshot_non_transactional", _non_tx_upsert
    )

    monkeypatch.setattr(tx_store, "_clear_agent_snapshots_transactional", _tx_clear)
    monkeypatch.setattr(
        tx_store, "_clear_agent_snapshots_non_transactional", _non_tx_clear
    )
    monkeypatch.setattr(non_tx_store, "_clear_agent_snapshots_transactional", _tx_clear)
    monkeypatch.setattr(
        non_tx_store, "_clear_agent_snapshots_non_transactional", _non_tx_clear
    )

    snapshot = AgentSnapshotRecord(
        agent_name="agent",
        description="desc",
        subscriptions=["A"],
        output_types=["B"],
        labels=["l"],
        first_seen=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen=datetime(2026, 1, 2, tzinfo=UTC),
        signature="sig",
    )

    await tx_store.upsert_agent_snapshot(snapshot)
    await non_tx_store.upsert_agent_snapshot(snapshot)
    await tx_store.clear_agent_snapshots()
    await non_tx_store.clear_agent_snapshots()

    assert calls == ["tx-upsert", "non-tx-upsert", "tx-clear", "non-tx-clear"]


async def test_load_agent_snapshots_handles_error_empty_and_valid_entries(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch)
    snapshot = AgentSnapshotRecord(
        agent_name="agent-ok",
        description="desc",
        subscriptions=["A"],
        output_types=["B"],
        labels=["l"],
        first_seen=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen=datetime(2026, 1, 2, tzinfo=UTC),
        signature="sig",
    )

    monkeypatch.setattr(
        store, "_read_index", lambda _k: (["bad", "empty", "agent-ok"], "etag-snap")
    )

    reconcile_calls: dict[str, object] = {}

    def _reconcile(index_key, index_ids, live_keys, *, etag=None):
        reconcile_calls["index_key"] = index_key
        reconcile_calls["ids"] = index_ids
        reconcile_calls["live"] = live_keys
        reconcile_calls["etag"] = etag
        return ["agent-ok"]

    monkeypatch.setattr(store, "_reconcile_index", _reconcile)
    monkeypatch.setattr(
        store._client,
        "get_bulk_state",
        lambda _store, keys, parallelism=10: SimpleNamespace(
            items=[
                _FakeBulkItem("snapshot:bad", "", error="boom"),
                _FakeBulkItem("snapshot:empty", ""),
                _FakeBulkItem("snapshot:agent-ok", serialize_agent_snapshot(snapshot)),
            ]
        ),
        raising=False,
    )

    result = await store.load_agent_snapshots()

    assert len(result) == 1
    assert result[0].agent_name == "agent-ok"
    assert reconcile_calls["live"] == {"agent-ok"}
    assert reconcile_calls["etag"] == "etag-snap"
