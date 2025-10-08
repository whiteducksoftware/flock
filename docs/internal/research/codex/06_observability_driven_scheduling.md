# Observability‑Driven Scheduling from OTel Traces

Score: 8.6 / 10

## Abstract
Flock records rich execution traces (OpenTelemetry→DuckDB). We propose learning scheduling policies (priorities, batching, admission control) directly from these traces to minimize makespan/cost under mixed workloads. This bridges systems telemetry and adaptive orchestration.

## Research Questions / Hypotheses
- H1: Policies trained on trace features outperform static heuristics for mixed workloads.
- H2: Tail‑latency reductions emerge from adaptive batching and join‑aware prioritization.
- H3: Learned policies remain stable under moderate distribution shifts.

## Experiment Sketch
- Collect traces across workloads; extract features (queue depth, artifact types, durations). Train policy (bandit/RL or supervised imitation of oracle).
- Compare to heuristics (FIFO, SRPT‑like, join‑aware rules) on held‑out runs.
- Validate stability with drifted workloads and failure injections.

## Project Plan (4–6 weeks)
- Week 1: Trace schema + feature extraction in DuckDB.
- Week 2: Baselines + simple learners; offline evaluation.
- Week 3: Online A/B in sandbox; guardrails for regressions.
- Week 4: Report + reusable policy hooks in Flock.

## Metrics
- Makespan, P95/P99 latency, $/success, policy regret, stability under drift.

## Value Proposition
- Turns built‑in observability into measurable performance wins and a publication‑worthy evaluation method for agents.

## Sources / Further Reading
- OpenTelemetry overview. https://opentelemetry.io/
- DuckDB analytics. https://duckdb.org/
- Google cluster traces for scheduling research (trace‑driven scheduling precedent). https://ai.googleblog.com/2012/05/google-cluster-data.html
