# 15-decisions: Decision Models

Decision models (TypeSafe Jev, Cloudflare Clef, Microsoft-Decision-1, OpenAI Decisions) answer typed questions (one of N options, yes/no, ordered scales) with a probability for every answer, without generating text. Flock uses them to route workflows: one agent decides, other agents subscribe to an option.

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

## 03_color_sorter.py

A decision agent sorts generated shapes into color bins by looking at their images. Orange and purple shapes sit between two bins: `gpt-6-luna` returns p = 1.00 for pure colors and 0.85-0.95 for the in-between ones, so a threshold of 0.97 sends those to an `inspector` (UNSURE).

**Key Concepts:**
- `flock.Image` fields (`Image.from_pil`, `Image.from_file`, `Image.from_bytes`)
- An image-capable decision model (`IMAGE_DECISION_MODEL`, default `openai/gpt-6-luna`; Microsoft-Decision-1 and Jev accept text only)
- Bin agents without an LLM; only the decision model is called

**Run:**
```bash
uv run examples/15-decisions/03_color_sorter.py
```

Set `USE_DASHBOARD = True` to watch the decider's option lanes fill with thumbnails, one shape per second.

<p align="center">
  <img alt="The color sorter's option lanes filling in the dashboard" src="../../docs/assets/images/decisions/decision-lanes.gif" width="360">
</p>

## 04_question_types.py

One decider asks three questions about every support ticket in a single request: which team (`Choice`), is it urgent (`YesNo`) and how angry is the customer (`Scale`). Handlers subscribe to the answers they need; they only log, so the decision model is the only model called.

**Key Concepts:**
- `class Urgent(YesNo)` and `class Anger(Scale)` (levels lowest first)
- `.decides(Team, Urgent, Anger)`: one request, one decision per question
- `.consumes(Urgent.yes)` and `.consumes(Anger.angry.or_higher)` (probability-weighted score at least "angry")

**Run:**
```bash
uv run examples/15-decisions/04_question_types.py
```

**What You'll See (Microsoft-Decision-1):**
```
ticket                               Team      Urgent   Anger
Charged twice AGAIN                  billing   yes      furious (3.0)
Dark mode request                    tech      no       calm (0.0)
Can't log in before my demo          tech      yes      UNSURE (1.7)
Invoice address                      billing   no       calm (0.0)
App deleted my notes                 tech      yes      angry (2.0)
Weird charge after the app crashed   billing   yes      UNSURE (0.7)
```

Set `USE_DASHBOARD = True` to watch the decider fill its three questions in the dashboard.

<p align="center">
  <img alt="A decider asking a choice, a yes/no and a scale question" src="../../docs/assets/images/decisions/decision-types-agent-view.png" width="800">
</p>
