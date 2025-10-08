# Adversarial Schemas & Structured Generation Safety

Score: 8.3 / 10

## Abstract
Structured decoding (JSON Schema/grammar) improves reliability but can introduce new attack surfaces (e.g., adversarial schemas, coercing unsafe content into allowed fields). We investigate schema‑level attacks and blackboard‑level mitigations (linting, quarantines, policy checks at publish()).

## Research Questions / Hypotheses
- H1: Certain schema patterns elevate risk (overly permissive enums, free‑text in sensitive fields).
- H2: Pre‑publish schema linting and policy checks reduce unsafe outputs without high false positives.
- H3: Trace‑linked quarantines aid rapid triage and fix loops.

## Experiment Sketch
- Curate risky schema patterns; generate adversarial prompts; run models with structured outputs.
- Add Flock middleware: schema lints, deny rules, quarantine artifacts; measure blocked violations vs false positives.

## Project Plan (3–5 weeks)
- Week 1: Attack taxonomy + fixtures.
- Week 2: Implement lints/quarantine; evaluate on tasks (e.g., web agents with sensitive topics).
- Week 3: Reporting + remediation playbook.

## Metrics
- Violation rate reduction, FP rate, latency overhead.

## Value Proposition
- Balanced perspective: structured outputs are powerful but need governance; shows Flock can enforce it.

## Sources / Further Reading
- OpenAI Structured Outputs overview. https://openai.com/index/introducing-structured-outputs-in-the-api/
- ST‑WebAgentBench (safety for web agents) for risky scenario design. https://osf.io/preprints/osf/6xkse
