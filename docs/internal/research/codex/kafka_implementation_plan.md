# KafkaBlackboardStore — Implementation Plan

This plan adds a distributed, durable Blackboard store backed by Apache Kafka (or Redpanda) with clean delivery semantics, indexing, retries/DLQ, and observability. It enables large‑scale demos and research ideas 02 and 10 (parallel batching + distributed blackboard), and lays groundwork for others.

## Goals (v1 → v2)
- v1 (demo‑ready, at‑least‑once):
  - Produce artifacts to Kafka, consume to schedule agents, preserve ordering per key.
  - Partitioning by correlation_id or custom partition_key; parallel scaling via partitions/consumer groups.
  - Minimal global “index” to support `store.get` and `store.list_by_type` without full scans.
- v2 (production semantics):
  - Exactly‑once processing for publish→consume path (idempotent producers, transactions, read_committed).
  - DLQ + controlled retries with backoff; backpressure using lag.
  - Persistent dedup for (artifact_id, agent_name) to survive restarts.
  - Rich OTel instrumentation and dashboard visibility.

Non‑goals (now): schema registry, cross‑DC replication; we can add later.

## API Surface (Python)
- New: `src/flock/stores/kafka_store.py`
  - `class KafkaBlackboardStore(BlackboardStore)` implements:
    - `async def publish(self, artifact: Artifact) -> None`
    - `async def get(self, artifact_id: UUID) -> Artifact | None`
    - `async def list(self) -> list[Artifact]` (bounded recent window)
    - `async def list_by_type(self, type_name: str) -> list[Artifact]`
  - ctor opts:
    - `bootstrap_servers: str`
    - `topic_artifacts: str = "flock.artifacts"`
    - `topic_by_id: str = "flock.by_id"` (compacted)
    - `topic_processed: str = "flock.processed"` (compacted, durable dedup)
    - `topic_dlq_prefix: str = "flock.dlq."`
    - security config (TLS/SASL), batching (linger.ms, batch.size), acks, enable_idempotence, transactional_id (optional), read_committed (consumer)
    - `index_window: int = 10_000` (bounded in‑mem recent window for list)

## Message Model
- Encoding: JSON (artifact fields) for v1; optional schema registry later.
- Keys:
  - Producer key = `partition_key` if set else `correlation_id` if set else `hash(artifact.type + artifact.id)`.
  - Rationale: keeps correlated artifacts co‑located; otherwise spreads evenly.
- Topics:
  - `flock.artifacts` — append‑only event log of artifacts (N partitions).
  - `flock.by_id` — compacted index; key = artifact.id, value = artifact JSON (latest only).
  - `flock.processed` — compacted dedup; key = f"{artifact.id}:{agent_name}", value = metadata (timestamp, partition, offset, result).
  - DLQs: `flock.dlq.<agent>` (non‑compacted) for poison artifacts.

## Scheduling Flow
1) Publish: orchestrator→store.publish() produces to `flock.artifacts` and `flock.by_id` (dual‑write in same transaction when tx enabled).
2) Consume: orchestrator consumers (one per process) read `flock.artifacts` as a consumer group; for each artifact, the orchestrator computes target agents by subscription filters and schedules tasks.
3) Dedup: before scheduling (artifact, agent), check `flock.processed` (durable) to avoid re‑execution after restarts; in v1, fall back to in‑mem `_processed` set.
4) Commit: after agent finishes successfully, write processed key to `flock.processed` (and commit consumer offset). In tx mode, include both in the same transaction.

## Delivery Semantics
- v1: at‑least‑once with idempotent agent execution (dedup key).
- v2: exactly‑once (producer idempotence + transactions; consumers in read_committed; “processed” write + offset commit are atomically included in the same transaction).

## Retries & DLQ
- Retries: bounded attempts with exponential backoff counts embedded in headers.
  - Kafka lacks native delay; implement retry topics `flock.retry.<n>` and a lightweight delay worker, or schedule by time field and a polling worker.
- DLQ: after max attempts, route to `flock.dlq.<agent>` with error context. Provide dashboard drill‑down + replay action.

## Backpressure & Health
- Monitor consumer lag by partition; expose gauges in metrics and UI.
- Throttle publish if lag exceeds thresholds; lower agent concurrency on heavy partitions.

## Indexing & Queryability
- `get(id)`: read from an in‑process materialized map built by consuming `flock.by_id` (compacted) on startup; updates in real time.
- `list_by_type(type)`: maintain a bounded in‑mem LRU of recent artifact IDs per type while consuming `flock.artifacts`. Return the last K (configurable). Document that “list all” is not supported at infinite scale.
- `list()`: return the bounded recent window across types (document semantics).

## Observability
- Producer/consumer OTel spans with attributes: `kafka.topic`, `partition`, `offset`, `transaction_id`, `artifact.id`, `artifact.type`, `correlation_id`.
- Emit RED metrics per agent and per partition; display lag and retry counts in dashboard.

## Security
- TLS/SASL configs for cloud Kafka; secrets via env.
- ACL recommendations: producers to artifacts/by_id/processed; consumers in orchestrator group; separate writer for DLQ.

## Config & Ops
- Env vars:
  - `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_CLIENT_ID`, `KAFKA_SASL_*`, `KAFKA_SSL_*`
  - `KAFKA_TX_ENABLE=true|false`, `KAFKA_TX_ID=flock-orch-<node>`
  - `FLOCK_INDEX_WINDOW=10000`
- Local dev:
  - docker‑compose in `.flock/dev/kafka` (Redpanda or Kafka+ZK/Kraft) + UI (redpanda console or kafkaui).
  - Testcontainers in CI for integration tests.

## Failure Modes & Handling
- Producer fail mid‑transaction: abort and retry; artifacts not visible with read_committed.
- Orchestrator crash after consuming but before scheduling: on restart, message is reprocessed; dedup prevents double execution.
- Poison artifacts: route to DLQ and notify.

## Minimal Acceptance Criteria (v1)
- Publish/consume at‑least‑once across N partitions; tests assert no duplicate agent executions using dedup key.
- `get()` returns last version of an artifact after restart (via compacted by_id rebuild).
- Bounded `list`/`list_by_type` work and documented as recent‑window views.
- OTel spans include Kafka attributes; lag metrics visible.

## Stretch Acceptance (v2)
- Exactly‑once path validated with tx + read_committed; chaos tests for crash recovery.
- DLQ + retries with backoff; replay tool.
- Backpressure throttling based on lag; dashboard indicators.

## Test Strategy
- Unit tests: produce/consume round‑trip; partitioning; dedup logic.
- Integration: Testcontainers to boot Redpanda/Kafka; transactional tests; restart recovery; DLQ replay.
- Performance smoke: N=50k artifacts, P=8 partitions; measure makespan and p95 latency vs in‑memory store.

## Timeline & Milestones
- Week 1: v1 producer/consumer, in‑mem dedup, by_id compacted index, basic tests; local docker‑compose.
- Week 2: durable dedup (processed compacted topic), metrics/OTel, docs; initial benchmarks.
- Week 3: transactions + read_committed, retries/DLQ/backpressure, chaos tests; polish dashboard.

## Example Wiring
```python
from flock.orchestrator import Flock
from flock.stores.kafka_store import KafkaBlackboardStore

store = KafkaBlackboardStore(
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    topic_artifacts="flock.artifacts",
    topic_by_id="flock.by_id",
    topic_processed="flock.processed",
)
flock = Flock(store=store)
```

## Future Enhancements
- Schema evolution with Avro/Protobuf + Schema Registry; compaction‑friendly encoding for indices.
- RocksDB/Embedded state store for indexes (Kafka Streams‑style) if needed.
- Multi‑topic sharding (per‑tenant or per‑type) with dynamic discovery.
- Mirroring or bridge for interop (e.g., Kafka Connect to data lake).
