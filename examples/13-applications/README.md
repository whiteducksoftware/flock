# 13 — Applications: run Flock behind your own host

`FlockApplication` turns a factory that builds a configured `Flock` into a
transport-independent execution API: typed input, an explicit output
contract, per-workflow isolation, incremental outputs and one terminal
result. See the [Applications guide](../../docs/guides/applications.md).

| Example | What it shows |
|---|---|
| `01_worker.py` | Queue-worker style jobs, streaming outputs, concurrent principals |
| `02_starlette_sse.py` | Your own ASGI endpoint streaming Server-Sent Events |

Both use deterministic engines from `incident_app.py`, so no API key is needed.
For Microsoft Foundry hosted agents, see [`../14-foundry`](../14-foundry/) (`flock-core[foundry]`).
