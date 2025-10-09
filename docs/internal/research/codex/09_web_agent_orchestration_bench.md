# Web‑Agent Orchestration Bench (Blackboard vs Graph)

Score: 8.2 / 10

## Abstract
We build a reproducible harness where identical agents/tools run under two orchestration modes—Flock’s blackboard vs a graph engine—on WebArena/BrowserGym/WorkArena tasks. We measure success, path optimality, and tail latency, isolating orchestration as the variable.

## Research Questions / Hypotheses
- H1: Blackboard orchestration improves parallelism and reduces coordination overhead on multi‑input tasks.
- H2: For tasks requiring joins/batching, blackboard reduces errors and retries.
- H3: Differences are visible in trace DAGs and resource utilization.

## Experiment Sketch
- Choose a subset of WebArena/BrowserGym/WorkArena tasks; implement task adapters once; swap the orchestration layer.
- Normalize tools (MCP if possible) to keep only orchestration different.
- Collect success rate, action length, and latency; analyze traces and failure modes.

## Project Plan (4–6 weeks)
- Week 1: Harness and task adapters.
- Week 2: Baseline runs + trace collection.
- Week 3: Analysis + ablations; publish plots and example traces.

## Metrics
- Task success, action length/path optimality, P95 latency, and cost.

## Value Proposition
- A clean, public comparison that elevates orchestration as a first‑class design choice.

## Sources / Further Reading
- WebArena benchmark. https://webarena.dev/
- BrowserGym (web agent evaluation toolkit). https://arxiv.org/abs/2406.05294
- WorkArena (enterprise‑like browser tasks). https://arxiv.org/abs/2406.15864
