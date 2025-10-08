# Contract‑First Reliability Under Model Upgrades

Score: 9.6 / 10

## Abstract
Modern agent frameworks often encode behavior in long prompts or ad‑hoc schemas, leading to breakage when model families change. Flock’s “typed artifacts as contracts” approach uses Pydantic models and structured decoding so that the data contract, not prompt phrasing, defines coordination. This study quantifies reliability and cost/latency impacts of schema‑first orchestration across model upgrades (e.g., GPT‑4o variants and open‑weights successors), comparing against prompt‑centric graphs.

## Research Questions / Hypotheses
- H1: Contract‑first (typed artifacts + constrained decoding) yields higher valid‑schema rates under model version changes than prompt‑only baselines.
- H2: Contract‑first reduces downstream parse failures and recovery work (fewer hotfixes) after upgrades.
- H3: With identical tasks, overall cost/latency is competitive due to fewer retries and cleaner failure modes.

## Experiment Sketch
- Tasks: code review, bug triage, and web‑agent subtasks with structured outputs.
- Systems compared: Flock (typed artifacts + structured outputs) vs LangGraph/CrewAI/AutoGen flavors with prompt‑only JSON.
- Models: at least two distinct minor version upgrades per provider (e.g., GPT‑4o older vs newer) and one cross‑provider swap.
- Measure across N=1000 runs per task/model: valid‑schema rate, downstream parse errors, success, retries, tokens, P50/P95 latency, $ cost.
- Ablations: disable structure (free‑form) vs enable JSON schema; vary temperature; degrade/perturb schema to simulate drift.

## Project Plan (4–6 weeks)
- Week 1: Implement unified harness; define three task families and ground‑truth validators.
- Week 2: Baseline runs; record traces (OpenTelemetry→DuckDB) and artifact validity.
- Week 3: Upgrade models; rerun; compute deltas and failure taxonomies.
- Week 4: Write report; produce plots and a 2‑min demo video; artifact dataset release.
- Optional: Add open‑weights models and constrained decoding libraries.

## Metrics
- Primary: Valid‑to‑schema rate; E2E success.
- Secondary: Retry count, token cost, P50/P95 latency, incident rate after upgrades.

## Value Proposition
- Evidence that Flock’s schema‑as‑instruction improves robustness when models change.
- Concrete reliability curves that product teams and platform owners care about.

## Sources / Further Reading
- OpenAI Structured Outputs: JSON Schema‑based decoding and guarantees. https://openai.com/index/introducing-structured-outputs-in-the-api/
- LangGraph docs (graph‑based orchestration). https://langchain-ai.github.io/langgraph/
- CrewAI overview. https://docs.crewai.com/
- AutoGen docs. https://microsoft.github.io/autogen/
- Classic blackboard architectures (Nii, 1986/1994). https://ojs.aaai.org/aimagazine/index.php/aimagazine/article/view/550
- OpenTelemetry + DuckDB for trace analytics (methodology). https://opentelemetry.io/
- DuckDB (embedded analytical database). https://duckdb.org/
