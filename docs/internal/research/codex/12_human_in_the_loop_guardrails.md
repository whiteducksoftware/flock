# Human‑in‑the‑Loop Guardrails at Publish Time

Score: 7.7 / 10

## Abstract
We augment Flock with configurable “ask‑human” gates triggered by policies at publish time (e.g., sensitive topics, high‑risk actions). We measure safety gains and latency impact on enterprise‑like workflows, using web‑agent safety benchmarks as inspiration.

## Research Questions / Hypotheses
- H1: Targeted HIL gates prevent a large fraction of risky outputs with modest added latency.
- H2: Policy authoring is simpler over typed artifacts than free‑text prompts.

## Experiment Sketch
- Define risk policies over artifact schemas and content; simulate human approvals via scripted reviewers.
- Evaluate on web‑agent tasks with sensitive operations; measure prevented violations vs overhead.

## Project Plan (3–5 weeks)
- Week 1: Policy engine + UI hooks in dashboard.
- Week 2: Benchmarks and ablations.
- Week 3: Write‑up + demo.

## Metrics
- Violations prevented, FP rate, added latency, reviewer effort.

## Value Proposition
- Pragmatic safety layer suitable for enterprise deployments; easily demoable.

## Sources / Further Reading
- ST‑WebAgentBench (safety for web agents). https://osf.io/preprints/osf/6xkse
- Responsible orchestration patterns (surveys on HIL for LLM systems). https://arxiv.org/abs/2407.14686
