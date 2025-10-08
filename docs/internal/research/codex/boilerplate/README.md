# Research Boilerplate

This boilerplate provides a minimal, reproducible scaffold to run experiments, capture traces, and analyze results.

Common layout:
- `_shared/harness/` – reusable Python harness (tracing + runner)
- `<paper-id>/` – paper-specific workspace with config, scripts, and analysis

Prerequisites:
- Use UV for env management (already configured in this repo)
- Ensure `DEFAULT_MODEL` is set if you run LLM-backed agents; boilerplates use a no‑op engine by default so no API key is required

Quick start (any paper folder):
```bash
cd .flock/research/boilerplate/<paper-id>
uv run python scripts/run.py --config configs/experiment.json
uv run python scripts/analyze.py --db "../../../traces.duckdb"
```

Traces are exported to `.flock/traces.duckdb` via the shared harness. Queries are in `analysis/queries.sql`.
