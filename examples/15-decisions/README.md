# 15-decisions: Decision Models

Decision models (TypeSafe Jev, Cloudflare Clef, Microsoft-Decision-1) answer a typed question with a probability for every option of a closed set, without generating text. Flock uses them to route workflows: one agent decides, other agents subscribe to an option.

Guide: [docs/guides/decisions.md](../../docs/guides/decisions.md)

## 01_ticket_triage.py

Routes support tickets to billing, shipping or tech support. Tickets the decision model is not sure about go to a supervisor.

**Key Concepts:**
- `class Route(Choice)`: options as attributes, the docstring is the question
- `.decides(Route, model=..., threshold=0.8)` on the deciding agent
- `.consumes(Route.billing)` and `.consumes(Route.UNSURE)` downstream; the team agents receive the ticket itself

**Run with Microsoft-Decision-1 on Azure AI Foundry (default):**
```bash
# AZURE_API_BASE and AZURE_API_KEY set (deployment decision-1)
uv run examples/15-decisions/01_ticket_triage.py
```

**Run with another decision model:**
```bash
DEFAULT_DECISION_MODEL=openai/gpt-6-luna uv run examples/15-decisions/01_ticket_triage.py
DEFAULT_DECISION_MODEL=jev/jev-latest uv run examples/15-decisions/01_ticket_triage.py   # JEV_API_KEY

# local Clef model via llama.cpp (separate terminal: llama serve -m Clef-Flash-Q8_0.gguf -b 4096 -ub 4096 -ngl 99)
DEFAULT_DECISION_MODEL=local/clef-flash uv run examples/15-decisions/01_ticket_triage.py
```

The team agents write their replies with `DEFAULT_MODEL`.

**What You'll See:**
```
Charged twice            → billing  [billing 0.97  tech 0.01  shipping 0.01]
Parcel missing           → shipping [shipping 0.99  billing 0.01  tech 0.01]
App crash                → tech     [tech 0.99  billing 0.01  shipping 0.01]
Refund for broken item   → UNSURE   [billing 0.53  shipping 0.31  tech 0.16]
```

## 02_arxiv_race.py

A race on 100 recent arXiv abstracts (`data/arxiv_abstracts.json`, 18 categories, arXiv metadata under CC0): one LLM agent and one decision agent per configured decision model sort every paper into one of nine research fields at the same time. Every agent works one paper at a time. Live progress bars show the race; the report shows total time, time per paper and agreement with arXiv's primary category, plus the papers where anyone disagreed with arXiv.

By default the LLM races Microsoft-Decision-1 on Azure AI Foundry (`AZURE_API_BASE`, `AZURE_API_KEY`). Uncomment more entries in `DECISION_MODELS` to add OpenAI Decisions, Jev or a local Clef model; models without keys or without a reachable server are skipped after a warm-up request.

**Key Concepts:**
- The same `Choice` drives several deciders; each publishes its own `Decision`
- `DSPyEngine(enable_context=False)`: Flock's default context is everything on the blackboard an agent may read, here all papers and every contender's answers so far. The flag keeps the LLM's prompt to the paper it consumes; decision agents decide on their input only

**Run:**
```bash
uv run examples/15-decisions/02_arxiv_race.py
```

**One run with every contender enabled (2026-10-10, local model on an RTX 4090):**

| Contender | Total | Per paper | Agrees with arXiv |
|---|---|---|---|
| LLM openai/gpt-4.1 | 58.3 s | 583 ms | 88/100 |
| Decision local/clef-flash (Q8_0) | 8.5 s | 85 ms | 91/100 |
| Decision openai/gpt-6-luna | 17.2 s | 172 ms | 95/100 |
| Decision azure/decision-1 | 17.8 s | 178 ms | 90/100 |
| Decision jev/jev-latest | 25.0 s | 250 ms | 88/100 |

Hosted latencies include the network round trip from the caller. arXiv's primary category is one label per paper; many disagreements are papers that sit between two fields.
