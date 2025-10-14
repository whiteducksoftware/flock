# Hybrid Blackboard Architectures: Storage-Polymorphic Coordination for Multi-Agent Systems

**Part 2: Architecture and Implementation**

---

## 3. Hybrid Blackboard Architecture

### 3.1 Design Requirements

We identified four core requirements for a production-ready hybrid blackboard store:

**R1. Deterministic, Auditable Core**
The system must support **deterministic replay** for compliance, debugging, and research reproducibility. All coordination decisions must be traceable to a canonical log.

**R2. Low-Latency Provenance Queries**
Agents and dashboards must answer "why did we reach conclusion X?" in milliseconds, not seconds. Recursive joins over large relational tables are too slow for interactive debugging.

**R3. Semantic Routing for Opportunistic Volunteers**
Agents should trigger on **conceptual similarity**, not just exact type matches. Example: a "network security specialist" agent should volunteer when any artifact semantically aligns with "intrusion detection," even if types differ (AlertReport vs ThreatIntel vs NetworkFlow).

**R4. Graceful Degradation if Overlays Fail**
Graph or vector services may become unavailable (network partition, service crash, config error). The system must continue basic operations (publish, list, type-based triggering) using only the relational core, while logging degradation warnings.

### 3.2 Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    Agent Publish                         │
│             artifact = SynthesisReport(...)              │
│             await ctx.board.publish(artifact)            │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  Relational Core     │  ← SQLite / Postgres (source of truth)
          │  ┌────────────────┐  │
          │  │ artifacts      │  │  (id, type, payload, created_at, visibility)
          │  │ consumptions   │  │  (agent, artifact_id, result)
          │  │ artifact_rels  │  │  (from_id, relation, to_id, weight)
          │  │ artifact_embed │  │  (artifact_id, vector, model, created_at)
          │  └────────────────┘  │
          └──────────▲────────────┘
                     │
                     │ CDC Stream (async job queue)
                     │
      ┌──────────────┴──────────────┐
      │                             │
┌─────┴─────┐                 ┌─────┴─────┐
│ Graph Hub │                 │ Vector Hub│
│ Neo4j /   │                 │ Milvus /  │
│ Memgraph  │                 │ Pinecone /│
│           │                 │ FAISS     │
│ Nodes:    │                 │           │
│ Artifact  │                 │ Embeddings│
│           │                 │ + metadata│
│ Edges:    │                 │           │
│ PRODUCED  │                 │ ANN index │
│ DERIVED   │                 │ (HNSW)    │
│ CONFLICTS │                 │           │
└─────┬─────┘                 └─────┬─────┘
      │                             │
      │  Cypher queries             │  Similarity search
      │  (provenance path)          │  (semantic neighbors)
      │                             │
      └──────────────┬──────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  HybridStore Façade  │
          │  ┌────────────────┐  │
          │  │ publish()      │  │
          │  │ list_by_type() │  │
          │  │ add_relation() │  │
          │  │ find_related() │  │
          │  │ find_similar() │  │
          │  └────────────────┘  │
          └──────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │  Agent Subscription        │
        │  .consumes_similar(...)    │
        │  .consumes_related(...)    │
        └────────────────────────────┘
```

**Key Insight:** The relational core is the **canonical log**. Graph and vector hubs are **eventually-consistent projections** maintained via change-data-capture. This ensures:
- All writes succeed even if overlays are down (R4)
- Replay only requires the relational log (R1)
- Overlays accelerate reads (R2, R3) but don't compromise correctness

### 3.3 Data Model

**Relational Core Tables:**

```sql
-- Existing tables (from Flock)
CREATE TABLE artifacts (
    id UUID PRIMARY KEY,
    type VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL,
    produced_by VARCHAR(255),
    correlation_id UUID,
    visibility VARCHAR(50) DEFAULT 'default',
    tags TEXT[]
);

CREATE TABLE consumption_records (
    id UUID PRIMARY KEY,
    agent VARCHAR(255) NOT NULL,
    artifact_id UUID REFERENCES artifacts(id),
    result VARCHAR(50) NOT NULL,  -- 'success', 'error', 'rejected'
    metadata JSONB,
    created_at TIMESTAMP NOT NULL
);

-- New tables for hybrid features
CREATE TABLE artifact_relations (
    id UUID PRIMARY KEY,
    from_artifact_id UUID REFERENCES artifacts(id),
    relation VARCHAR(100) NOT NULL,  -- 'derived_from', 'conflicts_with', 'supports'
    to_artifact_id UUID REFERENCES artifacts(id),
    weight FLOAT,  -- Optional confidence/strength
    created_at TIMESTAMP NOT NULL,
    UNIQUE(from_artifact_id, relation, to_artifact_id)
);

CREATE TABLE artifact_embeddings (
    artifact_id UUID PRIMARY KEY REFERENCES artifacts(id),
    embedding_vector FLOAT[],  -- Or VECTOR type in PGVector
    embedding_model VARCHAR(100) NOT NULL,
    embedding_model_hash VARCHAR(64),
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE sync_status (
    artifact_id UUID PRIMARY KEY REFERENCES artifacts(id),
    graph_synced BOOLEAN DEFAULT FALSE,
    graph_sync_error TEXT,
    graph_last_attempt TIMESTAMP,
    vector_synced BOOLEAN DEFAULT FALSE,
    vector_sync_error TEXT,
    vector_last_attempt TIMESTAMP
);
```

**Graph Schema (Neo4j/Cypher):**

```cypher
// Nodes
(a:Artifact {
    id: UUID,
    type: String,
    produced_by: String,
    created_at: Timestamp,
    tags: [String]
})

(ag:Agent {name: String})

// Edges
(a1:Artifact)-[:PRODUCED_BY]->(ag:Agent)
(a1:Artifact)-[:DERIVED_FROM {weight: Float}]->(a2:Artifact)
(a1:Artifact)-[:CONFLICTS_WITH {confidence: Float}]->(a2:Artifact)
(a1:Artifact)-[:SUPPORTS {strength: Float}]->(a2:Artifact)
```

**Vector Index (Milvus/Pinecone):**

```python
# Collection schema
{
    "id": UUID,                    # Maps to artifact.id
    "type": String,
    "embedding": Vector(1536),     # text-embedding-3-large
    "tags": List[String],
    "visibility": String,
    "created_at": Timestamp
}

# Index: HNSW with cosine similarity
```

### 3.4 Synchronization Pipeline (CDC)

**Flow:**

1. **Write to Relational Core**
   ```python
   async def publish(self, artifact: Artifact) -> UUID:
       # Synchronous write to relational DB
       async with self.db.transaction():
           await self.db.insert_artifact(artifact)
           await self.db.insert_sync_status(artifact.id)

       # Enqueue CDC event (non-blocking)
       await self.cdc_queue.push(ArtifactCreatedEvent(artifact_id=artifact.id))
       return artifact.id
   ```

2. **CDC Worker Pool**
   ```python
   async def cdc_worker():
       while True:
           event = await cdc_queue.pop()

           if isinstance(event, ArtifactCreatedEvent):
               # Update graph
               try:
                   await graph_adapter.create_node(event.artifact_id)
                   await db.update_sync_status(event.artifact_id, graph_synced=True)
               except Exception as e:
                   await db.update_sync_status(event.artifact_id, graph_sync_error=str(e))
                   # Retry with exponential backoff

               # Update vector index
               try:
                   embedding = await embedding_service.embed(artifact.payload)
                   await vector_adapter.upsert(event.artifact_id, embedding)
                   await db.update_sync_status(event.artifact_id, vector_synced=True)
               except Exception as e:
                   await db.update_sync_status(event.artifact_id, vector_sync_error=str(e))

           elif isinstance(event, RelationAddedEvent):
               await graph_adapter.create_edge(event.from_id, event.relation, event.to_id, event.weight)
   ```

3. **Automatic Relation Inference**

   The system can automatically infer relations from existing coordination patterns:

   ```python
   async def infer_relations(artifact: Artifact) -> list[tuple[str, UUID, float]]:
       relations = []

       # 1. Correlation chain (same correlation_id)
       if artifact.correlation_id:
           related = await db.find_by_correlation(artifact.correlation_id, before=artifact.created_at)
           for r in related:
               relations.append(("part_of_workflow", r.id, 1.0))

       # 2. Consumption provenance (agent consumed X to produce Y)
       consumptions = await db.find_consumptions_by_agent(
           agent=artifact.produced_by,
           time_window=(artifact.created_at - timedelta(minutes=5), artifact.created_at)
       )
       for cons in consumptions:
           relations.append(("derived_from", cons.artifact_id, 0.9))

       # 3. Temporal proximity within same agent (likely causal)
       recent = await db.find_artifacts(
           produced_by=artifact.produced_by,
           time_window=(artifact.created_at - timedelta(seconds=30), artifact.created_at),
           limit=5
       )
       for r in recent:
           relations.append(("follows", r.id, 0.7))

       return relations
   ```

4. **Embedding Strategy Configuration**

   ```python
   embedding_config = {
       "Summary": {
           "model": "text-embedding-3-large",
           "fields": ["title", "content"],  # Concatenate these for embedding
           "dim": 1536
       },
       "KnowledgeChunk": {
           "model": "text-embedding-3-small",
           "fields": ["text"],
           "dim": 512
       },
       # Default for unconfigured types
       "_default": {
           "model": "text-embedding-3-small",
           "fields": ["*"],  # JSON stringify entire payload
           "dim": 512
       }
   }
   ```

**Consistency Guarantees:**

- **Relational writes:** Immediate consistency (ACID transactions)
- **Graph/vector sync:** Eventually consistent (async workers with retry)
- **Sync lag monitoring:** Expose `max_sync_lag` metric (p95 time from publish to overlay sync)
- **Backlog alerts:** Alert if sync queue depth > 1000 or lag > 5 minutes

### 3.5 Agent-Facing APIs

**HybridStore Façade:**

```python
class HybridBlackboardStore(BlackboardStore):
    """Unified store combining relational, graph, and vector backends."""

    async def publish(self, artifact: Artifact) -> UUID:
        """Write to relational core, enqueue CDC."""
        ...

    async def list_by_type(self, type: str, limit: int = 100) -> list[Artifact]:
        """Standard type-based query (relational)."""
        ...

    async def add_relation(
        self,
        from_artifact_id: UUID,
        relation: str,
        to_artifact_id: UUID,
        weight: float | None = None
    ) -> None:
        """Record provenance/causal relation."""
        await self.db.insert_relation(from_artifact_id, relation, to_artifact_id, weight)
        await self.cdc_queue.push(RelationAddedEvent(...))

    async def find_related(
        self,
        artifact_id: UUID,
        mode: Literal["graph", "semantic", "hybrid"] = "graph",
        depth: int = 2,
        limit: int = 10
    ) -> list[Artifact]:
        """Find related artifacts via graph traversal or semantic similarity."""

        if mode == "graph":
            if not self.graph_adapter.is_healthy():
                logger.warning("Graph overlay unavailable, falling back to relational")
                return await self._find_related_relational(artifact_id, depth, limit)

            # Cypher query: MATCH (a:Artifact {id: $id})-[:DERIVED_FROM*1..depth]->(related)
            related_ids = await self.graph_adapter.traverse(
                start=artifact_id, relation="DERIVED_FROM", depth=depth, limit=limit
            )
            return await self.db.get_artifacts_by_ids(related_ids)

        elif mode == "semantic":
            embedding = await self.db.get_embedding(artifact_id)
            similar_ids = await self.vector_adapter.search(embedding, limit=limit)
            return await self.db.get_artifacts_by_ids(similar_ids)

        elif mode == "hybrid":
            # Combined scoring: 0.6 * graph_distance + 0.4 * semantic_similarity
            return await self._hybrid_search(artifact_id, depth, limit)

    async def find_similar(
        self,
        reference: Artifact | UUID,
        min_similarity: float = 0.75,
        type_filter: str | None = None,
        limit: int = 10
    ) -> list[Artifact]:
        """Semantic similarity search via vector index."""

        if isinstance(reference, UUID):
            embedding = await self.db.get_embedding(reference)
        else:
            embedding = await self.embedding_service.embed(reference.payload)

        # ANN search with metadata filter
        results = await self.vector_adapter.search(
            embedding,
            min_score=min_similarity,
            filter={"type": type_filter} if type_filter else None,
            limit=limit
        )

        return await self.db.get_artifacts_by_ids([r.id for r in results])
```

**BoardHandle Extensions (Agent Context):**

```python
class BoardHandle:
    """Agent's view of the blackboard."""

    async def add_relation(self, target: UUID | Artifact, relation: str, weight: float | None = None):
        """Record that current artifact relates to target."""
        target_id = target if isinstance(target, UUID) else target.id
        await self.store.add_relation(self.current_artifact_id, relation, target_id, weight)

    async def find_provenance(self, depth: int = 3) -> list[Artifact]:
        """Find all artifacts that led to current artifact."""
        return await self.store.find_related(
            self.current_artifact_id, mode="graph", depth=depth
        )

    async def find_semantically_similar(self, min_similarity: float = 0.8) -> list[Artifact]:
        """Find artifacts conceptually similar to current one."""
        return await self.store.find_similar(
            self.current_artifact_id, min_similarity=min_similarity
        )
```

**Subscription Extensions:**

```python
# Semantic subscription (trigger on conceptual similarity)
agent = (
    flock.agent("cross_domain_reviewer")
    .consumes_similar(
        reference_id="c0ffee-1234",  # Or reference_type + embedding
        min_similarity=0.85,
        type_filter=SynthesisReport  # Optional
    )
)

# Graph-based subscription (trigger on provenance relation)
agent = (
    flock.agent("root_cause_analyzer")
    .consumes_related(
        relation="derived_from",
        depth=2,
        type=ErrorReport
    )
)
```

### 3.6 Correctness & Fallback Semantics

**Invariants:**

1. **Relational log is canonical** – All coordination decisions must be explainable from relational tables alone.

2. **Overlays are acceleration structures** – Graph/vector can be **rebuilt offline** from the relational log if corrupted.

3. **Graceful degradation** – If overlays fail:
   - Type-based subscriptions continue via relational queries
   - Semantic/graph subscriptions log warnings and skip (don't crash)
   - Admin dashboard shows "degraded mode" alert

4. **Deterministic replay** – Re-running the flow with the same relational log produces identical agent invocations (overlays are rebuilt on replay if needed).

**Fallback Algorithm:**

```python
async def find_related(self, artifact_id: UUID, mode: str, depth: int, limit: int):
    if mode == "graph":
        if self.graph_adapter.is_healthy():
            try:
                return await self._find_related_graph(artifact_id, depth, limit)
            except Exception as e:
                logger.error(f"Graph query failed: {e}, falling back to relational")
                self.metrics.increment("fallback.graph_to_relational")

        # Fallback: recursive CTE in relational DB
        return await self._find_related_relational(artifact_id, depth, limit)

    elif mode == "semantic":
        if self.vector_adapter.is_healthy():
            try:
                return await self._find_similar_vector(artifact_id, limit)
            except Exception as e:
                logger.warning(f"Vector query failed: {e}, no fallback available")
                self.metrics.increment("fallback.vector_unavailable")
                return []  # Degrade to empty (semantic features disabled)

        return []  # No semantic fallback to relational
```

**Operational Safeguards:**

- **Health checks:** Periodic `/health` endpoint for graph/vector services
- **Sync status dashboard:** Show per-artifact sync state (pending, synced, error)
- **Resync API:** `POST /admin/resync?artifact_id=X&target=graph` to manually retry
- **Embedding recomputation:** `POST /admin/recompute_embeddings?model=text-embedding-3-large` for bulk updates

---

## 4. Implementation in Flock

### 4.1 Storage Adapters

Flock's hybrid store uses **pluggable adapters** to support various backends:

**Relational Adapter (SQLite / Postgres):**

```python
class RelationalAdapter:
    def __init__(self, dsn: str):
        self.engine = create_async_engine(dsn)

    async def insert_artifact(self, artifact: Artifact) -> UUID: ...
    async def get_artifacts_by_ids(self, ids: list[UUID]) -> list[Artifact]: ...
    async def find_by_type(self, type: str, limit: int) -> list[Artifact]: ...
    async def insert_relation(self, from_id, relation, to_id, weight): ...
    async def insert_embedding(self, artifact_id, vector, model, model_hash): ...
```

**Graph Adapter (Neo4j):**

```python
class Neo4jGraphAdapter:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = neo4j.AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def create_node(self, artifact_id: UUID, type: str, metadata: dict): ...
    async def create_edge(self, from_id: UUID, relation: str, to_id: UUID, weight: float | None): ...

    async def traverse(self, start: UUID, relation: str, depth: int, limit: int) -> list[UUID]:
        """Return artifact IDs reachable via relation within depth hops."""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (start:Artifact {id: $start})-[r:$relation*1..$depth]->(related:Artifact)
                RETURN related.id AS id
                LIMIT $limit
                """,
                start=str(start), relation=relation, depth=depth, limit=limit
            )
            return [UUID(record["id"]) async for record in result]

    async def is_healthy(self) -> bool:
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception:
            return False
```

**Vector Adapter (Milvus / FAISS / PGVector):**

```python
class MilvusVectorAdapter:
    def __init__(self, uri: str, collection: str, dim: int):
        self.collection = Collection(collection)
        self.dim = dim

    async def upsert(self, artifact_id: UUID, embedding: list[float], metadata: dict): ...

    async def search(
        self,
        query_vector: list[float],
        min_score: float = 0.0,
        filter: dict | None = None,
        limit: int = 10
    ) -> list[SearchResult]:
        """ANN search with optional metadata filtering."""
        search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
        results = self.collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            expr=self._build_filter_expr(filter) if filter else None
        )
        return [SearchResult(id=r.id, score=r.distance) for r in results[0] if r.distance >= min_score]
```

**Configuration DSL:**

```yaml
# flock_config.yaml
store:
  type: hybrid
  relational:
    dsn: "postgresql://user:pass@localhost/flock"
  graph:
    provider: neo4j
    uri: "neo4j://localhost:7687"
    user: neo4j
    password: secret
  vector:
    provider: milvus
    uri: "tcp://localhost:19530"
    collection: "flock_artifacts"
    embedding_model: "text-embedding-3-large"
    dim: 1536

  # Embedding strategy per type
  embeddings:
    Summary:
      model: text-embedding-3-large
      fields: [title, content]
    KnowledgeChunk:
      model: text-embedding-3-small
      fields: [text]
```

### 4.2 Change-Data-Capture Infrastructure

```python
class CDCWorkerPool:
    def __init__(self, num_workers: int = 4):
        self.queue = AsyncQueue()  # Durable: SQLite WAL or Redis
        self.workers = [asyncio.create_task(self._worker()) for _ in range(num_workers)]

    async def _worker(self):
        while True:
            event = await self.queue.pop()
            try:
                await self._handle_event(event)
                self.metrics.increment("cdc.success")
            except Exception as e:
                logger.error(f"CDC worker error: {e}")
                self.metrics.increment("cdc.error")
                await self._retry_with_backoff(event)

    async def _handle_event(self, event: CDCEvent):
        if isinstance(event, ArtifactCreatedEvent):
            # Update graph
            artifact = await self.db.get_artifact(event.artifact_id)
            await self.graph_adapter.create_node(artifact.id, artifact.type, {...})

            # Infer relations
            relations = await self.infer_relations(artifact)
            for rel, target_id, weight in relations:
                await self.graph_adapter.create_edge(artifact.id, rel, target_id, weight)

            # Compute embedding
            if artifact.type in self.embedding_config:
                embedding = await self.embedding_service.embed(artifact, self.embedding_config[artifact.type])
                await self.vector_adapter.upsert(artifact.id, embedding, {...})

            # Mark synced
            await self.db.update_sync_status(artifact.id, graph_synced=True, vector_synced=True)
```

**Observability:**

- **Metrics:** `cdc.queue_depth`, `cdc.sync_lag_seconds`, `cdc.error_count`
- **Tracing:** Integrate with OpenTelemetry to trace publish → CDC → overlay sync
- **Dashboards:** Grafana panels showing sync health, failure rates, backlog

### 4.3 Pattern Integration

The hybrid store unlocks enhanced versions of coordination patterns:

**Self-Correcting Contracts (Graph-Enhanced):**

```python
root_cause_agent = (
    flock.agent("root_cause_analyzer")
    .consumes(ContractViolation)
    .publishes(RootCauseReport)
)

@root_cause_agent.agent
async def analyze_root_cause(ctx: Context, violation: ContractViolation):
    # Use graph provenance to trace back to original cause
    provenance = await ctx.board.find_related(
        violation.id, mode="graph", depth=5
    )

    # Find all ErrorReports in provenance chain
    errors = [a for a in provenance if isinstance(a, ErrorReport)]

    await ctx.publish(RootCauseReport(
        violation_id=violation.id,
        root_causes=errors,
        provenance_chain=[a.id for a in provenance]
    ))
```

**Expectation Watchtower (Semantic-Enhanced):**

```python
# Specialist volunteers based on semantic similarity to posted expectation
malware_analyst = (
    flock.agent("malware_specialist")
    .consumes_similar(
        reference_type=ExpectationPosted,
        min_similarity=0.85,
        filter=lambda exp: "malware" in exp.tags or "hash" in exp.tags
    )
    .publishes(CollectedEvidence)
)

@malware_analyst.agent
async def gather_malware_intel(ctx: Context, expectation: ExpectationPosted):
    # Check if this expectation is semantically similar to our expertise
    # (automatically handled by consumes_similar subscription)

    evidence = await fetch_malware_hash(expectation.description)
    await ctx.publish(CollectedEvidence(expectation_id=expectation.id, evidence=evidence))
    await ctx.board.add_relation(target=expectation.id, relation="fulfills", weight=1.0)
```

**Island Driving (Hybrid Scoring):**

```python
@rendezvous_agent.agent
async def find_rendezvous(ctx: Context, forward: ForwardFragment, reverse: ReverseConstraint):
    # Hybrid scoring: combine graph proximity + semantic similarity
    candidates = await ctx.board.find_related(
        forward.id, mode="hybrid", depth=3, limit=20
    )

    # Score each candidate: graph_distance * 0.6 + semantic_similarity * 0.4
    scored = []
    for cand in candidates:
        graph_dist = await ctx.board.graph_distance(forward.id, cand.id)
        semantic_sim = await ctx.board.semantic_similarity(reverse.id, cand.id)
        score = 0.6 * (1.0 / (graph_dist + 1)) + 0.4 * semantic_sim
        scored.append((cand, score))

    best = max(scored, key=lambda x: x[1])
    await ctx.publish(RendezvousHypothesis(location=best[0], confidence=best[1]))
```

### 4.4 Security & Visibility

**Propagating Visibility Constraints:**

```python
# Relational: visibility column
# Graph: Visibility label on nodes
# Vector: Metadata filter

async def list_by_type(self, type: str, visibility: str = "default") -> list[Artifact]:
    # Relational query
    artifacts = await self.db.query("SELECT * FROM artifacts WHERE type = ? AND visibility = ?", type, visibility)
    return artifacts

async def search_vector(self, embedding, visibility: str = "default"):
    # Milvus metadata filter
    results = await self.vector_adapter.search(
        embedding,
        filter={"visibility": visibility}
    )
    return results
```

**Multi-Tenancy:**

- **Option 1:** Separate graph databases per tenant (isolated Neo4j instances)
- **Option 2:** Tenant label/property on all nodes; enforce in Cypher queries
- **Option 3:** Hybrid: shared vector index with tenant metadata filter, separate graph per tenant

---

**End of Part 2**

**Next:** Part 3 covers detailed evaluation (three coordination suites, experiments, performance tables, cost analysis).
