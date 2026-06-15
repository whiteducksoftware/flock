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


def test_read_and_write_index_use_etag_and_state_options(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch, supports_etag=True, consistency="strong")

    monkeypatch.setattr(
        store._client,
        "get_state",
        lambda _store, _key: _FakeStateResponse('["a"]', etag="etag-read"),
        raising=False,
    )

    save_call: dict[str, object] = {}

    def _save_state(_store, key, value, **kwargs):
        save_call["key"] = key
        save_call["value"] = value
        save_call.update(kwargs)

    monkeypatch.setattr(store._client, "save_state", _save_state, raising=False)

    items, etag = store._read_index("idx:key")
    store._write_index("idx:key", ["x"], etag="etag-write")

    assert items == ["a"]
    assert etag == "etag-read"
    assert save_call["key"] == "idx:key"
    assert save_call["value"] == '["x"]'
    assert save_call["etag"] == "etag-write"
    assert save_call["state_metadata"] == {}
    assert save_call["options"] is not None


def test_reconcile_index_without_stale_entries_does_not_write(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    called = {"count": 0}

    def _write(*_args, **_kwargs):
        called["count"] += 1

    monkeypatch.setattr(store, "_write_index", _write)

    result = store._reconcile_index("idx:test", ["a", "b"], {"a", "b"})

    assert result == ["a", "b"]
    assert called["count"] == 0


async def test_query_via_dapr_api_handles_pagination_errors_and_tag_filter(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch)

    keep = Artifact(
        type="Demo",
        payload={"x": 1},
        produced_by="writer",
        tags={"keep", "extra"},
    )
    drop = Artifact(
        type="Demo",
        payload={"x": 2},
        produced_by="writer",
        tags={"other"},
    )

    class _QueryItem:
        def __init__(self, key: str, data: str, error: str | None = None) -> None:
            self.key = key
            self._data = data
            self.error = error

        def text(self) -> str:
            return self._data

    class _QueryResponse:
        def __init__(self, results, token: str | None) -> None:
            self.results = results
            self.token = token

    calls: list[str] = []

    def _query_state(*, store_name: str, query: str):
        calls.append(query)
        if len(calls) == 1:
            return _QueryResponse(
                [
                    _QueryItem("bad", "", error="boom"),
                    _QueryItem("non-artifact", "not-json"),
                    _QueryItem("artifact-1", keep.model_dump_json()),
                ],
                token="next-token",
            )
        return _QueryResponse([_QueryItem("artifact-2", drop.model_dump_json())], None)

    monkeypatch.setattr(store._client, "query_state", _query_state, raising=False)

    artifacts = await store._query_via_dapr_api(FilterConfig(tags={"keep"}))

    assert [a.id for a in artifacts] == [keep.id]
    assert len(calls) == 2
    assert '"token": "next-token"' in calls[1]


def test_query_via_index_scan_type_filters_and_reconcile_paths(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    artifact = Artifact(type="Demo", payload={"v": 1}, produced_by="writer")

    class _AlwaysMatch:
        def __init__(self, _filters) -> None:
            pass

        def matches(self, _artifact: Artifact) -> bool:
            return True

    monkeypatch.setattr(
        "flock.storage.dapr.dapr_state_blackboard_store.ArtifactFilter",
        _AlwaysMatch,
    )

    def _read_index(key: str):
        if key == _type_index_key("A"):
            return ([str(artifact.id)], "etag-a")
        if key == _type_index_key("B"):
            return ([str(uuid4())], "etag-b")
        return ([], None)

    monkeypatch.setattr(store, "_read_index", _read_index)

    monkeypatch.setattr(
        store._client,
        "get_bulk_state",
        lambda _store, _keys, parallelism=10: SimpleNamespace(
            items=[
                _FakeBulkItem(f"artifact:{artifact.id}", artifact.model_dump_json()),
                _FakeBulkItem(f"artifact:{uuid4()}", "not-json"),
            ]
        ),
        raising=False,
    )

    reconciled: list[tuple[str, list[str], set[str], str | None]] = []

    def _reconcile(index_key, index_ids, live_keys, *, etag=None):
        reconciled.append((index_key, index_ids, live_keys, etag))
        return [str(artifact.id)]

    monkeypatch.setattr(store, "_reconcile_index", _reconcile)

    result = store._query_via_index_scan(FilterConfig(type_names={"A", "B"}))

    assert [a.id for a in result] == [artifact.id]
    assert len(reconciled) == 2
    assert {row[0] for row in reconciled} == {
        _type_index_key("A"),
        _type_index_key("B"),
    }
    assert all(str(artifact.id) in row[2] for row in reconciled)


async def test_get_consumptions_by_artifact_ids_skips_error_entries(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch)
    artifact_id = uuid4()

    monkeypatch.setattr(
        store._client,
        "get_bulk_state",
        lambda store_name, keys, parallelism=10: SimpleNamespace(
            items=[
                _FakeBulkItem(f"consumptions:{artifact_id}", "[]"),
                _FakeBulkItem("consumptions:bad", "[]", error="oops"),
            ]
        ),
        raising=False,
    )

    result = await store._get_consumptions_by_artifact_ids([artifact_id])

    assert result == {str(artifact_id): []}


async def test_publish_transactional_writes_artifact_and_index_updates(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch, supports_transactions=True, supports_etag=True)
    artifact = Artifact(type="Demo", payload={"x": 1}, produced_by="writer")

    def _read_index(key: str):
        if key == "idx:artifacts":
            return ([], "etag-all")
        return ([], "etag-type")

    monkeypatch.setattr(store, "_read_index", _read_index)

    save_calls: list[dict[str, object]] = []

    def _save_state(_store, key, value, **kwargs):
        save_calls.append({"key": key, "value": value, **kwargs})

    tx_calls: dict[str, object] = {}

    def _execute_state_transaction(*, store_name, operations):
        tx_calls["store_name"] = store_name
        tx_calls["operations"] = operations

    monkeypatch.setattr(store._client, "save_state", _save_state, raising=False)
    monkeypatch.setattr(
        store._client,
        "execute_state_transaction",
        _execute_state_transaction,
        raising=False,
    )

    await store._publish_transactional(artifact)

    assert len(save_calls) == 1
    assert save_calls[0]["key"] == f"artifact:{artifact.id}"
    operations = tx_calls["operations"]
    assert len(operations) == 2
    assert {op.key for op in operations} == {"idx:artifacts", "idx:type:Demo"}


async def test_record_consumptions_non_transactional_groups_and_saves_bulk(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch, supports_etag=True)
    artifact_id = uuid4()
    existing = ConsumptionRecord(artifact_id=artifact_id, consumer="existing")
    new_record = ConsumptionRecord(artifact_id=artifact_id, consumer="new")

    monkeypatch.setattr(
        store._client,
        "get_state",
        lambda _store, _key: _FakeStateResponse(
            json.dumps([
                {
                    "artifact_id": str(existing.artifact_id),
                    "consumer": existing.consumer,
                    "run_id": existing.run_id,
                    "correlation_id": existing.correlation_id,
                    "consumed_at": existing.consumed_at.isoformat(),
                }
            ]),
            etag="etag-cons",
        ),
        raising=False,
    )

    captured: dict[str, object] = {}

    def _save_bulk_state(*, store_name, states):
        captured["store_name"] = store_name
        captured["states"] = states

    monkeypatch.setattr(
        store._client, "save_bulk_state", _save_bulk_state, raising=False
    )

    await store._record_consumptions_non_transactional([new_record])

    states = captured["states"]
    assert len(states) == 1
    payload = json.loads(states[0].value)
    assert len(payload) == 2
    assert {entry["consumer"] for entry in payload} == {"existing", "new"}


def test_build_dapr_query_single_producer_and_visibility_paths() -> None:
    query = json.loads(
        _build_dapr_query(
            FilterConfig(
                produced_by={"solo-producer"},
                visibility={"Public"},
            )
        )
    )

    and_conditions = query["filter"]["AND"]
    assert {"EQ": {"produced_by": "solo-producer"}} in and_conditions
    assert {"EQ": {"visibility.kind": "Public"}} in and_conditions


def test_store_initializes_eventual_consistency_branch(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch, consistency="eventual")

    assert store._consistency.name == "unspecified"


async def test_retry_on_etag_conflict_re_raises_non_etag_errors(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch, supports_etag=True, etag_max_retries=3)

    async def _sleep_should_not_be_called(_delay: float) -> None:
        raise AssertionError("sleep should not be called for non-etag errors")

    monkeypatch.setattr(
        "flock.storage.dapr.dapr_state_blackboard_store.asyncio.sleep",
        _sleep_should_not_be_called,
    )

    def _operation() -> None:
        raise RuntimeError("not an etag conflict")

    try:
        await store._retry_on_etag_conflict(_operation)
    except RuntimeError as err:
        assert "not an etag conflict" in str(err)
    else:
        raise AssertionError("Expected RuntimeError to be raised")


def test_reconcile_index_with_stale_entries_writes_cleaned_index(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    write_calls: list[tuple[str, list[str], str | None]] = []

    def _write(index_key: str, items: list[str], *, etag: str | None = None) -> None:
        write_calls.append((index_key, items, etag))

    monkeypatch.setattr(store, "_write_index", _write)

    cleaned = store._reconcile_index(
        "idx:artifacts",
        ["live-1", "stale-1", "live-2"],
        {"live-1", "live-2"},
        etag="etag-reconcile",
    )

    assert cleaned == ["live-1", "live-2"]
    assert write_calls == [("idx:artifacts", ["live-1", "live-2"], "etag-reconcile")]


async def test_publish_non_transactional_persists_and_updates_indexes(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch, supports_etag=True, supports_ttl=True)
    artifact = Artifact(type="Demo", payload={"x": 1}, produced_by="writer")

    save_calls: list[dict[str, object]] = []
    index_writes: list[tuple[str, list[str], str | None]] = []

    def _read_index(key: str):
        if key == "idx:artifacts":
            return ([], "etag-all")
        if key == "idx:type:Demo":
            return ([], "etag-type")
        raise AssertionError(f"Unexpected index key {key}")

    def _save_state(_store, key, value, **kwargs):
        save_calls.append({"key": key, "value": value, **kwargs})

    def _write_index(key: str, items: list[str], *, etag: str | None = None) -> None:
        index_writes.append((key, items, etag))

    monkeypatch.setattr(store, "_read_index", _read_index)
    monkeypatch.setattr(store._client, "save_state", _save_state, raising=False)
    monkeypatch.setattr(store, "_write_index", _write_index)

    await store._publish_non_transactional(artifact)

    assert len(save_calls) == 1
    assert save_calls[0]["key"] == f"artifact:{artifact.id}"
    assert {w[0] for w in index_writes} == {"idx:artifacts", "idx:type:Demo"}
    assert all(str(artifact.id) in w[1] for w in index_writes)


async def test_record_consumptions_transactional_groups_and_transacts(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch, supports_etag=True)
    first_id = uuid4()
    second_id = uuid4()
    records = [
        ConsumptionRecord(artifact_id=first_id, consumer="a"),
        ConsumptionRecord(artifact_id=first_id, consumer="b"),
        ConsumptionRecord(artifact_id=second_id, consumer="c"),
    ]

    def _get_state(_store, key: str):
        if key.endswith(str(first_id)):
            return _FakeStateResponse("[]", etag="etag-first")
        if key.endswith(str(second_id)):
            return _FakeStateResponse("[]", etag="etag-second")
        return _FakeStateResponse("[]")

    tx_call: dict[str, object] = {}

    def _execute_state_transaction(*, store_name, operations):
        tx_call["store_name"] = store_name
        tx_call["operations"] = operations

    monkeypatch.setattr(store._client, "get_state", _get_state, raising=False)
    monkeypatch.setattr(
        store._client,
        "execute_state_transaction",
        _execute_state_transaction,
        raising=False,
    )

    await store._record_consumptions_transactional(records)

    operations = tx_call["operations"]
    assert len(operations) == 2
    assert {op.key for op in operations} == {
        f"consumptions:{first_id}",
        f"consumptions:{second_id}",
    }


async def test_upsert_agent_snapshot_transactional_builds_operations(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch, supports_etag=True)
    snapshot = AgentSnapshotRecord(
        agent_name="agent-a",
        description="desc",
        subscriptions=["Input"],
        output_types=["Output"],
        labels=["label"],
        first_seen=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen=datetime(2026, 1, 2, tzinfo=UTC),
        signature="sig-a",
    )

    monkeypatch.setattr(
        store._client,
        "get_state",
        lambda _store, _key: _FakeStateResponse("", etag="etag-snap"),
        raising=False,
    )
    monkeypatch.setattr(store, "_read_index", lambda _k: ([], "etag-idx"))

    tx_call: dict[str, object] = {}

    def _execute_state_transaction(*, store_name, operations):
        tx_call["store_name"] = store_name
        tx_call["operations"] = operations

    monkeypatch.setattr(
        store._client,
        "execute_state_transaction",
        _execute_state_transaction,
        raising=False,
    )

    await store._upsert_agent_snapshot_transactional(snapshot)

    operations = tx_call["operations"]
    assert len(operations) == 2
    assert {op.key for op in operations} == {
        "snapshot:agent-a",
        "idx:snapshots",
    }


async def test_upsert_agent_snapshot_non_transactional_reads_etag_and_updates_index(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch, supports_etag=True)
    snapshot = AgentSnapshotRecord(
        agent_name="agent-b",
        description="desc",
        subscriptions=["Input"],
        output_types=["Output"],
        labels=["label"],
        first_seen=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen=datetime(2026, 1, 2, tzinfo=UTC),
        signature="sig-b",
    )

    monkeypatch.setattr(
        store._client,
        "get_state",
        lambda _store, _key: _FakeStateResponse("", etag="etag-existing"),
        raising=False,
    )
    monkeypatch.setattr(store, "_read_index", lambda _k: ([], "etag-idx"))

    save_calls: list[dict[str, object]] = []
    index_writes: list[tuple[str, list[str], str | None]] = []

    def _save_state(_store, key, value, **kwargs):
        save_calls.append({"key": key, "value": value, **kwargs})

    def _write_index(key: str, items: list[str], *, etag: str | None = None) -> None:
        index_writes.append((key, items, etag))

    monkeypatch.setattr(store._client, "save_state", _save_state, raising=False)
    monkeypatch.setattr(store, "_write_index", _write_index)

    await store._upsert_agent_snapshot_non_transactional(snapshot)

    assert len(save_calls) == 1
    assert save_calls[0]["etag"] == "etag-existing"
    assert index_writes == [("idx:snapshots", ["agent-b"], "etag-idx")]


async def test_clear_agent_snapshots_transactional_deletes_all_and_index(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch)
    monkeypatch.setattr(store, "_read_index", lambda _k: (["a", "b"], "etag-idx"))

    tx_call: dict[str, object] = {}

    def _execute_state_transaction(*, store_name, operations):
        tx_call["store_name"] = store_name
        tx_call["operations"] = operations

    monkeypatch.setattr(
        store._client,
        "execute_state_transaction",
        _execute_state_transaction,
        raising=False,
    )

    await store._clear_agent_snapshots_transactional()

    operations = tx_call["operations"]
    assert len(operations) == 3
    assert {op.key for op in operations} == {
        "snapshot:a",
        "snapshot:b",
        "idx:snapshots",
    }


async def test_clear_agent_snapshots_non_transactional_deletes_and_resets_index(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch)
    monkeypatch.setattr(store, "_read_index", lambda _k: (["a", "b"], "etag-idx"))

    deleted_keys: list[str] = []
    wrote_index: list[tuple[str, list[str], str | None]] = []

    def _delete_state(_store, *, key, options=None):
        _ = options
        deleted_keys.append(key)

    def _write_index(key: str, items: list[str], *, etag: str | None = None) -> None:
        wrote_index.append((key, items, etag))

    monkeypatch.setattr(store._client, "delete_state", _delete_state, raising=False)
    monkeypatch.setattr(store, "_write_index", _write_index)

    await store._clear_agent_snapshots_non_transactional()

    assert deleted_keys == ["snapshot:a", "snapshot:b"]
    assert wrote_index == [("idx:snapshots", [], "etag-idx")]


async def test_list_returns_empty_when_index_empty(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    monkeypatch.setattr(store, "_read_index", lambda _k: ([], "etag-none"))

    result = await store.list()

    assert result == []


async def test_list_by_type_reads_bulk_and_reconciles_non_empty_index(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch)
    artifact = Artifact(type="Demo", payload={"v": 1}, produced_by="writer")
    stale_id = str(uuid4())
    monkeypatch.setattr(
        store, "_read_index", lambda _k: ([str(artifact.id), stale_id], "etag-type")
    )

    reconcile_calls: dict[str, object] = {}

    def _reconcile(index_key, index_ids, live_keys, *, etag=None):
        reconcile_calls["index_key"] = index_key
        reconcile_calls["index_ids"] = index_ids
        reconcile_calls["live_keys"] = live_keys
        reconcile_calls["etag"] = etag
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

    result = await store.list_by_type("Demo")

    assert [a.id for a in result] == [artifact.id]
    assert reconcile_calls["index_key"] == "idx:type:Demo"
    assert reconcile_calls["etag"] == "etag-type"
    assert reconcile_calls["live_keys"] == {str(artifact.id)}


async def test_query_artifacts_limit_zero_and_without_meta(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    artifacts = [
        Artifact(type="T", payload={"i": 2}, produced_by="a"),
        Artifact(type="T", payload={"i": 1}, produced_by="a"),
    ]

    async def _backend(_filters):
        return artifacts

    monkeypatch.setattr(store, "_query_backend", _backend)

    page, total = await store.query_artifacts(limit=0, offset=0, embed_meta=False)

    assert total == 2
    assert len(page) == 2
    assert all(isinstance(item, Artifact) for item in page)


async def test_fetch_graph_artifacts_keeps_existing_envelopes(monkeypatch) -> None:
    store, _ = _make_store(monkeypatch)
    envelope = ArtifactEnvelope(
        artifact=Artifact(type="T", payload={"x": 1}, produced_by="agent")
    )

    async def _query(**_kwargs):
        return ([envelope], 1)

    monkeypatch.setattr(store, "query_artifacts", _query)

    envelopes, total = await store.fetch_graph_artifacts()

    assert total == 1
    assert envelopes == [envelope]


async def test_summarize_artifacts_raises_type_error_for_non_artifact_items(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch)
    envelope = ArtifactEnvelope(
        artifact=Artifact(type="T", payload={}, produced_by="agent")
    )

    async def _query(**_kwargs):
        return ([envelope], 1)

    monkeypatch.setattr(store, "query_artifacts", _query)

    try:
        await store.summarize_artifacts()
    except TypeError as err:
        assert "Expected Artifact instance" in str(err)
    else:
        raise AssertionError("Expected TypeError to be raised")


async def test_load_agent_snapshots_returns_empty_when_index_is_empty(
    monkeypatch,
) -> None:
    store, _ = _make_store(monkeypatch)
    monkeypatch.setattr(store, "_read_index", lambda _k: ([], "etag-empty"))

    result = await store.load_agent_snapshots()

    assert result == []
