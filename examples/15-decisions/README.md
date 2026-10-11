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

## 05_compliance_checklist.py

Checks 24 fictional security documents (policies, procedures, audit reports) against 100 controls with one `Checklist`: one request with 100 yes/no questions per document, one decision per document. The data is generated by `data/make_compliance_data.py` (controls written for the example, loosely modelled on ISO/IEC 27001, NIS2 and BSI IT-Grundschutz topics) and comes with ground truth, so the example reports how often the model agrees.

**Key Concepts:**
- `Checklist.from_items("Controls", catalog, question=...)`
- `.consumes(Controls.failed)` (any control "no"), `.consumes(Controls.bcm_06.no)` (one control)
- `.consumes(Controls.ANY, where=...)` for documents with unsure controls

**Run:**
```bash
uv run examples/15-decisions/05_compliance_checklist.py
```

**What You'll See (Microsoft-Decision-1, threshold 0.8):**
```
document                                       outcome   yes   no   ?  agrees  latency
doc_01 Information Security Policy             failed     12   82   6   94/94    995 ms
doc_10 Internal Audit Report: ISMS             failed     29   65   6   90/94    829 ms
doc_16 Backup and Recovery Concept             failed      9   90   1   94/99    554 ms
...
All answers: precision 0.75, recall 1.00 for 'implemented'; 161 answers below the threshold
```

Every document fails some controls: a single policy or procedure never covers the whole catalog.

<p align="center">
  <img alt="A checklist decision: one cell per control" src="../../docs/assets/images/decisions/decision-checklist-card.png" width="460">
</p>

## 06_control_mapping_tournament.py

Maps evidence sentences from the compliance documents to the one control they implement, out of 100, in three ways:

1. **`flat`:** one choice question with all 100 controls.
2. **`tournament`:** one node. Groups of 20 go out in one request, the 3 most probable controls of each group survive, then a final question.
3. **A screening network:** four separate `screen_*` nodes check 25 controls each with yes/no checklists, in parallel. The `ranker` waits for all four, receives the sentence and asks a final choice question about the controls that passed.

```
                  ┌── screen_001_025 ──┐
EvidenceSentence ─┼── screen_026_050 ──┼──> ranker ──> Decision[Control]
                  ├── screen_051_075 ──┤
                  └── screen_076_100 ──┘
```

**Key Concepts:**
- `Choice.from_options(...)` and `Checklist.from_items(...)` from a catalog
- `.decides(Control, tournament=Tournament(group_size=20, keep=3))`
- `.consumes(*(screen.ANY for screen in SCREENS))`: wait for every screen's decision about the same sentence
- `.decides(Control, options=passes)`: a final question about the passes only
- `Flock(decision_model=..., decision_rate_limit="100/min")`: one model and one request budget for every decider (eight requests per sentence stay within the deployment's 100 per minute; HTTP 429s from other clients are retried)

**Run:**
```bash
uv run examples/15-decisions/06_control_mapping_tournament.py
```

**What You'll See (Microsoft-Decision-1):**
```
contender      right    median  requests
flat          10/10     182 ms         1
tournament    10/10     388 ms         2
network       10/10     441 ms         5

Right control among the tournament's finalists: 10/10
Right control among the network's passes: 10/10 (median 5 passes per sentence)
```

The default Microsoft-Decision-1 deployment allows 100 requests per minute; this example sends eight per sentence.

<p align="center">
  <img alt="A screening network: four screens and a ranker" src="../../docs/assets/images/decisions/decision-network-agent-view.png" width="800">
</p>

## 07_escalation.py

Sorts the 100 arXiv abstracts with a cascade: Microsoft-Decision-1 answers first, and papers it is not sure about (below 0.9 or refused) go to OpenAI's `gpt-6-luna`. Papers still unsure after the last tier park in an `inbox` (`ResearchField.UNSURE`). The report lists how many papers each tier answered and how often it agrees with arXiv, then every escalated paper with its trail.

**Key Concepts:**
- `.decides(ResearchField, model=TIERS[0], escalate=TIERS[1:], threshold=0.9)`
- `decision.tier` (0 is `model=`) and `decision.attempts` (the earlier tiers' answers)
- Only unsure questions, or unsure checklist items, go up

**Run:**
```bash
# AZURE_API_BASE, AZURE_API_KEY and OPENAI_API_KEY set
uv run examples/15-decisions/07_escalation.py
```

Set `USE_DASHBOARD = True` to watch the decisions arrive; escalated ones show their trail.

**What You'll See (2026-10-11):**
```
tier  model                  answered   agree
0     azure/decision-1             82      76
1     openai/gpt-6-luna            12      10
      UNSURE (inbox)                6

118 requests for 100 papers; the last tier was asked 18 times.

Escalated papers:
  One Block, Multiple Depths: Recurrent Vision Transformers   arXiv computer_vision
      microsoft-decision-1: machine_learning 0.56 → gpt-6-luna: computer_vision 1.00
  ...
```

## 08_voting.py

Three decision models (Microsoft-Decision-1, Jev, `gpt-6-luna`) sort the 100 arXiv abstracts by a vote. Papers the vote does not settle park in an `inbox` (`ResearchField.UNSURE`). The decisions record every model's answer, so the report shows each model on its own next to the ensemble, then every paper the models disagree about.

**Key Concepts:**
- `.decides(ResearchField, models=MODELS, vote=VOTE, threshold=0.8)`
- `vote="majority"` (more than half of the models give the same firm answer), `"unanimous"` or `"mean"` (threshold on the mean probabilities)
- `decision.votes` (every model's answer) and `decision.probabilities` (the mean)

**Run:**
```bash
# AZURE_API_BASE, AZURE_API_KEY, JEV_API_KEY and OPENAI_API_KEY set
uv run examples/15-decisions/08_voting.py
VOTE=unanimous uv run examples/15-decisions/08_voting.py
```

Set `USE_DASHBOARD = True` to watch the decisions arrive with their votes.

**What You'll See (2026-10-11, majority):**
```
                        firm   agree
azure/decision-1          87      81
jev/jev-latest            89      82
openai/gpt-6-luna         95      91
vote: majority            89      84
UNSURE (inbox)            11

Papers the models disagree about:
  Prediction-Powered Data Fusion for Treatment Effect Estima  arXiv machine_learning
      microsoft-decision-1: economics · jev-1.13.0: machine_learning · gpt-6-luna: machine_learning → machine_learning
  OneSearch-VL: Unified Multimodal Deep Research Agent for I  arXiv computer_vision
      microsoft-decision-1: unsure · jev-1.13.0: unsure · gpt-6-luna: computer_vision → UNSURE
  ...
```

With `VOTE=unanimous`, 80 papers are firm and 78 of them agree with arXiv; with `VOTE=mean`, 84 and 81.

## 09_shadow.py

Microsoft-Decision-1 sorts the 100 arXiv abstracts live while OpenAI's `gpt-6-luna` runs in the shadow: it answers every paper too, its answer is recorded in the decision, and it routes nothing. The report compares both on the same papers and lists the papers the shadow would have routed differently.

**Key Concepts:**
- `.decides(ResearchField, model=LIVE, shadow=SHADOW, threshold=0.8)`
- `decision.shadow`: the shadow's choice under the same threshold, probabilities and latency, or its error
- A failing shadow never fails the live decision

**Run:**
```bash
# AZURE_API_BASE, AZURE_API_KEY and OPENAI_API_KEY set
uv run examples/15-decisions/09_shadow.py
```

Set `USE_DASHBOARD = True` to watch the decider count how often the shadow agrees.

**What You'll See (2026-10-11):**
```
                            firm   agree       median
live   azure/decision-1       88      82       166 ms
shadow openai/gpt-6-luna      95      91       140 ms

The shadow would have routed 86 of 100 papers the same way.

Papers the shadow would have routed differently:
  Prediction-Powered Data Fusion for Treatment Effect Estima  arXiv machine_learning
      live: economics · shadow: machine_learning
  What 30,000 Hours of Ego-centric Video Does Not Teach       arXiv computer_vision
      live: UNSURE · shadow: computer_vision
  ...
```
