# My Amazing Hybrid Blackboard Store

## Vision
Give Flock a storage backend that keeps the **canonical blackboard log** in a durable relational store, while projecting the same artifacts into a **graph layer** (for provenance/explanation) and a **vector layer** (for semantic routing). Agents and dashboards interact with a unified API; the hybrid store handles synchronization, consistency, and fallbacks behind the scenes.

The goal is to unlock:
- Provenance queries (“why did we reach this conclusion?”) without expensive joins
- Semantic subscriptions (“trigger when a new artifact is similar to X”) without bolting on ad-hoc retrievers
- Deterministic replays and audits backed by the relational log

## Architecture Overview

```
          ┌───────────────────────┐
 Publish  │  Relational Core      │  ← SQLite/Postgres
────────▶ │  artifacts, tags,     │
          │  consumption records   │
          └──────────▲────────────┘
                     │ CDC stream (async jobs)
                     │
      ┌──────────────┴──────────────┐
      │                             │
┌─────┴─────┐                 ┌─────┴─────┐
│ Graph Hub │                 │ Vector Hub│
│ Neo4j/Ogre│                 │ Milvus etc│
│ Edges:    │                 │ Embeddings│
│ produced→ │                 │ Similarity│
│ derived→  │                 │   index   │
└─────┬─────┘                 └─────┬─────┘
      │  GQL / Cypher queries       │ Annoy/HNSW lookups
      │                             │
     Agents / dashboards via HybridStore service façade
```

## Components

1. **Relational core (existing SQLite/SQLAlchemy store)**
   - Source of truth for `Artifact`, `ConsumptionRecord`
   - Records `created_at`, visibility, tags, version
   - Adds new tables:
     - `artifact_relations(artifact_id, relation, target_id, weight, created_at)`
     - `artifact_embeddings(artifact_id, embedding_vector, embedding_model, created_at)`

2. **Graph hub (Neo4j, Memgraph, or TinkerPop)**
   - Nodes: Artifacts (id, type, produced_by, timestamp)
   - Edges:
     - `PRODUCED_BY` (Artifact → Agent)
     - `DERIVED_FROM` (Artifact → Artifact)
     - `CONFLICTS_WITH`, `SUPPORTS`, etc.
   - Optional edge weights/confidence
   - Maintained through change-data-capture (CDC) jobs

3. **Vector hub (Milvus, Pinecone, FAISS)**
   - Indexes artifact payload embeddings
   - Supports similarity search, hybrid metadata filters
   - Tracks embedding model/version per entry

4. **HybridStore façade**
   - Implements `BlackboardStore` interface
   - Delegate:
     - Writes to relational core synchronously (ensures durability)
     - Pushes change events to graph/vector layers asynchronously (retry queues)
   - Exposes new APIs:
     - `relational` / `graph` / `vector` handles for advanced queries
     - `find_related(artifact_id, depth=1, mode="graph|semantic")`
     - `subscribe_similar(type, reference_id, min_similarity)`
     - `record_relation(from_id, relation, to_id, weight=None)`
     - `upsert_embedding(artifact_id, embedding, model_name)`

## Data Flow

1. **Publish**
   - `HybridStore.publish(artifact)` writes to relational core inside transaction
   - After commit, enqueue message `ArtifactCreated` to async worker
   - Worker:
     - Updates graph hub with new node + edges (based on relations table)
     - Generates/ingests embedding (if type is configured for embeddings)

2. **Relations**
   - Agents can call `ctx.board.add_relation(target="artifact_id", relation="derived_from", weight=0.9)` which writes to relational `artifact_relations`
   - CDC job syncs this to graph hub

3. **Embeddings**
   - On publish (or via background job) compute embedding using configured model
   - Store vector + metadata in `artifact_embeddings` table and push to vector index
   - For deterministic replay, store embedding model hash and version

4. **Similarity Queries**
   - `HybridStore.find_similar(reference_id, type=None, min_similarity=0.8)` queries vector hub
   - Returns artifact IDs (ordered by similarity). Optional cross-check against relational store for visibility filtering

5. **Provenance Queries**
   - `HybridStore.graph().path(start=artifact_id, relation="DERIVED_FROM", depth=3)` runs a Cypher query; fallback to relational join if graph hub unavailable

## API Extensions

### New BoardHandle Methods

```python
class BoardHandle:
    async def add_relation(self, *, artifact_id: UUID, relation: str, target_id: UUID, weight: float | None = None) -> None:
        ...

    async def find_related(self, *, artifact_id: UUID, mode: Literal["graph", "semantic", "hybrid"], limit: int = 10) -> list[Artifact]:
        ...

    async def find_similar(self, *, reference: Artifact | UUID, min_similarity: float = 0.75, type_filter: str | None = None) -> list[Artifact]:
        ...
```

### Subscription Enhancements

```python
(
    flock.agent("similarity_reviewer")
    .consumes(SynthesizedReport)
    .consumes_similar(
        reference="artifact-id",
        min_similarity=0.8,
        type=SynthesizedReport,
        embedding_field="summary_vector",
    )
)
```

Behind the scenes the orchestrator translates `consumes_similar` into vector lookups + artifact filtering before scheduling.

### Store Configuration

```python
from flock.store.hybrid import HybridBlackboardStore, GraphConfig, VectorConfig

store = HybridBlackboardStore(
    core_dsn="sqlite:///blackboard.db",
    graph=GraphConfig(
        uri="neo4j://localhost:7687",
        user="neo4j",
        password="secret",
    ),
    vector=VectorConfig(
        provider="milvus",
        uri="tcp://localhost:19530",
        collection="flock_artifacts",
        embedding_model="text-embedding-3-large",
    ),
    embed_types={"Summary", "KnowledgeChunk"},
)
```

## Operational Considerations

### Consistency & Ordering
- Relational log is the source of truth; graph/vector layers are eventually consistent.
- Include `sync_status` flags:
  - `artifact_sync(graph_synced: bool, vector_synced: bool, last_attempt: datetime, error: str | None)`
  - Expose admin API to resync artifacts (e.g., `store.resync(artifact_id, targets={"graph"})`)

### Embedding Recomputations
- Store embedding model + hash; if model changes, queue batch recomputation job.
- Provide CLI command: `flock hybrid recompute-embeddings --model text-embedding-3-large`

### Failure Modes
- Graph hub down: queue updates, fallback to relational queries and warn that graph-dependent features (e.g., `find_related(mode="graph")`) will degrade gracefully.
- Vector hub down: skip similarity scheduling, log warnings, maintain backlog.
- Provide telemetry counters for sync lag, error counts.

### Security & Visibility
- Mirror relational visibility checks in graph/vector queries by filtering on metadata.
- For sensitive deployments, allow separate credentials or network isolation per hub.

### Migration Path
1. Upgrade to hybrid store in passive mode (relational writes + background sync).
2. Run integrity checks (e.g., random graph traversals match relational join results).
3. Enable graph/vector features incrementally (subscriptions, APIs).

## Testing Strategy
- **Unit Tests**
  - Verify hybrid store implements `BlackboardStore` contract (publish/list/query).
  - Mock graph/vector clients to buffer updates and assert payloads.
- **Integration Tests**
  - Spin up SQLite + Neo4j (Docker) + Milvus (or FAISS) to validate sync pipeline.
  - Simulate outages: kill graph service, ensure relational store still works and backlog resumes afterward.
- **Performance Benchmarks**
  - Measure publish latency with and without sync workers.
  - Evaluate vector similarity accuracy on synthetic workloads.

## Roadmap
1. **Phase 1 – Core plumbing**
   - Implement hybrid store skeleton, relation/embedding tables, background workers.
   - Expose health metrics, resync CLI.
2. **Phase 2 – Graph features**
   - Add `add_relation` / `find_related` board APIs.
   - Integrate provenance path visualizations in dashboard.
3. **Phase 3 – Vector features**
   - Add `consumes_similar`, `find_similar`, semantic dashboard search.
   - Support embedding refresh pipeline.
4. **Phase 4 – Advanced**
   - Hybrid queries (vector + graph combined scoring).
   - Policy-based scheduling (“only run agent if semantic similarity >0.9 AND provenance chain length < 3”).
   - Multi-tenant graph partitions or label-based access control.

## Open Questions
- **Embedding model choice:** per artifact type vs global. Need configuration DSL.
- **Graph schema evolution:** should we enforce relation vocab (DERIVED_FROM, SUPPORTS, CONFLICTS_WITH) or allow arbitrary labels?
- **Backpressure:** how to throttle sync jobs when graph/vector services lag.
- **Transactional guarantees:** do we need two-phase commits for high-stakes environments, or is eventual consistency acceptable with retry logs?
- **Cost:** running Neo4j + Milvus adds operational overhead; consider pluggable adapters (e.g., use Postgres PGVector + pg_graph extension for smaller deployments).

---

**Outcome:** a hybrid store gives Flock builders the best of both worlds—durable, auditable records; rich provenance paths; semantic routing; and clear APIs for future orchestration features.
