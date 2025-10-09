# Distributed Blackboard on Kafka/Pulsar

Score: 8.0 / 10

## Abstract
We design and evaluate a pluggable distributed `BlackboardStore` backed by Kafka or Pulsar with partitions, transactions, idempotence, and DLQs. We measure throughput/latency scaling and failure recovery, demonstrating production‑grade semantics.

## Research Questions / Hypotheses
- H1: Partitioning yields near‑linear scaling for independent workloads.
- H2: Kafka transactions + idempotent producers achieve exactly‑once processing for agent consumption.
- H3: DLQ and replay policies bound failure impact and cost.

## Experiment Sketch
- Implement `KafkaBlackboardStore` with partitioning and consumer groups; add idempotency keys.
- Benchmarks: vary partitions/replicas/consumers; inject failures; measure recovery and duplicates.

## Project Plan (4–6 weeks)
- Week 1–2: Implementation + tests.
- Week 3: Benchmarks; chaos testing.
- Week 4: Write‑up + operational runbook.

## Metrics
- Throughput, P50/P95/P99 latency, duplicate rate, recovery time, $/task.

## Value Proposition
- A credible scale story and operational semantics that many “agent frameworks” lack.

## Sources / Further Reading
- Kafka semantics, transactions, idempotence. https://kafka.apache.org/documentation/#semantics
- Pulsar docs. https://pulsar.apache.org/
- Event‑driven systems at scale (Fowler). https://martinfowler.com/articles/201701-event-driven.html
