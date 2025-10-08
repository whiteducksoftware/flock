# Decoupled Event Orchestration → Parallel Throughput

Score: 9.4 / 10

## Abstract
Flock separates `publish()` from `run_until_idle()`, enabling batch publication before execution. This decoupling should materially reduce makespan for independent tasks versus graph engines that implicitly advance execution per edge update. We propose a head‑to‑head study demonstrating throughput and tail‑latency gains, including a distributed blackboard backing (Kafka/Pulsar) to show near‑linear scaling with partitions.

## Research Questions / Hypotheses
- H1: Batch‑then‑run achieves lower makespan than stepwise graph execution for independent agent tasks.
- H2: Partitioned queues (Kafka/Pulsar) provide near‑linear throughput gains for independent workloads.
- H3: Explicit batching reduces tail latency (P95/P99) under mixed workloads via better coalescing and fewer context switches.

## Experiment Sketch
- Workloads: synthetic (map‑style) and realistic (review analysis, retrieval+summarization). Vary independence and join needs.
- Systems: Flock (batch‑then‑run) vs graph engine baseline configured to run after each edge emission.
- Distributed mode: Flock with `KafkaBlackboardStore` partitions; measure throughput vs partitions and consumers.
- Failure: inject broker failures; test idempotence (exactly‑once) using Kafka transactions and idempotent producers.

## Project Plan (4–6 weeks)
- Week 1: Implement `KafkaBlackboardStore` (transactions, DLQ, backpressure), integration tests.
- Week 2: Build benchmark harness; produce baseline curves (in‑memory store).
- Week 3: Add Kafka/Pulsar experiments; failure/replay tests.
- Week 4: Analyze traces (OTel→DuckDB) and publish plots + write‑up.

## Metrics
- Makespan, RPS, CPU, memory, $/task, queue depth, and P50/P95/P99 latency; fairness under contention.

## Value Proposition
- Evidence that Flock’s decoupled event model is not just ergonomic—it’s faster and cheaper at scale, with clean semantics under failure.

## Sources / Further Reading
- Kafka idempotence and transactions (exactly‑once semantics). https://kafka.apache.org/documentation/#semantics
- Event‑driven architecture guides. https://martinfowler.com/articles/201701-event-driven.html
- Pulsar (streams + queue semantics). https://pulsar.apache.org/
- OpenTelemetry for trace‑level performance analysis. https://opentelemetry.io/
