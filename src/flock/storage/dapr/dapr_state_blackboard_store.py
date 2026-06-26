"""Dapr-Backed Blackboar Store.

Utilizes Dapr State-Store Components
as the backend for the Flock Blackboard.
"""

from __future__ import annotations

import asyncio
import atexit
import json
from asyncio import Lock
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal, TypeVar
from uuid import UUID

from dapr.clients.grpc._request import (
    TransactionalStateOperation,
    TransactionOperationType,
)
from dapr.clients.grpc._state import Concurrency, Consistency, StateItem, StateOptions
from grpc import (
    StatusCode,
    StreamStreamClientInterceptor,
    StreamUnaryClientInterceptor,
    UnaryStreamClientInterceptor,
    UnaryUnaryClientInterceptor,
)
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flock.core.artifacts import Artifact
from flock.core.store import (
    AgentSnapshotRecord,
    ArtifactEnvelope,
    BlackboardStore,
    ConsumptionRecord,
    FilterConfig,
)
from flock.logging import get_logger
from flock.registry import type_registry
from flock.storage.artifact_aggregator import ArtifactAggregator
from flock.storage.dapr import (
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
from flock.storage.in_memory.artifact_filter import ArtifactFilter
from flock.storage.in_memory.history_aggregator import HistoryAggregator
from flock.utils.type_resolution import TypeResolutionHelper


if TYPE_CHECKING:
    from dapr.clients.grpc._response import (
        BulkStatesResponse,
        QueryResponse,
    )


T = TypeVar("T")
tracer = trace.get_tracer(__name__)
logger = get_logger(__name__)
registry = type_registry

# ── Key-naming conventions ───────────────────────────────────────────
#
#   artifact:{uuid}            → serialised Artifact (JSON)
#   idx:artifacts              → JSON list of all artifact UUID strings
#   idx:type:{type_name}       → JSON list of UUID strings for that type
#   consumptions:{artifact_id} → JSON list of ConsumptionRecord dicts
#   snapshot:{agent_name}      → serialised AgentSnapshotRecord (JSON)
#   idx:snapshots              → JSON list of agent name strings
#
# Indexes are maintained manually via read-modify-write.  For stores
# that support transactions (Redis, PostgreSQL, CosmosDB) the artifact
# write and the index update should be wrapped in
# ``execute_state_transaction`` to guarantee atomicity.
# ─────────────────────────────────────────────────────────────────────

_IDX_ALL_ARTIFACTS = "idx:artifacts"
_IDX_SNAPSHOTS = "idx:snapshots"


def _artifact_key(artifact_id: UUID) -> str:
    return f"artifact:{artifact_id}"


def _type_index_key(type_name: str) -> str:
    return f"idx:type:{type_name}"


def _consumptions_key(artifact_id: UUID) -> str:
    return f"consumptions:{artifact_id}"


def _snapshot_key(agent_name: str) -> str:
    return f"snapshot:{agent_name}"


def _build_dapr_query(filters: FilterConfig | None) -> str:
    """Convert a :class:`FilterConfig` into a Dapr state query JSON string.

    Tags are excluded because the Dapr query language cannot express
    set-membership checks against JSON arrays; they must be post-filtered.
    """
    conditions: list[dict[str, Any]] = []
    if filters:
        if filters.type_names:
            names = sorted(filters.type_names)
            if len(names) == 1:
                conditions.append({"EQ": {"type": names[0]}})
            else:
                conditions.append({"IN": {"type": names}})
        if filters.produced_by:
            producers = sorted(filters.produced_by)
            if len(producers) == 1:
                conditions.append({"EQ": {"produced_by": producers[0]}})
            else:
                conditions.append({"IN": {"produced_by": producers}})
        if filters.correlation_id:
            conditions.append({"EQ": {"correlation_id": filters.correlation_id}})
        if filters.visibility:
            kinds = sorted(filters.visibility)
            if len(kinds) == 1:
                conditions.append({"EQ": {"visibility.kind": kinds[0]}})
            else:
                conditions.append({"IN": {"visibility.kind": kinds}})
        if filters.start:
            conditions.append({"GTE": {"created_at": filters.start.isoformat()}})
        if filters.end:
            conditions.append({"LTE": {"created_at": filters.end.isoformat()}})

    query: dict[str, Any] = {}
    if len(conditions) == 1:
        query["filter"] = conditions[0]
    elif len(conditions) > 1:
        query["filter"] = {"AND": conditions}
    query["sort"] = [{"key": "created_at", "order": "ASC"}]
    return json.dumps(query)


class DaprStateBlackboardStoreClientConfig(BaseModel):
    """Optional Config for the underlying Dapr-Client for the Blackboard."""

    dapr_grpc_endpoint: str | None = Field(
        default=None, description="Dapr Runtime gRPC endpoint address. Optional."
    )
    headers_callback: Callable[[], dict[str, str]] | None = Field(
        default=None,
        description="lambda: dict[str, str]. Optional. Generate headers for each request.",
    )
    interceptors: (
        list[
            UnaryUnaryClientInterceptor
            | UnaryStreamClientInterceptor
            | StreamUnaryClientInterceptor
            | StreamStreamClientInterceptor
        ]
        | None
    ) = Field(default=None, description="gRPC interceptors")
    http_timeout_seconds: int | None = Field(
        default=None,
        description="Specify a timeout for http-connections to the dapr-backend.",
    )
    max_grpc_message_length: int | None = Field(
        default=None,
    )

    retry_policy: Any | None = Field(default=None, description="Retry-Policy.")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DaprStateBlackboardConfig(BaseModel):
    """Configuration for a Dapr-Compatible BlackboardStore."""

    store_name: str = Field(
        default="statestore", description="Name of the state-store for the blackboard."
    )
    supports_ttl: bool = Field(
        default=False,
        description="Whether or not the underlying backend should implement TTL for entries. Only works if the backend really supports it! Otherwise, you will get errors",
    )
    encrypted_backend: bool = Field(
        default=False, description="Flag to indicate that the backend is encrypted."
    )
    backend_encryption_key: str | None = Field(
        default=None,
        description="Optional. Encryption key for the backend. Only used if `encrypted_backend`==True.",
    )
    supports_transactions: bool = Field(
        default=False,
        description="Whether or not the underlying backend is transactional. (strongly recommended. Examples are: Redis, CosmosDB, PostgresQL).",
    )

    supports_dapr_query_lang: bool = Field(
        default=False,
        description="If the configured backend supports dapr-queries. Optional.",
    )

    supports_etag: bool = Field(
        default=False,
        description="Enable optimistic concurrency control via Dapr ETags. "
        "When True, all read-modify-write operations pass the ETag received "
        "during the preceding read, using first-write-wins semantics. "
        "ETag mismatch retries are planned as follow-up hardening work.",
    )

    etag_max_retries: int = Field(
        default=3,
        description="Reserved for follow-up ETag conflict retry handling. "
        "Ignored by current write paths when supports_etag is False.",
        ge=0,
    )

    consistency: Literal["unspecified", "eventual", "strong"] = Field(
        default="unspecified",
        description="Consistency level for state operations. "
        "Use Consistency.strong for strong consistency or "
        "Consistency.eventual for eventual consistency. "
        "Defaults to Consistency.unspecified (backend default).",
    )

    entries_ttl_seconds: int | None = Field(
        default=None,
        description="Optional TTL in Seconds for entries in the underlying state-store.",
    )

    client_config: DaprStateBlackboardStoreClientConfig | None = Field(
        default=None,
        description="Optional Dapr Client configuration. If not provided, the client will be created using default Dapr-Settings.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _validate_config(self) -> DaprStateBlackboardConfig:
        if self.entries_ttl_seconds is not None and not self.supports_ttl:
            logger.warning(
                "entries_ttl_seconds is set but supports_ttl is False; "
                "TTL will not be applied to state entries."
            )
        if self.encrypted_backend and self.supports_transactions:
            logger.warning(
                "Encrypted backend with transactions is not supported due to a "
                "bug in the Dapr runtime's ExecuteStateTransaction handler "
                "(values are corrupted via Go's fmt.Appendf before encryption). "
                "Falling back to non-transactional operations."
            )
            self.supports_transactions = False
        return self


class DaprStateBlackboardStore(BlackboardStore):
    """Dapr-backed implementation of :class:`BlackboardStore`.

    Leverages Dapr State Management to persist artifacts, consumption
    records, and agent snapshots.  Works with any Dapr state-store
    component (Redis, PostgreSQL, CosmosDB, …).

    Args:
        store_name: The Dapr component name (``metadata.name`` in the
            component YAML).  Defaults to ``"statestore"``.

    .. warning:: **Encryption and transactions are mutually exclusive.**

       When the Dapr state-store component is configured with
       ``primaryEncryptionKey`` (i.e. ``encrypted_backend=True``), the
       ``supports_transactions`` flag is automatically forced to
       ``False``.  This is caused by a bug in the Dapr Go runtime
       (`ExecuteStateTransaction handler
       <https://github.com/dapr/dapr/blob/master/pkg/api/grpc/grpc.go>`_):
       before encrypting, it converts the raw ``[]byte`` value via
       ``fmt.Appendf(nil, "%v", req.Value)`` which produces a
       space-separated decimal representation (e.g.
       ``[91 34 102 ...]``) instead of the original bytes.  The
       ``SaveState`` / ``SaveBulkState`` handlers do **not** have this
       problem — they pass the raw bytes directly to encryption.

       As a consequence, all writes fall back to the non-transactional
       path (``save_state`` / ``save_bulk_state``) when encryption is
       enabled.  Index updates are therefore **not** atomic in this
       mode; however, stale index entries are reconciled lazily on read,
       so data consistency is maintained eventually.
    """

    def __init__(self, config: DaprStateBlackboardConfig) -> None:
        self._store_name = config.store_name
        client_config = config.client_config or DaprStateBlackboardStoreClientConfig()
        self._client = create_dapr_client(client_config)
        self._lock = Lock()
        self._supports_ttl = config.supports_ttl
        self._entries_ttl = config.entries_ttl_seconds
        self._encrypted_backend = config.encrypted_backend
        self._aggregator = ArtifactAggregator()
        self._history_aggregator = HistoryAggregator()
        self._supports_transactions = config.supports_transactions
        self._supports_dapr_query_lang = config.supports_dapr_query_lang
        self._supports_etag = config.supports_etag
        self._etag_max_retries = config.etag_max_retries
        if config.consistency == "eventual":
            self._consistency = Consistency.eventual
        elif config.consistency == "strong":
            self._consistency = Consistency.strong
        else:
            self._consistency = Consistency.unspecified
        # Register cleanup
        atexit.register(self.close)
        logger.info(
            f"{__name__} initialized (store={config.store_name}, ttl={config.entries_ttl_seconds}, encrypted={config.encrypted_backend}, transactions={config.supports_transactions}, etag={config.supports_etag}, consistency={config.consistency})"
        )

    def close(self) -> None:
        """Release the underlying gRPC channel."""
        logger.info("Closing Dapr-Client...")
        self._client.close()

    # ── helpers ──────────────────────────────────────────────────────
    def _create_state_metadata_for_save(self, key: str, *, ttl: int | None = None):
        """Create the metadata dict for entries."""
        metadata = {}
        if self._supports_ttl and ttl and ttl > 0:
            metadata["ttlInSeconds"] = str(ttl)
        logger.debug(f"Created metadata for entry {key}: {metadata}")
        return metadata

    def _build_state_options(self) -> StateOptions | None:
        """Build :class:`StateOptions` based on the current configuration.

        Returns ``StateOptions`` with ``concurrency=first_write`` when
        ETags are enabled, or with the configured ``consistency`` when
        it differs from ``unspecified``.  Returns ``None`` when neither
        is configured.
        """
        concurrency = (
            Concurrency.first_write if self._supports_etag else Concurrency.unspecified
        )
        if (
            concurrency == Concurrency.unspecified
            and self._consistency == Consistency.unspecified
        ):
            return None
        return StateOptions(
            concurrency=concurrency,
            consistency=self._consistency,
        )

    @staticmethod
    def _is_etag_mismatch(err: Exception) -> bool:
        """Return ``True`` if *err* represents a Dapr ETag mismatch."""
        if hasattr(err, "code") and callable(err.code):
            code = err.code()
            if code == StatusCode.ABORTED:
                return True
            if code == StatusCode.FAILED_PRECONDITION:
                details = (
                    err.details()
                    if hasattr(err, "details") and callable(err.details)
                    else ""
                )
                if details and "etag" in details.lower():
                    return True
        return False

    async def _retry_on_etag_conflict(
        self,
        operation: Callable[[], None],
    ) -> None:
        """Execute *operation* with automatic retry on ETag conflicts.

        Re-raises the original exception after ``_etag_max_retries``
        consecutive failures.
        """
        last_err: Exception | None = None
        for attempt in range(1, self._etag_max_retries + 1):
            try:
                operation()
                return
            except Exception as exc:
                if not self._is_etag_mismatch(exc):
                    raise
                last_err = exc
                delay = 0.1 * (2 ** (attempt - 1))  # 100ms, 200ms, 400ms …
                logger.warning(
                    f"ETag conflict (attempt {attempt}/{self._etag_max_retries}), "
                    f"retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
        raise last_err  # type: ignore[misc]

    def _read_index(self, key: str) -> tuple[list[str], str | None]:
        """Read a JSON index list from the state store.

        Returns a tuple of ``(items, etag)`` where *etag* is the
        state-store ETag when ``supports_etag`` is enabled, or
        ``None`` otherwise.
        """
        with tracer.start_as_current_span(f"{__name__}._read_index"):
            logger.debug(f"reading index for: {key}")
            resp = self._client.get_state(self._store_name, key)
            etag = resp.etag if self._supports_etag else None
            return deserialize_index(resp.text()), etag

    def _write_index(
        self,
        key: str,
        items: list[str],
        *,
        etag: str | None = None,
    ) -> None:
        """Overwrite a JSON index list in the state store."""
        with tracer.start_as_current_span(f"{__name__}._write_index"):
            logger.debug(f"overwriting json index list for: {key}...")
            meta = self._create_state_metadata_for_save(key, ttl=None)
            self._client.save_state(
                self._store_name,
                key,
                serialize_index(items),
                etag=etag if self._supports_etag else None,
                options=self._build_state_options(),
                state_metadata=meta,
            )

    def _reconcile_index(
        self,
        index_key: str,
        index_ids: list[str],
        live_keys: set[str],
        *,
        etag: str | None = None,
    ) -> list[str]:
        """Remove stale entries from an index and persist the cleaned version.

        Compares *index_ids* against *live_keys* (the set of keys whose
        bulk-get returned non-empty data).  Any id whose corresponding
        data key is absent from *live_keys* is considered expired /
        deleted and is pruned from the index.

        The cleaned index is written back only when at least one stale
        entry is detected, avoiding unnecessary writes.

        Args:
            index_key: The state-store key for the index
                (e.g. ``idx:artifacts`` or ``idx:type:Foo``).
            index_ids: The raw id list read from the index.
            live_keys: Set of data-store keys that returned non-empty
                data from the bulk-get.
            etag: Optional ETag from the preceding index read.

        Returns:
            The cleaned list of ids (same order, stale entries removed).
        """
        with tracer.start_as_current_span(f"{__name__}._reconcile_index"):
            cleaned = [uid for uid in index_ids if uid in live_keys]
            stale_count = len(index_ids) - len(cleaned)
            if stale_count > 0:
                logger.info(
                    f"Reconciling index '{index_key}': removed {stale_count} stale entry/entries"
                )
                self._write_index(index_key, cleaned, etag=etag)
            return cleaned

    async def _query_via_dapr_api(
        self, filters: FilterConfig | None = None
    ) -> list[Artifact]:
        """Fetch artifacts using the Dapr state query API (alpha).

        Handles token-based pagination internally so callers always
        receive the full result set.  Tags are post-filtered in-memory
        because the Dapr query language cannot express set-membership
        against JSON arrays.
        """
        with tracer.start_as_current_span(f"{__name__}._query_via_dapr_api"):
            query_json = _build_dapr_query(filters)
            logger.debug(f"Dapr query: {query_json}")
            artifacts: list[Artifact] = []
            token: str | None = None
            while True:
                # Inject pagination token for subsequent pages
                if token:
                    query_dict = json.loads(query_json)
                    query_dict.setdefault("page", {})["token"] = token
                    current_query = json.dumps(query_dict)
                else:
                    current_query = query_json
                response: QueryResponse = self._client.query_state(
                    store_name=self._store_name, query=current_query
                )
                for item in response.results:
                    if item.error:
                        logger.error(f"Query item error: {item.error}")
                        continue
                    try:
                        artifact = deserialize_artifact(item.text())
                    except Exception:
                        logger.debug(f"Skipping non-artifact key: {item.key}")
                        continue
                    artifacts.append(artifact)
                # Continue if more pages available
                if response.token:
                    token = response.token
                else:
                    break
            # Post-filter tags (Dapr query cannot handle array membership)
            if filters and filters.tags:
                artifacts = [a for a in artifacts if filters.tags.issubset(a.tags)]
            logger.debug(
                f"Dapr query returned {len(artifacts)} artifact(s) after post-filtering"
            )
            return artifacts

    def _query_via_index_scan(
        self, filters: FilterConfig | None = None
    ) -> list[Artifact]:
        """Fetch artifacts via index read + bulk get + in-memory filtering.

        Used when the backend does not support the Dapr query API or
        when the backend is encrypted (server-side queries are impossible
        on encrypted state).
        """
        with tracer.start_as_current_span(f"{__name__}._query_via_index_scan"):
            filters = filters or FilterConfig()
            # Optimisation: narrow the scan when type_names are provided
            if filters.type_names:
                uid_set: set[str] = set()
                for type_name in filters.type_names:
                    ids, _etag = self._read_index(_type_index_key(type_name))
                    uid_set.update(ids)
                all_ids = list(uid_set)
            else:
                all_ids, _etag = self._read_index(_IDX_ALL_ARTIFACTS)
            if not all_ids:
                return []
            keys = [_artifact_key(UUID(uid)) for uid in all_ids]
            items = self._client.get_bulk_state(
                self._store_name, keys, parallelism=10
            ).items
            # Build live-keys set and deserialize in one pass
            live_keys: set[str] = set()
            artifacts: list[Artifact] = []
            for item in items:
                if item.error or not item.text():
                    continue
                try:
                    artifacts.append(deserialize_artifact(item.text()))
                    live_keys.add(item.key.replace("artifact:", ""))
                except Exception:
                    logger.debug(f"Skipping non-artifact key: {item.key}")
                    continue
            # Reconcile stale index entries
            if filters.type_names:
                for type_name in filters.type_names:
                    type_ids, type_etag = self._read_index(_type_index_key(type_name))
                    self._reconcile_index(
                        _type_index_key(type_name),
                        type_ids,
                        live_keys,
                        etag=type_etag,
                    )
            else:
                self._reconcile_index(
                    _IDX_ALL_ARTIFACTS, all_ids, live_keys, etag=_etag
                )
            # Apply full in-memory filtering
            artifact_filter = ArtifactFilter(filters)
            artifacts = [a for a in artifacts if artifact_filter.matches(a)]
            logger.debug(
                f"Index scan returned {len(artifacts)} artifact(s) after filtering"
            )
            return artifacts

    async def _query_backend(
        self, filters: FilterConfig | None = None
    ) -> list[Artifact]:
        """Return matching artifacts from the backend.

        Dispatches to the Dapr query API when available, otherwise falls
        back to a full index scan with in-memory filtering.
        """
        with tracer.start_as_current_span(f"{__name__}._query_backend"):
            if self._encrypted_backend or not self._supports_dapr_query_lang:
                return self._query_via_index_scan(filters)
            return await self._query_via_dapr_api(filters)

    async def _get_consumptions_by_artifact_ids(
        self, artifact_ids: list[UUID]
    ) -> dict[str, list[ConsumptionRecord]]:
        """Get a list of consumption-records for a specific artifact by ID."""
        with tracer.start_as_current_span(
            f"{__name__}._get_consumptions_by_artifact_ids"
        ):
            logger.debug(f"Fetching consumptions for {len(artifact_ids)} artifact(s)")
            # Retrieve consumptions for each artifact_id
            results: dict[str, list[ConsumptionRecord]] = {}
            entry_ids: list[str] = []
            for artifact_id in artifact_ids:
                entry_ids.append(_consumptions_key(artifact_id))  # noqa: PERF401
            retrieved_consumption_entries: BulkStatesResponse = (
                self._client.get_bulk_state(
                    store_name=self._store_name, keys=entry_ids, parallelism=10
                )
            )
            # pre-filter results to exclude errors
            # and normalize results
            for entry in retrieved_consumption_entries.items:
                if entry.error:
                    logger.error(
                        f"Error when retrieving consumptions for entry: {entry.key}"
                    )
                    continue
                key = entry.key.replace("consumptions:", "")
                data = entry.text()
                # etag = entry.etag
                # deserialize
                consumptions_records = deserialize_consumption_records(data)
                results[key] = consumptions_records
            logger.debug(
                f"Retrieved consumptions for {len(results)}/{len(artifact_ids)} artifact(s)"
            )
            return results

    async def _publish_transactional(self, artifact: Artifact) -> None:
        """Publish an artifact to the blackboard (transactional).

        The artifact data key is saved separately with TTL metadata
        (when configured) because ``TransactionalStateOperation`` does
        not support per-item metadata.  Index updates remain atomic
        inside the transaction and are never given a TTL.
        """
        with tracer.start_as_current_span(f"{__name__}._publish_transactional"):
            async with self._lock:
                logger.debug(
                    f"Publishing artifact {artifact.id} (type={artifact.type}) [transactional]"
                )
                key = _artifact_key(artifact.id)
                uid = str(artifact.id)
                # 1. Read current indexes
                all_ids, all_etag = self._read_index(_IDX_ALL_ARTIFACTS)
                type_idx, type_etag = self._read_index(_type_index_key(artifact.type))
                if uid not in all_ids:
                    all_ids.append(uid)
                    type_idx.append(uid)
                # 2. Persist the artifact itself (with TTL when configured)
                artifact_meta = self._create_state_metadata_for_save(
                    key, ttl=self._entries_ttl
                )
                self._client.save_state(
                    self._store_name,
                    key,
                    serialize_artifact(artifact),
                    options=self._build_state_options(),
                    state_metadata=artifact_meta,
                )
                # 3. Atomically update both indexes (no TTL)
                artifact_idx_update_op = TransactionalStateOperation(
                    key=_IDX_ALL_ARTIFACTS,
                    data=serialize_index(all_ids),
                    etag=all_etag,
                    operation_type=TransactionOperationType.upsert,
                )
                type_index_update_op = TransactionalStateOperation(
                    key=_type_index_key(artifact.type),
                    data=serialize_index(type_idx),
                    etag=type_etag,
                    operation_type=TransactionOperationType.upsert,
                )
                _ = self._client.execute_state_transaction(
                    store_name=self._store_name,
                    operations=[artifact_idx_update_op, type_index_update_op],
                )
                logger.info(
                    f"Published artifact {artifact.id} (type={artifact.type}) [transactional]"
                )

    async def _publish_non_transactional(self, artifact: Artifact) -> None:
        """Publish an artifact to the blackboard in a non-transactional manner."""
        with tracer.start_as_current_span(f"{__name__}._publish_non_transactional"):
            async with self._lock:
                logger.debug(
                    f"Publishing artifact {artifact.id} (type={artifact.type}) [non-transactional]"
                )
                key = _artifact_key(artifact.id)
                uid = str(artifact.id)
                meta = self._create_state_metadata_for_save(key, ttl=self._entries_ttl)
                # 1. Persist the artifact itself (with TTL when configured)
                self._client.save_state(
                    self._store_name,
                    key,
                    serialize_artifact(artifact),
                    options=self._build_state_options(),
                    state_metadata=meta,
                )
                # 2. Append to the global artifact index
                all_ids, all_etag = self._read_index(_IDX_ALL_ARTIFACTS)
                if uid not in all_ids:
                    all_ids.append(uid)
                    self._write_index(_IDX_ALL_ARTIFACTS, all_ids, etag=all_etag)
                # 3. Append to the per-type index
                type_idx, type_etag = self._read_index(_type_index_key(artifact.type))
                if uid not in type_idx:
                    type_idx.append(uid)
                    self._write_index(
                        _type_index_key(artifact.type), type_idx, etag=type_etag
                    )
                logger.info(
                    f"Published artifact {artifact.id} (type={artifact.type}) [non-transactional]"
                )

    async def _record_consumptions_transactional(
        self, records: Iterable[ConsumptionRecord]
    ) -> None:
        """Records the fact that an artifact has been consumed and by whom. (transactional).

        Note: TTL cannot be applied per-item inside a Dapr state
        transaction (the Python SDK does not expose per-operation
        metadata).  Consumption records saved here will not carry TTL.
        Orphaned records (whose parent artifact has expired) are
        harmless — they are never referenced once the artifact's index
        entry is reconciled away.
        """
        with tracer.start_as_current_span(
            f"{__name__}._record_consumptions_transactional"
        ):
            async with self._lock:
                logger.debug("Recording consumptions [transactional]")
                # Group incoming records by artifact-id
                by_artifact: dict[UUID, list[ConsumptionRecord]] = {}
                transaction_operations: list[TransactionalStateOperation] = []
                for rec in records:
                    by_artifact.setdefault(rec.artifact_id, []).append(rec)
                for artifact_id, new_records in by_artifact.items():
                    key = _consumptions_key(artifact_id)
                    # Read existing consumptions records for this artifact
                    resp = self._client.get_state(self._store_name, key)
                    cons_etag = resp.etag if self._supports_etag else None
                    existing = (
                        deserialize_consumption_records(resp.text())
                        if resp.text()
                        else []
                    )
                    existing.extend(new_records)
                    transaction_operations.append(
                        TransactionalStateOperation(
                            key=key,
                            operation_type=TransactionOperationType.upsert,
                            data=serialize_consumption_records(existing),
                            etag=cons_etag,
                        )
                    )
                # Apply pending operations
                _ = self._client.execute_state_transaction(
                    store_name=self._store_name,
                    operations=transaction_operations,
                )
                logger.info(
                    f"Recorded consumptions for {len(by_artifact)} artifact(s) [transactional]"
                )

    async def _record_consumptions_non_transactional(
        self,
        records: Iterable[ConsumptionRecord],
    ) -> None:
        """Records the fact that an artifact has been consumed and by whom. (non-transactional)."""
        with tracer.start_as_current_span(
            f"{__name__}._record_consumptions_non_transactional"
        ):
            async with self._lock:
                logger.debug("Recording consumptions [non-transactional]")
                # Group incoming records by artifact_id.
                by_artifact: dict[UUID, list[ConsumptionRecord]] = {}
                state_items: list[StateItem] = []
                for rec in records:
                    by_artifact.setdefault(rec.artifact_id, []).append(rec)
                for artifact_id, new_records in by_artifact.items():
                    key = _consumptions_key(artifact_id)
                    # Read existing consumption records for this artifact.
                    resp = self._client.get_state(self._store_name, key)
                    cons_etag = resp.etag if self._supports_etag else None
                    existing = (
                        deserialize_consumption_records(resp.text())
                        if resp.text()
                        else []
                    )
                    existing.extend(new_records)
                    consumption_meta = self._create_state_metadata_for_save(
                        key, ttl=self._entries_ttl
                    )
                    opts = self._build_state_options()
                    state_items.append(
                        StateItem(
                            key=key,
                            value=serialize_consumption_records(existing),
                            etag=cons_etag,
                            options=opts.get_proto() if opts else None,
                            metadata=consumption_meta,
                        )
                    )
                self._client.save_bulk_state(
                    store_name=self._store_name,
                    states=state_items,
                )
                logger.info(
                    f"Recorded consumptions for {len(by_artifact)} artifact(s) [non-transactional]"
                )

    async def _upsert_agent_snapshot_transactional(
        self, snapshot: AgentSnapshotRecord
    ) -> None:
        """Upsert a Snapshot of an agent. (transactional)."""
        with tracer.start_as_current_span(
            f"{__name__}._upsert_agent_snapshot_transactional"
        ):
            async with self._lock:
                logger.debug(
                    f"Upserting snapshot for agent '{snapshot.agent_name}' [transactional]"
                )
                # 1. Read existing snapshot etag (for OCC) and build operations
                snap_resp = self._client.get_state(
                    self._store_name, _snapshot_key(snapshot.agent_name)
                )
                snap_etag = snap_resp.etag if self._supports_etag else None
                all_ids, idx_etag = self._read_index(_IDX_SNAPSHOTS)
                if snapshot.agent_name not in all_ids:
                    all_ids.append(snapshot.agent_name)
                snapshot_save_op = TransactionalStateOperation(
                    key=_snapshot_key(snapshot.agent_name),
                    data=serialize_agent_snapshot(snapshot),
                    etag=snap_etag,
                    operation_type=TransactionOperationType.upsert,
                )
                append_to_glob_idx_op = TransactionalStateOperation(
                    key=_IDX_SNAPSHOTS,
                    data=serialize_index(all_ids),
                    etag=idx_etag,
                    operation_type=TransactionOperationType.upsert,
                )
                operations = [
                    snapshot_save_op,
                    append_to_glob_idx_op,
                ]
                _ = self._client.execute_state_transaction(
                    store_name=self._store_name, operations=operations
                )
                logger.info(
                    f"Upserted snapshot for agent '{snapshot.agent_name}' [transactional]"
                )

    async def _upsert_agent_snapshot_non_transactional(
        self, snapshot: AgentSnapshotRecord
    ) -> None:
        """Upsert a Snapshot of an agent. (non-transactional)."""
        with tracer.start_as_current_span(
            f"{__name__}._upsert_agent_snapshot_non_transactional"
        ):
            async with self._lock:
                logger.debug(
                    f"Upserting snapshot for agent '{snapshot.agent_name}' [non-transactional]"
                )
                meta = self._create_state_metadata_for_save(snapshot.signature)
                # 1. Read existing snapshot to capture etag (for OCC on upsert)
                snap_etag: str | None = None
                if self._supports_etag:
                    snap_resp = self._client.get_state(
                        self._store_name, _snapshot_key(snapshot.agent_name)
                    )
                    snap_etag = snap_resp.etag or None
                # 2. Persist the snapshot
                self._client.save_state(
                    self._store_name,
                    key=_snapshot_key(snapshot.agent_name),
                    value=serialize_agent_snapshot(snapshot),
                    etag=snap_etag,
                    options=self._build_state_options(),
                    state_metadata=meta,
                )
                # 2. Append to the global snapshot index
                all_ids, idx_etag = self._read_index(_IDX_SNAPSHOTS)
                if snapshot.agent_name not in all_ids:
                    all_ids.append(snapshot.agent_name)
                    self._write_index(_IDX_SNAPSHOTS, all_ids, etag=idx_etag)
                logger.info(
                    f"Upserted snapshot for agent '{snapshot.agent_name}' [non-transactional]"
                )

    async def _clear_agent_snapshots_transactional(self) -> None:
        """Clear out all agent-snapshots. (transactional)."""
        with tracer.start_as_current_span(
            f"{__name__}._clear_agent_snapshots_transactional"
        ):
            async with self._lock:
                logger.debug("Clearing all agent snapshots [transactional]")
                # 1. Get a list of all snapshot ids.
                all_ids, idx_etag = self._read_index(_IDX_SNAPSHOTS)
                # 2. Prepare transaction
                operations: list[TransactionalStateOperation] = []
                for snapshot_id in all_ids:
                    operation = TransactionalStateOperation(
                        operation_type=TransactionOperationType.delete,
                        key=_snapshot_key(snapshot_id),
                        data=str(snapshot_id),
                    )
                    operations.append(operation)
                # 3. Also clear the index itself
                operations.append(
                    TransactionalStateOperation(
                        operation_type=TransactionOperationType.delete,
                        key=_IDX_SNAPSHOTS,
                        etag=idx_etag,
                        data="",
                    )
                )
                self._client.execute_state_transaction(
                    store_name=self._store_name,
                    operations=operations,
                )
                logger.info(f"Cleared {len(all_ids)} agent snapshot(s) [transactional]")

    async def _clear_agent_snapshots_non_transactional(self) -> None:
        """Clear out all agent-snapshots. (non-transactional)."""
        with tracer.start_as_current_span(
            f"{__name__}._clear_agent_snapshots_non_transactional"
        ):
            async with self._lock:
                logger.debug("Clearing all agent snapshots [non-transactional]")
                # 1. Get a list of all snapshot ids.
                all_ids, idx_etag = self._read_index(_IDX_SNAPSHOTS)
                logger.debug("Found %d snapshot(s) to delete", len(all_ids))
                # 2. Perform deletes
                for snapshot_id in all_ids:
                    logger.debug(f"Deleting agent snapshot '{snapshot_id}'")
                    _ = self._client.delete_state(
                        self._store_name,
                        key=_snapshot_key(snapshot_id),
                        options=self._build_state_options(),
                    )
                # 3. Clear the index
                self._write_index(_IDX_SNAPSHOTS, [], etag=idx_etag)
                logger.info(
                    f"Cleared {len(all_ids)} agent snapshot(s) [non-transactional]"
                )

    # ── core artifact operations ─────────────────────────────────────

    async def publish(self, artifact: Artifact) -> None:
        """Publish an artifact to the blackboard."""
        with tracer.start_as_current_span(f"{__name__}.publish"):
            logger.debug(f"Publishing artifact {artifact.id} (type={artifact.type})")
            if self._supports_transactions:
                await self._publish_transactional(artifact)
            else:
                await self._publish_non_transactional(artifact)

    async def get(self, artifact_id: UUID) -> Artifact | None:  # type: ignore[override]
        with tracer.start_as_current_span(f"{__name__}.get"):
            async with self._lock:
                logger.debug(f"Getting artifact {artifact_id}")
                resp = self._client.get_state(
                    self._store_name,
                    _artifact_key(artifact_id),
                )
                if not resp.text():
                    logger.debug(f"Artifact {artifact_id} not found")
                    return None
                logger.debug(f"Retrieved artifact {artifact_id}")
                return deserialize_artifact(resp.text())

    async def list(self) -> list[Artifact]:  # type: ignore[override]
        with tracer.start_as_current_span(f"{__name__}.list"):
            async with self._lock:
                logger.debug("Listing all artifacts")
                all_ids, idx_etag = self._read_index(_IDX_ALL_ARTIFACTS)
                if not all_ids:
                    logger.debug("No artifacts found")
                    return []
                keys = [_artifact_key(UUID(uid)) for uid in all_ids]
                items = self._client.get_bulk_state(
                    self._store_name,
                    keys,
                ).items
                # Build a mapping of live keys for reconciliation
                live_keys: set[str] = set()
                artifacts: list[Artifact] = []
                for item in items:
                    if not item.text():
                        continue
                    live_keys.add(item.key.replace("artifact:", ""))
                    artifacts.append(deserialize_artifact(item.text()))
                # Reconcile stale index entries
                self._reconcile_index(
                    _IDX_ALL_ARTIFACTS, all_ids, live_keys, etag=idx_etag
                )
                logger.debug(f"Listed {len(artifacts)} artifact(s)")
                return artifacts

    async def list_by_type(self, type_name: str) -> list[Artifact]:  # type: ignore[override]
        with tracer.start_as_current_span(f"{__name__}.list_by_type"):
            async with self._lock:
                logger.debug(f"Listing artifacts by type '{type_name}'")
                uids, idx_etag = self._read_index(_type_index_key(type_name))
                if not uids:
                    logger.debug(f"No artifacts of type '{type_name}' found")
                    return []
                keys = [_artifact_key(UUID(uid)) for uid in uids]
                items = self._client.get_bulk_state(
                    self._store_name,
                    keys,
                ).items
                # Build a mapping of live keys for reconciliation
                live_keys: set[str] = set()
                artifacts: list[Artifact] = []
                for item in items:
                    if not item.text():
                        continue
                    live_keys.add(item.key.replace("artifact:", ""))
                    artifacts.append(deserialize_artifact(item.text()))
                # Reconcile stale index entries
                self._reconcile_index(
                    _type_index_key(type_name), uids, live_keys, etag=idx_etag
                )
                logger.debug(
                    f"Listed {len(artifacts)} artifact(s) of type '{type_name}'"
                )
                return artifacts

    async def get_by_type(
        self,
        artifact_type: type[T],
        *,
        correlation_id: str | None = None,
    ) -> list[T]:  # type: ignore[override]
        with tracer.start_as_current_span(f"{__name__}.get_by_type"):
            logger.debug(
                f"Getting artifacts by type '{artifact_type.__name__}' (correlation_id={correlation_id})"
            )
            artifacts: list[Artifact] = []
            type_name = TypeResolutionHelper.safe_resolve(
                registry=registry, type_name=artifact_type.__name__
            )
            artifacts = await self.list_by_type(type_name)
            if correlation_id is not None:
                before = len(artifacts)
                artifacts = [a for a in artifacts if a.correlation_id == correlation_id]
                logger.debug(
                    f"Filtered by correlation_id '{correlation_id}': {before} -> {len(artifacts)} artifact(s)"
                )
            logger.debug(
                f"Returning {len(artifacts)} artifact(s) of type '{artifact_type.__name__}'"
            )
            return [artifact_type(**a.payload) for a in artifacts]  # type: ignore[return-value]

    # ── consumption records ──────────────────────────────────────────

    async def record_consumptions(
        self,
        records: Iterable[ConsumptionRecord],
    ) -> None:  # type: ignore[override]
        """Records the fact that an artifact has been consumed and by whom."""
        with tracer.start_as_current_span(f"{__name__}.record_consumptions"):
            logger.debug("Recording consumptions")
            if self._supports_transactions:
                await self._record_consumptions_transactional(records=records)
            else:
                await self._record_consumptions_non_transactional(records=records)

    # ── query / aggregation ──────────────────────────────────────────

    async def query_artifacts(
        self,
        filters: FilterConfig | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        embed_meta: bool = False,
    ) -> tuple[list[Artifact | ArtifactEnvelope], int]:
        with tracer.start_as_current_span(f"{__name__}.query_artifacts"):
            logger.debug(
                f"Querying artifacts (filters={filters}, limit={limit}, offset={offset}, embed_meta={embed_meta})"
            )
            artifacts = await self._query_backend(filters)
            # Sort consistently with InMemoryBlackboardStore
            artifacts.sort(key=lambda a: (a.created_at, a.id))
            # Total before pagination
            total = len(artifacts)
            # Apply offset/limit pagination
            offset = max(offset, 0)
            if limit <= 0:
                page = artifacts[offset:]
            else:
                page = artifacts[offset : offset + limit]

            if not embed_meta:
                logger.debug(f"Query returned {len(page)} artifact(s) (total={total})")
                return page, total

            artifact_ids = [a.id for a in page]
            consumptions = await self._get_consumptions_by_artifact_ids(
                artifact_ids=artifact_ids
            )
            envelopes: list[ArtifactEnvelope] = [
                ArtifactEnvelope(
                    artifact=a,
                    consumptions=consumptions.get(str(a.id), []),
                )
                for a in page
            ]
            logger.debug(f"Query returned {len(envelopes)} envelope(s) (total={total})")
            return envelopes, total

    async def fetch_graph_artifacts(
        self,
        filters: FilterConfig | None = None,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[ArtifactEnvelope], int]:
        """Return artifact envelopes (artifact + consumptions) for graph assembly."""
        logger.debug(f"Fetching graph artifacts (limit={limit}, offset={offset})")
        artifacts, total = await self.query_artifacts(
            filters=filters, limit=limit, offset=offset, embed_meta=True
        )
        envelopes: list[ArtifactEnvelope] = []
        for item in artifacts:
            if isinstance(item, ArtifactEnvelope):
                envelopes.append(item)
            elif isinstance(item, Artifact):
                envelopes.append(ArtifactEnvelope(artifact=item))
        logger.debug(f"Fetched {len(envelopes)} graph envelope(s)")
        return envelopes, total

    async def summarize_artifacts(
        self,
        filters: FilterConfig | None = None,
    ) -> dict[str, Any]:
        """Return aggregate artifact statistics for the given filters."""
        logger.debug(f"Summarizing artifacts (filters={filters})")
        filters = filters or FilterConfig()
        artifacts, total = await self.query_artifacts(
            filters=filters, limit=0, offset=0, embed_meta=False
        )
        for artifact in artifacts:
            if not isinstance(artifact, Artifact):
                raise TypeError("Expected Artifact instance")
        # Delegate to aggregator for aggregation logic
        is_full_window = filters.start is None and filters.end is None
        return self._aggregator.build_summary(artifacts, total, is_full_window)

    async def agent_history_summary(
        self,
        agent_id: str,
        filters: FilterConfig | None = None,
    ) -> dict[str, Any]:
        """Summarize agent history using history aggregator."""
        logger.debug(f"Summarizing agent history for '{agent_id}' (filters={filters})")
        filters = filters or FilterConfig()
        envelopes, _ = await self.query_artifacts(
            filters=filters,
            limit=0,
            offset=0,
            embed_meta=True,
        )
        # Delegate to history aggregator for aggregation logic
        return self._history_aggregator.aggregate(envelopes, agent_id)

    # ── agent snapshots ──────────────────────────────────────────────

    async def upsert_agent_snapshot(self, snapshot: AgentSnapshotRecord) -> None:
        with tracer.start_as_current_span(f"{__name__}.upsert_agent_snapshot"):
            logger.debug(f"Upserting agent snapshot for '{snapshot.agent_name}'")
            if self._supports_transactions:
                await self._upsert_agent_snapshot_transactional(snapshot)
            else:
                await self._upsert_agent_snapshot_non_transactional(snapshot)

    async def load_agent_snapshots(self) -> list[AgentSnapshotRecord]:
        with tracer.start_as_current_span(f"{__name__}.load_agent_snapshots"):
            async with self._lock:
                logger.debug("Loading all agent snapshots")
                snapshot_records: list[AgentSnapshotRecord] = []
                # 1. Get a list of all snapshot_ids
                all_ids, idx_etag = self._read_index(_IDX_SNAPSHOTS)
                if not all_ids:
                    return []
                # 2. Do a bulk read
                keys = [_snapshot_key(name) for name in all_ids]
                result: BulkStatesResponse = self._client.get_bulk_state(
                    self._store_name, keys=keys, parallelism=10
                )
                live_keys: set[str] = set()
                for item in result.items:
                    if item.error:
                        logger.error(f"Error retrieving snapshot: {item.error}")
                        continue
                    if not item.text():
                        logger.debug(f"Skipping empty snapshot entry: {item.key}")
                        continue
                    live_keys.add(item.key.replace("snapshot:", ""))
                    deserialized = deserialize_agent_snapshot(item.text())
                    snapshot_records.append(deserialized)
                # Reconcile stale snapshot index entries
                self._reconcile_index(_IDX_SNAPSHOTS, all_ids, live_keys, etag=idx_etag)
                logger.debug(f"Loaded {len(snapshot_records)} agent snapshot(s)")
                return snapshot_records

    async def clear_agent_snapshots(self) -> None:
        """Clear out all agent-snapshots."""
        with tracer.start_as_current_span(f"{__name__}.clear_agent_snapshots"):
            logger.debug("Clearing all agent snapshots")
            if self._supports_transactions:
                await self._clear_agent_snapshots_transactional()
            else:
                await self._clear_agent_snapshots_non_transactional()
