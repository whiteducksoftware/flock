# Cost‑Optimal Best‑of‑N and Cascade Gating

Score: 7.9 / 10

## Abstract
Best‑of‑N sampling and cascaded agents improve quality but increase cost/latency. We propose learned policies that set best_of and cascade depth per‑artifact, using trace features and outcome supervision to minimize $/success at fixed QoS.

## Research Questions / Hypotheses
- H1: Per‑artifact policies outperform fixed best_of and static cascades for cost‑adjusted quality.
- H2: Lightweight predictors (logistic/gradient boosting) are sufficient given rich trace features.
- H3: Policies remain robust across moderate model/version shifts.

## Experiment Sketch
- Generate datasets with varying difficulty; run with multiple best_of and cascade configurations; label outcomes.
- Train policy to choose parameters from features (artifact type, prior failures, confidence signals); evaluate cost/quality.

## Project Plan (3–5 weeks)
- Week 1: Data collection; define QoS thresholds.
- Week 2: Train/evaluate policies; ablations.
- Week 3: Online A/B with guardrails.

## Metrics
- $/success, P95 latency, success at fixed budget, regression under model drift.

## Value Proposition
- Turns an expensive knob (best_of) into an adaptive control surface with measurable ROI.

## Sources / Further Reading
- Self‑consistency and best‑of‑N for reasoning. https://arxiv.org/abs/2203.11171
- Cost‑quality tradeoffs in LLM pipelines (surveys, empirical studies). https://arxiv.org/abs/2403.09032
