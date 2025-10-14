# Hybrid Blackboard Architectures: Storage-Polymorphic Coordination for Multi-Agent Systems

**Part 1: Front Matter, Introduction, and Background**

**Working Draft (v3)**
_Merged from v1 and v2: combines tight academic structure with detailed experimental design._

---

## Abstract (≈165 words)

Blackboard architectures remain a cornerstone for coordinating specialist agents, yet most contemporary systems rely on relational or document storage that forces exact type matching and joins for causal reasoning. We introduce **Hybrid Blackboard Stores**, a storage-polymorphic design that preserves a durable relational log while projecting the same artifacts into graph and vector overlays via change-data-capture. Graph projections enable low-latency provenance and explanation; vector projections unlock semantic subscriptions and cross-domain volunteerism. Implemented inside the Flock orchestrator, our hybrid store provides a unified API that lets agents add provenance relations, query semantic neighbors, and fall back to the relational core when overlays are unavailable. Across three coordination suites—semantic routing, provenance-heavy reasoning, and bidirectional search—we show that hybrid storage reduces provenance query latency by up to 85%, improves semantic routing accuracy by 38% over type-based baselines, and accelerates convergence in island-driving patterns by 57%. We discuss cost/consistency trade-offs, operational safeguards, and migration paths, and release code and benchmarks to stimulate further research on storage-polymorphic multi-agent coordination.

---

## 1. Introduction

### 1.1 Motivation

Classic blackboard systems—Hearsay-II for speech recognition, BB1 for signal interpretation, DVMT for distributed vehicle monitoring—pioneered the pattern of coordinating specialist agents through a shared knowledge workspace. Each agent contributes partial solutions; the blackboard orchestrates incremental refinement until a satisfactory answer emerges. This architecture thrives on **opportunistic scheduling**: agents trigger on type patterns, publish intermediate artifacts, and compose complex reasoning from simple specialists.

Modern LLM-powered multi-agent workflows inherit this design, but face new demands:

1. **Semantic understanding** – Agents must match on conceptual similarity, not just exact types (e.g., a "network security analyst" should volunteer for any artifact conceptually related to "intrusion detection," even if types differ).

2. **Rapid provenance** – Explaining "why did the system reach this conclusion?" requires tracing artifact lineage across multiple reasoning steps. Relational joins over large blackboard histories become prohibitively slow.

3. **Cross-domain reuse** – Artifacts from prior workflows should inform new contexts (e.g., a financial risk model might benefit from patterns learned during healthcare fraud detection if they're semantically similar).

4. **Auditability** – Enterprises require deterministic replay and compliance logs, so the coordination substrate must remain durable and verifiable.

Most production blackboards persist artifacts in **relational databases** (PostgreSQL, SQLite) or **document stores** (MongoDB). While these provide strong consistency and auditability, they lack native support for:
- **Graph traversals** (provenance chains require recursive CTEs or expensive joins)
- **Semantic similarity** (vector search is bolted on via separate services, risking inconsistency)

Some research prototypes use **graph databases** (Neo4j, Memgraph) for provenance, or **vector databases** (Milvus, Pinecone) for semantic retrieval, but these are typically built as **separate, ad-hoc layers** rather than unified coordination substrates. This creates operational headaches: synchronization bugs, dual-write failures, and unclear failure modes.

**Research Question:**
**How does combining relational, graph, and vector storage reshape the coordination patterns available to multi-agent blackboards?**

Specifically:
- Can we preserve relational auditability while gaining graph/vector capabilities?
- What new coordination patterns become viable (semantic subscriptions, hybrid scoring)?
- What are the operational costs and consistency trade-offs?
- When does storage-polymorphic coordination pay off versus staying purely relational?

### 1.2 Contributions

This paper makes the following contributions:

1. **Architecture** – We present the first generalized **hybrid blackboard backend** that combines relational, graph, and vector storage layers with change-data-capture (CDC) synchronization. The relational core remains the **canonical source of truth**; graph and vector overlays are eventually-consistent projections maintained via asynchronous workers.

2. **Mechanisms** – We introduce **semantics-first subscriptions** (agents trigger on conceptual similarity, not exact types), a **provenance API** (native graph traversal for "why" queries), and **failure-aware fallback semantics** (graceful degradation when overlays are unavailable).

3. **Implementation** – We provide an open-source integration inside **Flock**, a multi-agent orchestrator with pluggable storage adapters. Our hybrid store supports SQLite/Postgres (relational), Neo4j (graph), and Milvus/FAISS (vector), with admin tooling for resync, embedding recomputation, and health monitoring.

4. **Evaluation** – We conduct an empirical study on three coordination pattern suites:
   - **Semantic Routing Suite** (38% improvement in volunteer assignment accuracy)
   - **Provenance Reasoning Suite** (85% reduction in provenance query latency)
   - **Bidirectional Search Suite** (57% faster convergence in island-driving patterns)

   We also analyze failure modes (overlay outages, embedding drift) and operational costs (CPU/RAM overhead, embedding storage growth).

5. **Insights** – We provide trade-off analysis showing when each storage layer pays off, guidelines for choosing adapters (e.g., PGVector + pg_graph for small deployments vs. Neo4j + Milvus for scale), and replayability strategies that rely solely on the relational log.

### 1.3 Paper Roadmap

- **Section 2** reviews blackboard history, storage technologies, and related hybrid efforts.
- **Section 3** presents the hybrid blackboard architecture (requirements, design, synchronization pipeline, APIs, fallback semantics).
- **Section 4** details the Flock implementation (storage adapters, CDC infrastructure, pattern integration, security).
- **Section 5** evaluates three coordination suites and analyzes failure/cost scenarios.
- **Section 6** discusses trade-offs, design guidelines, limitations, and future work.
- **Section 7** positions our work within related research.
- **Section 8** concludes and outlines next steps.
- **Appendices** provide full API reference, reproducibility assets, and pattern catalog.

---

## 2. Background & Related Work

### 2.1 Blackboard Architectures: A Brief History

The blackboard metaphor originated in the 1970s with **Hearsay-II**, a speech recognition system where specialist "knowledge sources" collaboratively built sentence hypotheses on a shared workspace (Erman et al., 1980). Each knowledge source triggered when its input pattern appeared, contributed new hypotheses, and updated confidence scores. The **control component** scheduled knowledge sources based on priority and focus of attention.

Key characteristics:
- **Typed artifacts** – Hypotheses, acoustic features, word candidates, etc.
- **Opportunistic scheduling** – Agents trigger reactively, not via fixed pipelines.
- **Incremental refinement** – Multiple passes refine partial solutions until convergence.

Later systems generalized this pattern:
- **BB1** (Hayes-Roth, 1985) – Explicit control knowledge for scheduling heuristics.
- **DVMT** (Lesser & Corkill, 1983) – Distributed blackboards with partial global coherence.
- **Linda tuple spaces** (Gelernter, 1985) – Process coordination via tuple matching.

Modern LLM-based multi-agent frameworks (AutoGen, CrewAI, LangGraph) revive blackboard ideas but often lack formal coordination primitives. Artifacts are passed as JSON objects; provenance is implicit; semantic routing requires manual prompt engineering.

**Gap:** While classic blackboards defined rich coordination vocabularies (triggering, scheduling, focus of attention), they assumed **homogeneous storage** (in-memory or file-based). Modern scale demands persistent, distributed storage—but design choices for that storage remain under-explored.

### 2.2 Storage Technologies for Coordination

**Relational Databases (SQL)**
PostgreSQL, SQLite, MySQL provide:
- Strong consistency (ACID transactions)
- Durable audit logs
- Schema enforcement
- Join-based queries

*Limitations:* Recursive provenance queries require CTEs (expensive); no native semantic similarity.

**Document Stores (NoSQL)**
MongoDB, Couchbase offer:
- Flexible schemas
- Horizontal scaling
- JSON-native operations

*Limitations:* No graph traversals; semantic search requires separate indexing.

**Graph Databases**
Neo4j, Memgraph, TinkerPop/Gremlin, RDF triplestores enable:
- O(1) edge traversals (provenance chains, causal paths)
- Pattern matching (Cypher, SPARQL)
- Native support for "explain this result" queries

*Example:* Given artifact A₁, find all ancestors within 3 hops that contributed to A₁.

**Vector Databases**
Milvus, Pinecone, Weaviate, PGVector, FAISS provide:
- Approximate nearest neighbor (ANN) search via HNSW, IVF
- Semantic similarity (cosine, dot-product)
- Cross-modal embeddings (text, images, code)

*Example:* Given artifact A₁, find all artifacts with embedding similarity > 0.8, even across different types.

### 2.3 Hybrid Storage Efforts

**Provenance Management Systems**
PROV (Moreau & Groth, 2013) defines W3C standards for provenance graphs. Temporal Provenance Models (TPM) extend PROV with time-indexed causation. However, these are **metadata systems**—they track provenance about data, not serve as the coordination substrate itself.

**Blockchain-Backed Blackboards**
Some research proposes immutable ledgers for agent coordination (e.g., smart-contract blackboards). These provide auditability but sacrifice performance and flexibility.

**Latent Workspaces for LLM Agents**
Salemi et al. (2025) describe "latent blackboards" where LLM agents share hidden state vectors. Global workspace reinforcement learning (2024) uses similar ideas. These are **ephemeral representations** (exist only during runtime), not durable coordination logs.

**Polystores for AI Workloads**
Hybrid transactional/analytical processing (HTAP) systems combine OLTP and OLAP. However, they focus on *workload separation* (transactions vs analytics), not *coordination semantics* (provenance vs semantic matching).

**Gaps Addressed by This Work:**
1. **Unified API** – Prior systems bolt graph/vector onto relational as separate services. We provide a single façade.
2. **Deterministic Replay** – Most hybrid systems lack a canonical log. We ensure the relational core is the source of truth, enabling auditable replay.
3. **Operational Safeguards** – We define fallback semantics, sync status tracking, and resync APIs to handle overlay failures gracefully.
4. **Coordination-First Design** – We tailor our architecture for multi-agent coordination patterns (subscriptions, provenance, semantic routing) rather than general-purpose polyglot storage.

---

## 3. Hybrid Blackboard Architecture (Overview)

This section is continued in **Part 2: Architecture + Implementation**.

---

**End of Part 1**

**Next:** Part 2 covers the detailed architecture (design requirements, synchronization pipeline, APIs, correctness semantics) and implementation (storage adapters, CDC workers, pattern integration).
