# Needed Framework Implementation

This document summarizes (a) concrete engineering tasks needed to execute the current research ideas, and (b) a wishlist of larger capabilities that would unlock even more ambitious studies. Each item links to primary docs where relevant.

---

## A) Immediate Engineering Needed for Current Ideas

1) Distributed Blackboard Store (Kafka first; Redis Streams/Pulsar optional)
- Implement `KafkaBlackboardStore` with partitions and consumer groups; support idempotent producers and transactional writes for EOS paths; expose `partition_key` and `correlation_id` routing.
- Delivery semantics: start with at‑least‑once + idempotency; add exactly‑once using Kafka transactions and `read_committed` consumers; document trade‑offs.
  - Kafka design notes on idempotence/transactions: https://docs.confluent.io/kafka/design/delivery-semantics.html and blog explainer: https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/
- DLQ + replay: per‑topic DLQs; poison‑pill detection; manual/automatic replay with backoff; visibility in dashboard.
- Backpressure: queue depth thresholds; publish throttling; per‑agent concurrency caps already exist—add adaptive control based on lag.
- Local dev: Testcontainers profiles to boot Kafka/Redpanda for CI (Python testcontainers docs: https://github.com/testcontainers/testcontainers-python ; PyPI: https://pypi.org/project/testcontainers/).
- Alternatives (later): Pulsar store (https://pulsar.apache.org/docs/) or Redis Streams for light deployments (streams + consumer groups: https://redis.io/docs/latest/develop/data-types/streams/ and `XREADGROUP`: https://redis.io/docs/latest/commands/xreadgroup/).

2) Scheduling and Admission Control
- Global “run queue” metrics; admission policies (FIFO, SRPT‑like, join‑aware); per‑agent rate limits; fair sharing across tenants.
- Batch controls: batch windows and sizes by type; knobs surfaced in API/UI.
- Failure domains: circuit‑breakers on artifacts; retry budgets per type/tenant.

3) Observability for Research
- Trace schema: ensure spans include `artifact.id`, `type`, `partition`, `offset`, `attempt`, `policy_decision`.
- Exporters: keep DuckDB for in‑repo analytics (https://duckdb.org/docs/); optional OTLP to vendor collectors.
- Canned queries/plots: makespan, RED metrics, tail latency, per‑policy diffs.
- Unified OTel docs: https://opentelemetry.io/docs/ and Traces concept: https://opentelemetry.io/docs/concepts/signals/traces/

4) Web‑Agent Bench Harness (for 02/09/12 studies)
- Adapters to run the same agents/tools under BrowserGym / WebArena / WorkArena.
  - WebArena: https://webarena.dev/
  - BrowserGym: https://arxiv.org/abs/2412.05467
  - WorkArena / WorkArena++: https://arxiv.org/html/2403.07718 and https://arxiv.org/abs/2407.05291
- Safety extension (12): integrate ST‑WebAgentBench policy checks: https://arxiv.org/abs/2410.06703

5) Structured‑Output Enforcement & Governance (01/08)
- First‑class JSON‑Schema contracts for artifacts; “strict decode” path with model‑side constrained decoding where supported.
  - OpenAI Structured Outputs reference: https://openai.com/index/introducing-structured-outputs-in-the-api/
- Schema linting (risky patterns), quarantine queue, and review UI.

6) MCP Enhancements (03/14)
- Tool filtering/allowlists; caching tool metadata; lat/var tracking per tool.
  - MCP overview: Anthropic announcement https://www.anthropic.com/news/model-context-protocol ; OpenAI Agents MCP docs: https://openai.github.io/openai-agents-python/mcp/
- Transports: stdio/SSE/HTTP with retries and timeouts surfaced to policies.

7) Visibility & Multi‑Tenancy (07)
- Label lattice + ABAC evaluator; audit in traces (who/what/why allowed).
- OIDC for API/UI (OpenID Connect Core): https://openid.net/specs/openid-connect-core-1_0-final.html
- Optional policy offload to OPA (Rego) for complex enterprise rules: https://www.openpolicyagent.org/docs

8) Stigmergic Tags (05)
- Tag/decay subsystem on the blackboard (TTL, reinforcement); predicates can read tag intensity; expose metrics and UI heatmaps.

9) Formal Tools (04)
- Export orchestrations to Petri nets/TLA+ for small‑system checks; static analyzer for feedback‑loop risk.
  - TLA+ book: Lamport, “Specifying Systems” (Microsoft Research page): https://www.microsoft.com/en-us/research/publication/specifying-systems-the-tla-language-and-tools-for-hardware-and-software-engineers/
  - Petri nets resources (intro): Springer overview chapter https://link.springer.com/chapter/10.1007/978-981-16-5203-5_1

10) Benchmark: SWE‑Bench track (optional tie‑in)
- Adapter to run repo‑level tasks and compare orchestration modes; data: https://arxiv.org/abs/2310.06770

---

## B) Ambitious Wishlist (Enables “crazier” research angles)

1) Multi‑Node Orchestrator & Membership
- Horizontal scale with sharded blackboards; leader election and metadata via Raft/etcd; per‑shard run queues and cross‑shard joins.
  - Raft background (readable intro/paper pointer): MIT recitation handout linking to “In Search of an Understandable Consensus Algorithm” (Raft): https://web.mit.edu/6.1800/www/recitations/20-raft.shtml/r20.pdf

2) Reproducibility & Time‑Travel
- Snapshot/replay of blackboard state and decisions; deterministic mode (seeded policies; tool stubbing); “trace‑to‑replay” utility to reproduce failures.

3) Long‑Term Trace Warehouse
- Optional ClickHouse or Parquet+Iceberg sink for multi‑TB traces; curated “FlockTrace‑X” public dataset and compression/sampling study.

4) Learned Scheduling (06/11)
- Trace‑driven ML policies for batching, admission, and best‑of‑N/cascade depth; safe online A/B with rollback.

5) GPU/Resource‑Aware Engines
- Integrate resource schedulers; co‑schedule GPU/CPU agents; model and cost awareness in policies.

6) Secure Tool Sandboxing at Scale
- gVisor or Firecracker isolation for untrusted tools or user‑code agents; per‑call resource caps; ephemeral sandboxes.
  - gVisor project overview: https://gvisor.dev/ ; Firecracker microVMs: https://firecracker-microvm.github.io/

7) Data Lifecycle & Governance
- Artifact retention/TTL; redaction; encryption‑at‑rest with KMS; lineage queries linking artifacts ↔ traces.

8) Ecosystem Interop
- LangGraph adapter (run graphs on top of blackboard), and a bridge that mirrors Flock publications into external buses (Kafka Connect EOS notes: https://debezium.io/blog/2023/06/22/towards-exactly-once-delivery/).

9) Policy‑as‑Data UX
- Live policy editing (OPA/Rego) with dry‑run eval on historical traces; policy diffs and “blast radius” analysis.

10) Bench Expansion
- Add WorkArena++, WebChoreArena for higher task complexity: https://arxiv.org/abs/2407.05291 ; https://github.com/WebChoreArena/WebChoreArena

---

## Notes on Priorities
- For fast “wow”: ship Kafka store (A1), trace enrichments (A3), and a batch‑vs‑sequential demo in the dashboard (02 idea). These alone produce visible parallelism and clear tail‑latency wins.
- For research credibility: structured outputs + governance (A5), MCP‑native tooling (A6), and the web‑bench harness (A4) let us publish rigorous, reproducible comparisons.
