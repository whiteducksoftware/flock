# 15-decisions: Decision Models

Decision models (TypeSafe Jev, Cloudflare Clef, Microsoft-Decision-1) answer a typed question with a probability for every option of a closed set, without generating text. Flock uses them to route workflows: one agent decides, other agents subscribe to an option.

Guide: [docs/guides/decisions.md](../../docs/guides/decisions.md)

## 01_ticket_triage.py

Routes support tickets to billing, shipping or tech support. Tickets the decision model is not sure about go to a supervisor.

**Key Concepts:**
- `class Route(Choice)`: options as attributes, the docstring is the question
- `.decides(Route, model=..., threshold=0.8)` on the deciding agent
- `.consumes(Route.billing)` and `.consumes(Route.UNSURE)` downstream; the team agents receive the ticket itself

**Run with a local Clef model:**
```bash
llama serve -m Clef-Flash-Q8_0.gguf -b 4096 -ub 4096 -ngl 99   # separate terminal
uv run examples/15-decisions/01_ticket_triage.py
```

**Run with Jev:**
```bash
export JEV_API_KEY=...
DEFAULT_DECISION_MODEL=jev/jev-latest uv run examples/15-decisions/01_ticket_triage.py
```

The team agents write their replies with `DEFAULT_MODEL`.

**What You'll See:**
```
Charged twice            → billing  [billing 0.97  tech 0.01  shipping 0.01]
Parcel missing           → shipping [shipping 0.99  billing 0.01  tech 0.01]
App crash                → tech     [tech 0.99  billing 0.01  shipping 0.01]
Refund for broken item   → UNSURE   [billing 0.53  shipping 0.31  tech 0.16]
```
