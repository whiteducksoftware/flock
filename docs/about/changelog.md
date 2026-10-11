---
title: Changelog
description: Recent changes, updates, and release history for Flock
tags:
  - changelog
  - releases
  - history
search:
  boost: 1.2
---

# Changelog

## [Unreleased]

### 🎉 New Features

- **Agent nodes carry their subscription groups and last error** (0.5.781, #585, prerequisite of #560) - Agent nodes in the graph snapshot carry `subscriptionGroups` (each subscription's types, so the dashboard can label an AND gate or a join) and, while the agent's status is `error`, `lastError` with the type, message, time, correlation ID and run of its latest failed run. The run registry keeps the error type, and `GET /api/agents/{name}/runs` reports it as `error_type`.
- **Engine tag for the dashboard's agent cards** (0.5.780, #583, prerequisite of #560) - `EngineComponent.kind` is an engine's short label for the dashboard: `DSPyEngine` is `"LLM"`, `OpenClawEngine` is `"OpenClaw"`, and a custom engine sets `kind = "..."` (none means no tag). Agent nodes in the graph snapshot carry it as `engineTag`, an agent without engines gets the default DSPy engine's, and a producer that is no agent (`external`) gets `"source"`. The dashboard demo's scripted replies are tagged `"LLM"`. See [EngineComponent](../guides/components.md#enginecomponent-replacing-the-execution-engine).
- **Artifact activity histogram** (0.5.771, #572, prerequisite of #557) - `GET /api/v1/artifacts/histogram` returns the artifacts and workflow errors per time bucket for the filters of the artifact list (`from`/`to`, the last hour by default, and 1 to 500 `buckets`), counting only what the caller may see. Stores get `artifact_histogram(filters, buckets=)`: SQLite groups in SQL, over a new index on `created_at`, so a range reads only its own rows; the in-memory and Dapr stores count in Python. The dashboard rework's timeline dock draws it.
- **Token usage and cost per run** (0.5.770, #571, prerequisite of #557) - Every agent run reports its `prompt_tokens`, `completion_tokens`, `tokens_used`, `usage` per model and `cost_usd` in its metrics, which reach the dashboard's Run Status and the run's trace (`flock.usage.tokens`, `flock.usage.cost_usd`). The DSPy engine tracks the usage LiteLLM reports, also when streaming; decision agents count the input tokens of each request once, across escalation tiers, votes, sections and the shadow. Costs come from LiteLLM's price table, and `Flock(model_prices={"azure/decision-1": (0.5, 0.0)})` prices the models it does not know (USD per million tokens); a run with an unpriced model reports its tokens and no cost, and a failed run the requests it made. Custom engines report usage with `flock.utils.usage.report_usage()` or in `EvalResult.metrics["usage"]`, which accepts nested values. `GET /api/agents/{name}/runs`, which returned an empty list until now, lists the agent's runs from the dashboard's event collector, newest first, so the dashboard's Run Status shows them (dashboard 0.1.34: an unpriced run shows no cost, an active run no duration yet); run durations use the monotonic clock. The dashboard demo reports tokens and costs at demo prices. See [Token usage and cost](../reference/configuration.md#token-usage-and-cost).
- **Dashboard demo without API keys** (#570) - `examples/04-misc/10_dashboard_triage_demo.py` runs the ticket triage of the dashboard design: decisions from a `FakeDecider` that takes a moment (some tickets stay `UNSURE` for review), team replies streamed token by token by a scripted engine, an AND gate, a join, a batch, a timer and an agent that fails every third time. `--port` serves a second dashboard for A/B comparisons.
- **Kingfisher milestone: a new CLI banner and `flock-flow --about`** (0.5.760, #555) - The milestone after "Raven" is named for the decision models: the kingfisher sits still, watches the water and dives only when it is sure, as a decision model answers firmly above its threshold and stays `UNSURE` below it. The banner is a formation of birds shaped like a prompt (`>`) in front of a compact FLOCK wordmark, with the version and milestone, a tagline and the model; it replaces the emoji box, whose bottom border the version pushed out of line. `flock-flow --about` shows the kingfisher as a colored half-block sprite and what it stands for, and `python -m flock` runs the CLI. The docs now call the CLI by its installed name, `flock-flow` (`flock` is util-linux's file-locking tool), e.g. `flock-flow decisions calibrate DB`.
- **Calibrating decision thresholds** (0.5.757, #542, completes #474) - `calibrate(decisions, labels, target_precision=0.95, min_support=5)` (`flock.decisions.calibration`) suggests per decider and question, and per checklist item, the lowest threshold whose firm answers reach the target precision, with its precision and coverage (labels per artifact and question); `labels_from_reviews()` makes human reviews labels, and `flock-flow decisions calibrate DB` prints the suggestions for a SQLite store. `.decides(..., item_thresholds={item: threshold})` gives checklist items their own threshold (`"Controls.mfa"` when item names repeat), and the dashboard names how many a decider has. `examples/15-decisions/14_calibration.py` calibrates on half of the compliance documents and measures on the other half: precision of "shown" 0.76 → 0.80, recall 0.99 → 0.90, almost three times as many unsure answers; 12 labelled documents per control are too few for the target. Escalating and voting deciders get no suggestion (a note says why); decisions record the decider's `mode` (`single`, `escalation`, `ensemble`) and the item thresholds that applied, and the CLI prints thresholds exactly. See [Calibrating thresholds](../guides/decisions.md#calibrating-thresholds). Frontend 0.1.33.
- **Human review of decisions** (0.5.756, #540, part of #474) - `await flock.review(decision_id, choice="tech", reviewer="lead")` publishes a person's answer as a decision of the same question about the same subject (probability 1.0, `model` and producer the reviewer, `review_of` the reviewed decision, the original's correlation and visibility), so it routes like any other decision; without `choice`, the best guess is confirmed. Choice, yes/no and scale decisions can be reviewed. `POST /api/control/decisions/{id}/review` does the same over the control API, and the dashboard shows review buttons on unsure decisions and the review on reviewed ones. `examples/15-decisions/13_human_review.py` routes the reviewed tickets to the chosen teams. See [Human review](../guides/decisions.md#human-review). Frontend 0.1.32.
- **Long documents in sections** (0.5.755, #538, part of #474) - `.decides(Controls, sections=Sections(field="text", max_chars=4000))` splits a text field at paragraph boundaries and asks every question about each section. A checklist item keeps the section with the most probable yes (yes if any section shows it), other questions the most confident section. Decisions record `sections`: the field, the sections' spans and `answered_by`, the section per answer. Works with `escalate=` and `shadow=`. The dashboard names a decision's sections and the answering section. `examples/15-decisions/12_long_documents.py` shows where each control is shown, and that on manuals that fit, the whole is more precise (0.87 against 0.75 with 51 instead of 12 requests). See [Long documents in sections](../guides/decisions.md#long-documents-in-sections). Frontend 0.1.31.
- **Coverage: checklist results across artifacts** (0.5.754, #536, part of #474) - `.consumes(Controls.ANY).aggregates(by="organisation", combine="any")` combines a checklist's decisions per group of decided artifacts and publishes `Coverage.of(Controls)` (`flock.decisions.coverage`) after every decision: combined `results` per item, an outcome, `evidence` (the artifacts that showed each item), `subject_ids`, `decision_ids` and a `revision` (the highest per group is current, whatever order coverages were stored in). `combine="any"` counts an item once any artifact shows it, `"all"` only if every artifact does. Groups are also filled from the agent's context (with the default provider, all visible decisions, so a restart with a persistent store recovers them), updates run one at a time, and coverage keeps the group's visibility (or `visibility=`). The dashboard counts an aggregating agent's groups by outcome and shows a coverage as a checklist grid. `examples/15-decisions/11_coverage.py`: per organisation, "shown" has recall 0.99 and precision 0.78 against the ground truth. See [Coverage across artifacts](../guides/decisions.md#coverage-across-artifacts). Frontend 0.1.30.
- **Explain decisions on demand** (0.5.753, #534, part of #474) - `.consumes(Route.UNSURE).explains(model="openai/gpt-4.1")` makes an agent that lets an LLM explain each decision it receives. The LLM gets the decided artifact and the decision (question, options and criteria, probabilities, threshold, checklist results) and writes an `Explanation` (`flock.decisions.explain`): why the decision came out this way, citing the input, and what would settle it. Flock links it to the decisions (`decision_ids`, `questions`) and subjects (`subject_ids`), records the LLM, and keeps the subjects' visibility (or `visibility=` on `.explains()`). Decisions now record custom `instructions`, so the explanation describes the question that was actually asked. The dashboard shows explanations as text and an explained decision's explanation on its card. `examples/15-decisions/10_explain.py`: of eight tickets, Microsoft-Decision-1 was unsure about one at threshold 0.95, and the LLM ran once. See [Explain on demand](../guides/decisions.md#explain-on-demand). Frontend 0.1.29.
- **Shadow mode for decision models** (0.5.752, #532, part of #474) - `.decides(ResearchField, model="azure/decision-1", shadow="openai/gpt-6-luna")` lets a candidate model answer every question too, concurrently. Its answer (choice under the same threshold, best guess, probabilities, latency; outcome and results for checklists) is recorded in the decision's `shadow` and never routes, so a model switch can be evaluated on live traffic. A failing shadow records its error and never fails the decision; one slower than `shadow_timeout` (default 10 s after the live answer) is cancelled and recorded as a timeout. The dashboard shows how often the shadow agrees on the decider and the shadow's answer on every decision. `examples/15-decisions/09_shadow.py`: with Microsoft-Decision-1 live, `gpt-6-luna` would have routed 86 of 100 arXiv abstracts the same way. See [Shadow mode](../guides/decisions.md#shadow-mode). Frontend 0.1.28.
- **Ensembles and voting for decision models** (0.5.751, #530, part of #474) - `.decides(ResearchField, models=["azure/decision-1", "jev/jev-latest", "openai/gpt-6-luna"], vote="majority", threshold=0.8)` asks every model about every question, concurrently, and votes: `majority` (default) needs more than half of the models to give the same firm answer, `unanimous` all of them, and `mean` applies the threshold to the mean probabilities. A refusal is no vote; checklist items are voted one by one. Decisions record every model's answer in `votes`, and their `probabilities` are the mean over the models that answered; disagreement routes to `UNSURE`. The dashboard shows a decider's vote and models and a decision's votes. `examples/15-decisions/08_voting.py` compares each model with the ensemble on 100 arXiv abstracts: the unanimous vote sorted 80 papers with 78 agreeing with arXiv, `gpt-6-luna` alone 95 with 91. See [Ensembles and voting](../guides/decisions.md#ensembles-and-voting). Frontend 0.1.27.
- **Escalation cascades for decision models** (0.5.750, #528, part of #474) - `.decides(ResearchField, model="azure/decision-1", escalate=["openai/gpt-6-luna"], threshold=0.9)` asks the next model about every question the previous one was not sure about (below the threshold or refused); only those questions, and of a checklist only the unsure items, go up. Decisions record the `tier` that answered and the earlier `attempts`; still unsure after the last tier, a decision routes to `UNSURE` as before. Every tier must accept images when the inputs hold one, and `escalate=` cannot be combined with `tournament=` yet. The dashboard shows a decider's cascade and an escalated decision's trail. `examples/15-decisions/07_escalation.py` sorts 100 arXiv abstracts: Microsoft-Decision-1 answered 82, `gpt-6-luna` 12 of the other 18, 6 went to `UNSURE`. See [Escalation cascades](../guides/decisions.md#escalation-cascades). Frontend 0.1.26.
- **Image limits on every publish path, and an Images guide** (0.5.743, #513, completes the scope agreed for #464) - every artifact's inline image data is checked against the limits of `Image` fields (20 MB, 50 million pixels) before it is stored, so `Artifact` objects published directly, component publishes and models changed after creation cannot bypass them; models, dicts, REST JSON, uploads and the dashboard already enforced them. The new [Images guide](../guides/images.md) documents creating images, the limits, every publish path, agents and decision models, dashboard thumbnails and the security rules (no fetching, checked uploads, visibility, including the known WebSocket and graph gaps tracked in #431 and #432). Tests cover the limits on each path and that private image data and thumbnails stay private over the REST API.
- **Image thumbnails across the dashboard, full images on demand** (0.5.742, #512, part of #464) - the message detail window, message history and historical blackboard show image thumbnails (field, type, size); clicking one loads the full image through `/api/v1/artifacts/{id}`, which applies visibility. `GET /api/v1/artifacts` and `/api/v1/artifacts/{id}` accept `images=thumbnails` (description in the payload plus an `images` list with 160 px previews; default stays full). WebSocket `message_published` events and the message history carry descriptions and thumbnails instead of full image data. Frontend 0.1.25.
- **Publish images from the dashboard and the REST API** (0.5.741, #511, part of #464) - the dashboard publish panel shows a picture picker with previews for `Image` and `list[Image]` fields; pictures are scaled to 1024 px and re-encoded in the browser, and the server re-encodes dashboard images again (format, size and pixel checks, metadata dropped). Validation errors from the dashboard publish return 422 again instead of 500. `POST /api/v1/artifacts/upload` takes `multipart/form-data` with one file part per `Image` field, named after the field or its alias (JPEG, PNG, GIF, WebP, BMP; at most 20 files per request, 20 MB and 50 million pixels per file, checked before parsing and decoding) and re-encodes each file like `Image.from_bytes()`. The JSON endpoint keeps accepting data URLs. `Image` schemas carry `"x-flock-image": true`, and `python-multipart` is now a direct dependency. Frontend 0.1.24.
- **LLM agents see images** (0.5.740, #510, part of #464) - `flock.Image` fields of consumed artifacts reach the model as pictures through the DSPy engine (`dspy.Image`), at any depth (`Image | None`, `list[Image]`, tuples, nested and self-referencing models) and in batches and joins. Images in conversation context are described (`🖼 image/jpeg · 42 KB`) instead of inlined as base64. Pictures sent to an OpenAI API model that LiteLLM lists as text-only fail before any request with an error naming the image fields. Example: `examples/01-getting-started/19_image_agent.py`.
- **Rate limits for decision models** - HTTP decision providers retry HTTP 429 and 503 up to 7 times. The wait is the provider's advice (`retry-after-ms`, `Retry-After` or `x-ratelimit-reset-requests`; seconds on Azure, durations such as `6m0s` on OpenAI) plus an exponential backoff with jitter, at most 60 s per wait, so that a burst of rejected requests does not come back at once. `Flock(decision_rate_limit="100/min")` adds a request budget per decision model: all deciders that use the same model share it, and requests over the budget wait for a free slot instead of failing. See [Rate limits](../guides/decisions.md#rate-limits).
- **Decision networks** - several handles in one `.consumes()` mean AND about the same subject: `.consumes(Route.billing, Urgent.yes)` or `.consumes(*(screen.ANY for screen in screens))` runs once a matching decision for every handle has arrived about the same subject (a join on `subject_ids`), delivers the subject once and puts all decisions into `ctx.decisions`. `.decides(question, options=callable)` restricts a Choice or Checklist to options chosen at runtime and records them as `candidates`. Together they build screening networks: parallel screen nodes over slices of a catalog and a ranker over their passes. `examples/15-decisions/06_control_mapping_tournament.py` compares a single choice, a tournament and a screening network on the same sentences (10/10 each; 182 ms, 388 ms, 441 ms). See [Decision networks](../guides/decisions.md#decision-networks).
- **Tournament bracket view** - every tournament round records its group size and, per group, the top candidates with probabilities (survivors plus the two strongest eliminated options). **⤢ bracket** on a tournament decision opens a full-screen bracket: one column per round, lines from every survivor to the next round, the winner's path highlighted and any option traceable on hover.
- **Tournaments for large choices** - `.decides(Requirement, tournament=Tournament(group_size=20, keep=3))` asks a Choice in rounds: groups of options as separate choice questions in one request, the most probable options of each group survive, then a final question. Choices may now define more than 255 options; they must be asked as a tournament. Decisions record their `rounds` (candidates, groups, refused groups, survivors). The dashboard shows the rounds above the final probabilities and compacts deciders and decisions with many options. `examples/15-decisions/06_control_mapping_tournament.py` maps evidence sentences to one of 100 controls: 25/25 with a single choice at 180 ms and 25/25 with a tournament at 419 ms. See [Decision Models](../guides/decisions.md#tournaments-for-large-choices).
- **Flock-wide decision model** - `Flock("openai/gpt-4.1", decision_model="azure/decision-1")` sets the decision model for every `.decides()` agent of the flock (a model string or a `DecisionProvider`). `model=` on `.decides()` still wins; `DEFAULT_DECISION_MODEL` is the fallback.
- **Checklists for decision models** - `Checklist` asks the same yes/no question for every item of a catalog and publishes one decision per artifact, with `results` (yes / no / UNSURE per item) and an outcome (`failed` if any item is no, `UNSURE` if any is unsure, `passed` otherwise). `Checklist.from_items()` and `Choice.from_options()` build question classes from data. Subscribers use `.consumes(Controls.failed)`, `.consumes(Controls.passed)` or a single item, `.consumes(Controls.bcm_06.no)`. `.decides(..., questions_per_request=100)` splits large question sets into concurrent requests. The dashboard shows checklist deciders with outcomes, a per-item strip and the most frequent gaps, and checklist decisions as a grid of item cells. `examples/15-decisions/05_compliance_checklist.py` checks 24 generated documents against 100 controls: recall 0.99 (an unsure answer counts as missed) and precision 0.75 against ground truth on Microsoft-Decision-1, about 600 ms per document. See [Decision Models](../guides/decisions.md#checklist).
- **Yes/no and scale questions for decision models, several per request** - `YesNo` (systemone `noul`, OpenAI `predicate`) and `Scale` (2-10 ordered levels, systemone and OpenAI `score`) join `Choice`. `.decides(Route, Urgent, Anger)` asks all questions in one request and publishes one decision per question; subscribers use `.consumes(Urgent.yes)`, `.consumes(Anger.angry)` or, on the probability-weighted score, `.consumes(Anger.angry.or_higher)` / `.or_lower`. Decisions carry `kind`, `score` and `refused`: a question the model refuses lands in `UNSURE` with `refused=True` instead of failing. The dashboard draws each question by kind (option bars, a yes/no split bar with the unsure zone, ordered level histograms with the weighted score). Verified live on Microsoft-Decision-1, OpenAI `gpt-6-luna`, TypeSafe Jev and a local Clef model. See [Decision Models](../guides/decisions.md#question-types) and `examples/15-decisions/04_question_types.py`.
- **Images in artifacts and decisions** (`flock.Image`) - an image field holds the picture as a base64 data URL; `Image.from_file()` / `from_bytes()` / `from_pil()` downscale (default 1024 px) and strip EXIF. Decision models that accept images (`openai/`, vision-enabled `local/` servers) receive every `Image` of a decider's inputs; text-only providers refuse them with a clear error. The dashboard shows image thumbnails, lanes of the latest images per decision option, and the decided image next to its probabilities. Pillow is now a base dependency. See [Decision Models](../guides/decisions.md#images) and `examples/15-decisions/03_color_sorter.py`.
- **Decision models** - an agent answers a typed `Choice` question with a decision model (calibrated probabilities over a closed option set, no generated text) and publishes a `Decision`; other agents subscribe to an option and receive the artifact that was decided on:

    ```python
    class Route(Choice):
        """Which team should handle this support ticket?"""
        billing = "Charges, invoices, refunds"
        tech = "Bugs, crashes, login problems"

    flock.agent("triage").consumes(Ticket).decides(Route, model="azure/decision-1", threshold=0.8)
    flock.agent("billing").consumes(Route.billing).publishes(Reply)
    flock.agent("supervisor").consumes(Route.UNSURE).publishes(Reply)
    ```

    Providers: Microsoft-Decision-1 on Azure AI Foundry (`azure/`), OpenAI Decisions (`openai/`), TypeSafe Jev (`jev/`) and any local `/v1/systemone` server such as llama.cpp with a Clef model (`local/`). Decisions inherit their subject's visibility. The dashboard shows decision agents with their options and counts, labels edges by option and renders decision artifacts as probability bars. In `examples/15-decisions/02_arxiv_race.py`, Microsoft-Decision-1 sorts 100 arXiv abstracts into research fields at 169 ms per paper against 598 ms for `gpt-4.1`, agreeing with arXiv's category on 90 papers against 85. See [Decision Models](../guides/decisions.md).

### ⚠️ Changes

- **PyTorch is no longer a dependency.** Semantic subscriptions (`flock-core[semantic]`) compute the same `all-MiniLM-L6-v2` embeddings with [fastembed](https://github.com/qdrant/fastembed) on ONNX Runtime instead of `sentence-transformers`. Similarity scores are identical (450 query/text pairs: largest difference below 0.00001, no decision changed at thresholds 0.3-0.7), so `semantic_match` thresholds keep their meaning. The model (~90 MB) is downloaded on first use to `~/.cache/flock/fastembed` (override with `FASTEMBED_CACHE_PATH`).

    | Fresh install from `uv.lock`, including downloads | Before | Now |
    |---|---|---|
    | `flock-core[semantic]`: environment size | 7.48 GB (140 packages) | 404 MB (117 packages) |
    | `flock-core[semantic]`: install time | 302 s | 10 s |
    | The `semantic` extra on its own | +7.16 GB, +295 s | +86 MB, +2.5 s |
    | Full development environment (all extras and groups) | 8.03 GB, 310 s | 702 MB, 16 s |

    Measured in a fresh `ghcr.io/astral-sh/uv:python3.12-bookworm` container per run (uv 0.9.30, empty cache, same machine and network, one run each). A base install without extras is unchanged (~316 MB, 8 s).

- **Removed: the in-process Hugging Face provider** (`Flock("transformers/<model>")`, extra `flock-core[transformers]`). Run local models in an OpenAI-compatible server (Ollama, llama.cpp, vLLM, LM Studio) and use its model string, e.g. `ollama_chat/qwen3:4b`. See [Local Models](../guides/local-models.md).
- Starlette 1.3 with FastAPI 0.143, MCP Python SDK 1.28.
- `requirements.txt` was removed; dependencies are managed with uv (`pyproject.toml`, `uv.lock`).

### 🐛 Fixes

- **A failed agent stays failed in the dashboard** (#585). The event collector set an agent back to `idle` and broadcast `agent_completed` when a failed run ended, so the dashboard showed the failure only for a moment. A failed run now leaves its agent `error` until it runs again, and only `agent_error` is broadcast.
- **Dashboard keyboard shortcuts work again** (#581). `App` and `DashboardLayout` both registered the shortcuts, so Ctrl+M, Ctrl+Shift+P, Ctrl+Shift+F and Ctrl+, toggled twice and did nothing, and Esc closed two panels per press. The layout registers them once.
- **The publish panel's tests wait for the artifact types** (#578). The panel renders its type select before the types load, and the tests chose a type as soon as the select was there, so they failed at random on slow CI runners (12 of 15 with the types arriving 20 ms later). They now wait for the type's option.
- **Dashboard decisions show their review and explanation, wherever these are** (#550). A decision in the graph showed its review and explanation only when they were in the same view, and an aggregating agent counted each group by the newest coverage revision in view. Reviews, explanations and newer revisions are published later, so filters and the view's limit left them out: a reviewed decision offered its review buttons again, and a group could count with a stale outcome. The graph now loads them from the store, starting at the earliest decision or coverage in view, with the view's visibility filter.
- **The dashboard graph shows the newest artifacts when more than its limit match** (#554). The graph read the first page of its store query, ordered oldest first, so with more than 500 matching artifacts (the default limit) a live dashboard showed the oldest ones and new artifacts appeared only once older ones left the time window. A full view now shows the newest artifacts; `total_artifacts` and `truncated` are unchanged.
- **Decision examples count unsure answers as misses** (#552). `05_compliance_checklist.py`, `11_coverage.py` and `12_long_documents.py` computed recall over firm answers only, so an unsure answer about a shown control was not counted as missed. With the fix, Microsoft-Decision-1 reaches recall 0.99 instead of 1.00 in 05 and 11, and 0.96 (whole manual) and 0.99 (sections) instead of 0.98 and 1.00 in 12; the README, the decisions guide and the examples README quote the new numbers.
- **LLM agents see every input of one type** (#546). An agent consuming several artifacts of one type at once, such as `.consumes(Task, Task)`, received all of them, but the DSPy engine sent only the first to the model. Such inputs are now one list field (`tasks: list[Task]`), as in batches; types that occur once keep their singular field. A fan-out of the input type (`.publishes(Task, fan_out=2)`) is named `output_tasks` instead of replacing the input list; this also fixed batches with such a fan-out.
- **The newest artifacts show in "last N minutes" views** (#547). The dashboard graph and the historical blackboard filtered the time presets up to the clock reading of the request, so an artifact stamped later (a wall clock that stepped back, as WSL2 does every 30 s, a browser clock behind the server's, or a publish racing the request) was left out. The presets now bound the start only; custom ranges keep their end.
- **Models with field aliases work everywhere** (#544). Payloads are stored with `model_dump()` (field names) but were rebuilt by alias, so publishing a model such as `order_id: str = Field(alias="orderId")` raised as soon as an agent subscribed to it, and joins, `get_by_type()` (in-memory, SQLite, Dapr), `EvalInputs.first_as()`/`all_as()`, `.calls()`, output `where=`/`validate=`/dynamic visibility, `FlockApplication` inputs given by field name or as another model, `FlockApplication` outputs and LLM outputs of such types failed; the DSPy engine passed such inputs to the LLM as plain dicts. Payloads are now rebuilt with `model_from_payload()` (`flock.core.artifacts`), which accepts field names and aliases. JSON from REST clients is validated by alias as before.
- **Scripts using the SQLite store exit.** The aiosqlite connection ran on a non-daemon thread, so a process whose `SQLiteBlackboardStore` was never closed hung after `asyncio.run()` returned, and `flock.shutdown()` did not close the store. The connection thread no longer keeps the process alive, and a full `flock.shutdown()` closes a SQLite store, which reconnects if used again. If an agent task outlives `cancel_grace`, the store stays open so the late task cannot reopen it; close it with `await store.close()` once the task has ended. Other stores are not closed.
- **New models work through Azure and gateways too.** When an API rejects `max_tokens` and asks for `max_completion_tokens` (an Azure deployment of `gpt-6-luna`, for example), the DSPy engine retries that request once with `max_completion_tokens` and remembers the model and endpoint for the rest of the process. The retry happens per LM request, so the agent's program and streaming are not re-run; other errors are not retried.
- **Timers and batches conflict in either order.** `.schedule()` rejected an existing batch subscription, but `.schedule().consumes(..., batch=...)` was accepted. Both orders now raise the same `ValueError`.
- **`TimeWindowContextProvider` works.** It compared a naive local `datetime.now()` with the UTC `created_at` of artifacts, so every agent using it failed with `TypeError: can't compare offset-naive and offset-aware datetimes`. The window is now computed in UTC and filtered by the store (`FilterConfig(start=...)`) instead of loading every artifact.
- **SQLite store persists artifacts with datetime fields.** `SQLiteBlackboardStore` wrote payloads with plain `json.dumps`, so any artifact with a `datetime`, `date`, `UUID` or `Decimal` field failed to publish, and scheduled agents never ran because every timer tick carries a `datetime`. Payloads are now encoded the way Pydantic does, as in the Dapr store; such values read back in their JSON form and validate into the model again.
- **Roadmap matches the backlog.** `ROADMAP.md` and the docs roadmap still promised 1.0 for Q4 2025 and listed shipped features as in flight. Both now list what 0.5 offers and summarize the planned work for Q4 2026: the 1.0 release scope and the separately qualified integrations.
- **Scheduling docs and examples match the API.** The scheduling guide, tutorial and example README described timer agents as functions with an `AgentContext` and `ctx.get_artifacts()`, which do not exist, and used `.consumes()` as a context filter. They now show LLM agents, custom engines and `.with_context(...)` for choosing what a timer run sees, and state that times are UTC. Examples 02-05 use context providers instead of `.consumes()`; the one-time reminder uses a UTC datetime (a naive local time fired off by the UTC offset), and the batch processor publishes one aggregate per sensor.
- **New OpenAI models work with the default DSPy engine.** For the OpenAI API (`openai/` without a custom base URL) the engine now sends its token limit as `max_completion_tokens`; `gpt-6-luna` and other new models rejected `max_tokens` with HTTP 400. OpenAI-compatible servers behind `openai/` keep `max_tokens`.
- **Streaming agents report the real error.** DSPy's `streamify` wraps a failure in an anyio TaskGroup, so logs and `WorkflowError` only said "unhandled errors in a TaskGroup (1 sub-exception)". A single wrapped failure is now unwrapped (CLI and dashboard streaming), and the console ends with a red error panel instead of an empty placeholder result.
- **Batching performance test no longer fails on slow CI runners.** It compared the time of 100 batched publishes with a fixed 3,000 ms limit, which branch coverage and slower runners exceeded; it now compares against the same publishes handled one by one in the same run.
- **No more `Type mismatch for field` warnings from DSPy agents.** The DSPy engine passed validated inputs as dicts while the signature types them as Pydantic models; DSPy 3.2 checks this and warned on every run. Inputs are now passed as the validated models; prompts are unchanged.
- **Test runs no longer crash agent output rendering.** A CLI helper test removed `rich` from `sys.modules` without restoring it, so later tests ran with two copies of rich's classes. Rich's own type checks then failed (`Text.append() takes from 2 to 3 positional arguments but 7 were given`), output rendering crashed and agent runs were marked failed in every full run. The test now restores the original modules.
- **No dashboard build in the repository.** The dashboard is built locally on the first `serve(dashboard=True)`; the unused committed build in `src/flock/api/static_files/` and the stale `scripts/build_dashboard.py` were removed. The context-provider guide's redaction example is now a working sketch instead of a link to a removed example.
- **Decision models, review fixes** (found in code review of the decision model PRs before release):
    - Providers reject answers with probabilities that are not finite or outside 0-1, instead of turning them into firm decisions; rounding just outside 0-1 is clamped. Scale scores must be finite and within the levels, since `.or_higher` and `.or_lower` route on them; a refused question has no score and matches no level.
    - A decision agent publishes only its decisions: `.decides()` with `.with_engines()` or `.publishes()` fails in either order. One agent cannot consume a question's handles and its decision type.
    - The dashboard keeps the other inputs of an agent that consumes a decision type directly, and only `UNSURE` (or `X.UNSURE`) edges count as the unsure branch.
    - Checklist items take the more probable answer before the threshold (thresholds below 0.5 no longer turn a 0.45 into `yes`). Option names from catalogs cannot shadow the question class (`__kind__`, `from_items`), and checklist item requests cannot collide with other question names.
    - Tournaments advance a leftover group of one option without a request. `options=` works for catalogs over 255 options (more than 255 runtime candidates without `tournament=` fail), and an empty runtime checklist is not marked refused.
    - Request budgets book a start when it happens (a late wake-up cannot let several requests through) and stay per flock when a provider instance is shared.
    - Images over 20 MB (base64 padding not counted, only canonical base64 accepted) or 50 million pixels are rejected when the artifact is created; the dashboard compacts image data also when no thumbnail can be made.
    - The bracket view is a modal that takes, keeps and returns keyboard focus; checklist cells carry their result as an accessible label.
- **Batch timeouts no longer depend on the wall clock.** `BatchSpec(timeout=...)` measured the elapsed time with `datetime.now()`. When the wall clock stepped back (VM time sync, NTP), batches flushed late and `run_until_idle()` could return before the flush; when it stepped forward (daylight saving), they flushed early. Timeouts now run on the monotonic clock. The timer tests check the waits they ask for instead of elapsed wall time. Both fix intermittent failures of four timing tests.

### 🔒 Security

- Patched vulnerable dependencies: anyio, PyJWT, cryptography, urllib3, python-multipart, Starlette, MCP SDK, tornado, gitpython, fsspec, json-repair, mistune, orjson, pymdown-extensions, soupsieve, virtualenv, bleach, idna, multidict, oauthlib, requests, setuptools, pygments, Jupyter and mkdocs-material dev tooling, and the dashboard's dev tooling (Vitest 4, Vite 7.3.7). Removing PyTorch, Transformers and sentence-transformers closes their advisories as well.
- How dependency alerts are handled, including LiteLLM advisories that only affect the LiteLLM proxy server, is documented in [CONTRIBUTING.md](https://github.com/whiteducksoftware/flock/blob/main/CONTRIBUTING.md).

## [0.5.700] - 2026-10-06

### 🎉 New Features

- **`FlockApplication`** (`flock.application`) - transport-independent execution for hosts: typed input, explicit output contract, one isolated `Flock` per workflow, incremental outputs, one terminal `WorkflowResult` (`succeeded`/`failed`/`cancelled`/`timed_out`), deadlines, cancellation, admission and id-retry protection. See [Applications](../guides/applications.md).
- **Microsoft Foundry hosting** (`flock.integrations.foundry`, install `flock-core[foundry]`) - hosts a `FlockApplication` as a Microsoft Foundry hosted agent via `azure-ai-agentserver-responses` 2.1. See [Foundry hosted agents](../guides/foundry.md).
- `DSPyEngine(max_completion_tokens=...)` for reasoning models that reject `max_tokens`.

### ⚠️ Changes

- OpenTelemetry now requires `>=1.43` (tested with 1.44; required by the Foundry SDK). The legacy `opentelemetry-exporter-jaeger` packages were removed; a `TelemetryConfig` with `jaeger_endpoint` (and the default `enable_jaeger=True`) raises in `setup_tracing()` - export to Jaeger via OTLP.
- `Flock.shutdown()` now cancels in-flight agent tasks (bounded by `cancel_grace`) before closing MCP connections. No new agent work is scheduled during shutdown; if a task outlives the grace period, the instance stays closed for scheduling.
- Scheduled-agent timers start with the first `publish()` as well as with `run_until*()`.
- The trace SQL query endpoint no longer exists; use the remaining trace read endpoints or local DuckDB analysis.

### 🔒 Security

- Removed arbitrary SQL execution from the trace HTTP API and the dashboard: a `SELECT` could read server files through DuckDB table functions despite `read_only=True`. The dashboard keeps Timeline, Statistics, RED Metrics, Dependencies, Configuration and Guide; the SQL tab, editor and CSV export are gone.
- `DSPyEngine` serialization (`model_dump()`, `model_dump_json()`) redacts known credential fields in `lm_kwargs` (`api_key`, `token`, `password`, `authorization`, ...) as `<redacted>`, also in nested values. The original values are still passed to `dspy.LM(...)`.

### 🐛 Fixes

- Orchestrator components are initialized exactly once (previously twice after `add_component()` or timer auto-registration, or when first publishes raced); an `on_initialize` hook may publish without recursing.
- Agent tasks that fail outside the agent run (context building, output persistence) are recorded instead of lost; an agent whose inputs were all deferred is no longer run with empty input.
- `no_output=True` now also silences user-built `DSPyEngine` instances.
- Flock chains to a previously installed `sys.excepthook`.

Releases 0.5.500 to 0.5.610 are described in the [GitHub release notes](https://github.com/whiteducksoftware/flock/releases).

## [0.5.400] - 2026-02-11

### 🎉 New Features

#### 🦞 OpenClaw Integration (Phase 1)
**First-class OpenClaw agent support — use OpenClaw agents as Flock pipeline agents with the same fluent API:**

```python
from flock import Flock
from flock.integrations.openclaw import OpenClawConfig

flock = Flock(openclaw=OpenClawConfig.from_env())
pizza_master = flock.openclaw_agent("codex").consumes(MyPizzaIdea).publishes(Pizza)
```

**Features:**
- **`flock.openclaw_agent()`** — Fluent builder for OpenClaw-backed agents
- **Spawn mode** — Isolated session per invocation, clean context, parallelizable
- **Env-based config** — `OPENCLAW_<ALIAS>_URL` + `OPENCLAW_<ALIAS>_TOKEN` auto-discovery
- **JSON repair** — Automatic extraction and retry for malformed agent output
- **Dashboard badge** — 🦞 OpenClaw agents show an orange lobster badge in the graph UI
- **Zero breaking changes** — All existing Flock semantics (blackboard, visibility, fan-out, conditions) work unchanged

**New files:**
- `src/flock/integrations/openclaw/` — Config, engine, and package exports
- `examples/11-openclaw/` — Three example scripts + README
- `docs/guides/openclaw.md` — Comprehensive integration guide
- `docs/specs/004-openclaw-integration/concept.md` — Full design spec (Phases 1–4)

### 🐛 Fixes

- Dashboard publish form now receives list defaults for artifact fields backed by Pydantic `default_factory` (array defaults are hydrated in artifact type schema responses), so list textareas prefill correctly.

---

## [0.5.30] - 2025-11-07

### 🎉 New Features

#### ⏰ Timer-Based Agent Scheduling
**Schedule agents to execute periodically or at specific times without requiring artifact triggers:**

```python
from datetime import timedelta, time, datetime
from flock import Flock

flock = Flock("openai/gpt-4.1")

# Periodic execution (every 30 seconds)
health_monitor = (
    flock.agent("health_monitor")
    .description("Monitors system health")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)

# Daily execution (5 PM every day)
daily_report = (
    flock.agent("daily_report")
    .schedule(at=time(hour=17, minute=0))
    .publishes(DailyReport)
)

# Cron expression (every weekday at 9 AM UTC)
workday_report = (
    flock.agent("workday_report")
    .schedule(cron="0 9 * * 1-5")  # Mon-Fri at 9 AM
    .publishes(WorkdayReport)
)

# One-time execution at specific datetime
reminder = (
    flock.agent("reminder")
    .schedule(at=datetime(2025, 12, 25, 9, 0))  # Christmas 9 AM
    .publishes(Reminder)
)
```

**Features:**
- **Interval-based scheduling** - Execute at regular intervals (`every=timedelta`)
- **Time-based scheduling** - Execute daily at specific time (`at=time`)
- **DateTime-based scheduling** - One-time execution at specific datetime (`at=datetime`)
- **Cron support** - Full 5-field cron expressions (UTC timezone) with `*`, lists, ranges, steps
- **Initial delay** - Wait before first execution (`after=timedelta`)
- **Repeat limits** - Control execution count (`max_repeats=int`)
- **Timer metadata** - Access `ctx.trigger_type`, `ctx.timer_iteration`, `ctx.fire_time` in agent context
- **Context filtering** - Combine timers with `.consumes()` to filter blackboard context

**Use cases:**
- Periodic monitoring (health checks, system status)
- Scheduled reports (daily summaries, weekly analytics)
- Batch processing (process accumulated data at intervals)
- Cleanup tasks (delete old records, archive data)
- Time-based alerts (check for stale data, missed deadlines)

**Timer Component:**
- `TimerComponent` orchestrator component manages timer tasks and state
- Automatic timer lifecycle management (startup, shutdown, cancellation)
- Timer state tracking (iteration count, last/next fire times)
- Background task management with graceful shutdown

**Documentation:**
- Complete scheduling guide (`docs/guides/scheduling.md`)
- Step-by-step tutorial (`docs/tutorials/scheduled-agents.md`)
- 6 production-ready examples (`examples/10-scheduling/`)

#### 🔧 Server Components Improvements

**Critical Fix: Orchestrator Component Initialization**
- Fixed server startup to ensure orchestrator components (like `TimerComponent`) initialize before HTTP server starts
- Prevents timer scheduling failures in dashboard/server mode
- Ensures all orchestrator components are ready before accepting requests

**Impact:**
- Scheduled agents now work correctly in `flock.serve()` mode
- Timer components initialize properly in CLI and dashboard modes
- No more race conditions between server startup and timer initialization

### 🔧 API Changes

**New Methods:**
- `.schedule(every=timedelta)` - Periodic execution
- `.schedule(at=time)` - Daily execution at specific time
- `.schedule(at=datetime)` - One-time execution at datetime
- `.schedule(cron=str)` - Cron expression scheduling
- `.schedule(after=timedelta)` - Initial delay before first execution
- `.schedule(max_repeats=int)` - Limit number of executions

**New Context Properties (Timer-Triggered Agents):**
- `ctx.trigger_type` - `"timer"` for timer-triggered executions
- `ctx.timer_iteration` - Current iteration count (0, 1, 2, ...)
- `ctx.fire_time` - Datetime when timer fired

**Validation:**
- Scheduled agents must declare `.publishes()` (enforced at agent creation)
- `after >= 0` validation (non-negative initial delay)
- `max_repeats > 0` validation (positive repeat limit)
- Cannot combine `.schedule()` with `.batch()` (mutually exclusive)

### 📚 Documentation

- Added comprehensive timer scheduling guide (`docs/guides/scheduling.md`) - 890+ lines
- Added scheduled agents tutorial (`docs/tutorials/scheduled-agents.md`) - 1,060+ lines
- Added 6 production-ready examples in `examples/10-scheduling/`:
  - `01_simple_health_monitor.py` - Basic periodic monitoring
  - `02_error_log_analyzer.py` - Timer + context filtering pattern
  - `03_daily_report_generator.py` - Daily scheduled reports
  - `04_batch_data_processor.py` - Periodic batch processing
  - `05_one_time_reminder.py` - One-time datetime execution
  - `06_cron_demo.py` - Cron expression examples
- Updated `AGENTS.md` with timer scheduling patterns and best practices

### ✅ Testing

- Added 38 timer component unit tests (`tests/test_timer_component.py`)
- Added integration tests for scheduled agent workflows (`tests/integration/test_scheduled_agents.py`)
- Added timer component registration tests (`tests/test_timer_component_registration.py`)
- Added agent schedule API tests (`tests/test_agent_schedule_api.py`)
- Added timer tick tests (`tests/test_timer_tick.py`)
- Added dashboard graph visualization tests for scheduled agents (`tests/test_dashboard_graph.py`)
- All tests passing with comprehensive coverage

### 🚀 Dependencies

- Added `croniter>=6.0.0` for cron expression parsing
- Added `python-dotenv>=1.2.1` for automatic `.env` file loading
- Added `types-croniter>=6.0.0.20250809` for type hints

### 🐛 Bug Fixes

- Fixed timer scheduling in dashboard mode (orchestrator initialization before server start)
- Fixed duplicate timer task creation (prevented multiple timers for same agent)
- Fixed CLI mode timer support (orchestrator initialization in CLI)
- Fixed frontend TypeScript compilation errors for scheduled agent visualization
- Fixed server component tests to be OS-agnostic

### 📦 Other Improvements

- Automatic `.env` file loading on import (via `python-dotenv`)
- Improved scheduled agent demo patterns and `run_until_idle()` API
- Enhanced dashboard visualization for scheduled agents (shows next fire time, iteration count)
- Restructured examples directory (moved patterns to `02-patterns/`, added `10-scheduling/`)

---

## [0.5.2] - 2025-10-19

### 🎉 New Features

#### 🌟 Fan-Out Publishing
**Produce multiple outputs from a single agent execution:**

```python
# Generate 10 diverse product ideas from one brief
idea_generator = (
    flock.agent("generator")
    .consumes(ProductBrief)
    .publishes(ProductIdea, fan_out=10)  # Produces 10 ideas!
)

# Multi-output fan-out: Generate 3 of EACH type in ONE LLM call!
multi_master = (
    flock.agent("multi_master")
    .consumes(Idea)
    .publishes(Movie, MovieScript, MovieCampaign, fan_out=3)
)
# = 9 total artifacts (3 movies + 3 scripts + 3 campaigns) in one execution!
```

**Features:**
- Single execution produces N artifacts per type
- Quality filtering with `where` parameter
- Validation with `validate` parameter
- Dynamic visibility control per artifact
- Massive efficiency: 1 LLM call → multiple validated outputs

**Use cases:**
- Content generation with diversity
- A/B testing variants
- Code review with multiple bug reports
- Multi-perspective analysis

#### 📦 BatchSpec - Cost Optimization
**Process multiple artifacts efficiently:**

```python
# Process 25 transactions in one batch = 96% cost reduction!
payment_processor = flock.agent("payments").consumes(
    Transaction,
    batch=BatchSpec(size=25, timeout=timedelta(seconds=30))
)

# Hybrid batching: by size OR timeout
analyzer = flock.agent("analyzer").consumes(
    LogEntry,
    batch=BatchSpec(size=100, timeout=timedelta(minutes=5))
)
```

**Features:**
- Size-based batching (flush when N artifacts accumulated)
- Timeout-based batching (flush after T seconds)
- Hybrid mode (whichever comes first)
- Automatic batch coordination

**Benefits:**
- 90%+ API cost reduction for bulk operations
- Efficient processing of high-volume streams
- Natural aggregation patterns

#### 🔗 JoinSpec - Data Correlation
**Correlate related artifacts within time windows:**

```python
# Match orders + shipments by order_id within 24 hours
customer_service = flock.agent("notifications").consumes(
    Order,
    Shipment,
    join=JoinSpec(by=lambda x: x.order_id, within=timedelta(hours=24))
)

# IoT sensor correlation
quality_control = flock.agent("qc").consumes(
    TemperatureSensor,
    PressureSensor,
    join=JoinSpec(by=lambda x: x.device_id, within=timedelta(seconds=30)),
    batch=BatchSpec(size=5)  # Combine with batching!
)
```

**Features:**
- Correlation by custom key (e.g., order_id, user_id, device_id)
- Time window enforcement
- Multi-type correlation support
- Composable with BatchSpec for multi-stage pipelines

**Use cases:**
- Order + shipment tracking
- Multi-modal data fusion (scans + labs + history)
- IoT sensor correlation
- Financial trade matching

#### 🧠 Semantic Subscriptions - Intelligence Beyond Keywords
**Match artifacts by MEANING, not keywords:**

```python
# Install semantic extras
pip install flock-core[semantic]

# Agents route based on semantic similarity
security_team = (
    flock.agent("security_team")
    .consumes(SupportTicket, semantic_match="security vulnerability exploit")
    .publishes(SecurityAlert)
)

billing_team = (
    flock.agent("billing_team")
    .consumes(SupportTicket, semantic_match="payment charge refund billing")
    .publishes(BillingResponse)
)

# "SQL injection" → Security Team (no "security" keyword needed!)
# "charged twice" → Billing Team (semantic understanding!)
```

**Advanced semantic filtering:**
```python
# Custom threshold (0.0-1.0, default 0.4)
.consumes(Ticket, semantic_match="urgent", semantic_threshold=0.7)  # Strict

# Multiple criteria (ALL must match - AND logic)
.consumes(Doc, semantic_match=["security", "compliance"])

# Field-specific matching
.consumes(Article, semantic_match={
    "query": "machine learning",
    "threshold": 0.6,
    "field": "abstract"  # Only match this field
})
```

**Semantic Context Provider:**
```python
from flock.semantic import SemanticContextProvider

# Find similar historical incidents for context-aware decisions
provider = SemanticContextProvider(
    query_text="database connection timeout",
    threshold=0.4,
    limit=5,
    artifact_type=Incident,
    where=lambda a: a.payload["resolved"] is True
)
similar_incidents = await provider.get_context(store)
```

**Features:**
- Local embeddings with all-MiniLM-L6-v2 model (~90MB)
- No external API required
- Fast with LRU cache (10k entries, ~15ms per embedding)
- Threshold control for precision/recall tuning
- Field extraction for targeted matching
- Multiple predicates with AND logic

**Benefits:**
- No keyword brittleness ("SQL injection" matches "security vulnerability")
- Better recall (catches semantically similar content)
- Intelligent routing without complex rule systems
- Context-aware agents with historical similarity search

**Use cases:**
- Smart ticket routing to specialized teams
- Content recommendation based on meaning
- Incident response with historical context
- Document classification by topic

### 📚 Documentation

- Added comprehensive semantic subscriptions guide (`docs/semantic-subscriptions.md`)
- Added 4 runnable examples in `examples/08-semantic/`:
  - `00_verify_semantic_features.py` - Quick verification (no LLM)
  - `01_intelligent_ticket_routing.py` - Smart routing demo
  - `02_multi_criteria_filtering.py` - Advanced filtering patterns
- Updated README with semantic subscriptions feature
- Added API documentation for all new features

### 🔧 API Changes

**New Parameters:**
- `fan_out` parameter in `.publishes()` for multi-output generation
- `semantic_match` parameter in `.consumes()` for meaning-based matching (replaces `text`)
- `semantic_threshold` parameter in `.consumes()` for similarity control (replaces `min_p`)
- `batch` parameter in `.consumes()` accepts `BatchSpec` objects
- `join` parameter in `.consumes()` accepts `JoinSpec` objects

**Note:** The original `text` and `min_p` parameters have been renamed to `semantic_match` and `semantic_threshold` for clarity. This makes it obvious that matching is semantic (meaning-based), not keyword-based.

### ✅ Testing

- Added 39 semantic subscription tests (100% passing)
- Added fan-out publishing tests
- Added BatchSpec and JoinSpec integration tests
- All 1,435+ tests passing with zero regressions

### 🚀 Performance

- Semantic matching: ~15ms per embedding (CPU)
- Batch processing: ~4.5ms per text with batching
- Cache hit rate: 60-80% typical
- Fan-out efficiency: N outputs in 1 LLM call

---

# Flock 0.5.0 Complete Changelog & Migration Guide

> **Complete architectural rewrite from workflow orchestration to blackboard architecture**

**Release Date**: 12. Oct 2025
**Migration Effort**: 1-4 weeks depending on system size
**Backward Compatibility**: **NONE** - This is a ground-up rewrite

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architectural Changes](#architectural-changes)
3. [Breaking Changes](#breaking-changes)
4. [New Features](#new-features)
5. [Migration Guide](#migration-guide)
6. [Performance Improvements](#performance-improvements)
7. [Deprecations & Removals](#deprecations--removals)
8. [Known Limitations](#known-limitations)
9. [Upgrade Recommendations](#upgrade-recommendations)

---

## Executive Summary

### What Changed?

Flock 0.5.0 is **not an incremental update**—it's a complete reimplementation with a fundamentally different architecture:

| Aspect | Flock 0.4 | Flock 0.5 |
|--------|-----------|-----------|
| **Architecture** | Workflow orchestration (LangGraph-style) | Blackboard architecture (Hearsay-II-style) |
| **Communication** | Direct agent-to-agent handoffs | Publish-subscribe via blackboard |
| **Execution Model** | Sequential by default | Parallel by default |
| **Type System** | String-based signatures | Pure Pydantic models with `@flock_type` |
| **Routing** | Explicit routers with config | Type-based subscription matching |
| **State** | Mutable `FlockContext` | Immutable `Artifact` objects |
| **Orchestration** | Temporal.io workflows | Event-driven coordination |
| **Dependencies** | PyTorch + Temporal + Heavy stack | DuckDB + FastAPI + Lean stack |

### Why This Change?

**Workflow orchestration doesn't scale.** As agent systems grow:
- **O(n²) complexity**: Every new agent requires updating router configuration
- **Tight coupling**: Agents must know about each other
- **Sequential bottlenecks**: Parallelism requires manual configuration
- **Testing complexity**: Must mock entire workflow graph

**Blackboard architecture solves this:**
- **O(n) complexity**: Agents subscribe to types, routing is automatic
- **Loose coupling**: Agents only know about data types
- **Natural parallelism**: All matching agents execute concurrently
- **Testing simplicity**: Test agents in isolation with type fixtures

**Research validation**: Recent studies show blackboard + MCP architectures achieve **competitive performance with SOTA multi-agent systems while using fewer tokens** ([Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture, 2024](https://arxiv.org/abs/2507.01701)).

---

## Architectural Changes

### Core Architecture: Workflow → Blackboard

#### Flock 0.4: Workflow Orchestration
```
[Agent A] → Router → [Agent B] → Router → [Agent C]
                ↓
        Temporal.io Workflow
```

**Characteristics:**
- Explicit handoffs between agents
- Central orchestrator manages execution
- Sequential by default, parallel requires configuration
- Tight coupling through router configuration

#### Flock 0.5: Blackboard Architecture
```
          [Blackboard Store]
               ↑     ↓
    ┌─────────┼─────┼─────────┐
    ↓         ↓     ↓         ↓
[Agent A] [Agent B] [Agent C] [Agent D]
```

**Characteristics:**
- Publish-subscribe communication
- No central orchestrator (event-driven)
- Parallel by default, executes all matching agents
- Loose coupling through type system

### Communication Model

#### 0.4: Direct Handoffs
```python
# Flock 0.4
class MyAgent(Agent):
    async def execute(self, context: FlockContext):
        result = await self.process(context.data)
        context.set_result(result)
        return "next_agent"  # Explicit routing
```

#### 0.5: Publish-Subscribe
```python
# Flock 0.5
@flock.agent("my_agent")
    .consumes(InputType)
    .publishes(OutputType)
    .does(process)

async def process(input: InputType) -> OutputType:
    # Pure transformation, no routing logic
    return OutputType(...)
```

### Execution Model

#### 0.4: Imperative Execution
```python
# Flock 0.4
context = FlockContext(initial_data)
result = await flock.run(context, entry_agent="start")
# Sequential execution, manual parallelism
```

#### 0.5: Declarative Execution
```python
# Flock 0.5
await flock.publish(UserRequest(query="..."))
await flock.run_until_idle()
# Parallel execution, automatic coordination
```

---

## Breaking Changes

### 1. Agent Definition

#### Before (0.4)
```python
from flock import FlockFactory, Agent, FlockContext

class ResearchAgent(Agent):
    def __init__(self, name: str):
        super().__init__(name)
        self.input_signature = "query: str"
        self.output_signature = "findings: List[str]"

    async def execute(self, context: FlockContext) -> str:
        query = context.data.get("query")
        findings = await self.research(query)
        context.set_result({"findings": findings})
        return "summarizer_agent"  # Explicit routing

agent = FlockFactory.create_default_agent(
    name="researcher",
    description="Research agent",
    agent_class=ResearchAgent
)
```

#### After (0.5)
```python
from flock import flock, flock_type
from pydantic import BaseModel

@flock_type
class Query(BaseModel):
    text: str

@flock_type
class Findings(BaseModel):
    results: list[str]

async def research_handler(query: Query) -> Findings:
    findings = await do_research(query.text)
    return Findings(results=findings)

agent = (
    flock.agent("researcher")
    .consumes(Query)
    .publishes(Findings)
    .does(research_handler)
)
```

**Key Changes:**
- ❌ No `FlockFactory`, `Agent` base class, or `FlockContext`
- ✅ Fluent builder pattern: `flock.agent().consumes().publishes().does()`
- ✅ Pure Pydantic types with `@flock_type` decorator
- ✅ Functions instead of classes (simpler)
- ✅ No explicit routing (type-based)

---

### 2. Multi-Agent Coordination

#### Before (0.4): Explicit Routing
```python
from flock import Router

# Define explicit routing logic
router = Router()
router.add_route("researcher", "summarizer", lambda ctx: ctx.has_findings())
router.add_route("summarizer", "formatter", lambda ctx: ctx.has_summary())

flock = FlockFactory.create(
    agents=[researcher, summarizer, formatter],
    router=router,
    entry_agent="researcher"
)
```

#### After (0.5): Type-Driven Flow
```python
# No router needed! Flow emerges from type relationships

# Researcher consumes Query, publishes Findings
researcher = flock.agent("researcher").consumes(Query).publishes(Findings).does(research)

# Summarizer consumes Findings, publishes Summary
summarizer = flock.agent("summarizer").consumes(Findings).publishes(Summary).does(summarize)

# Formatter consumes Summary, publishes Report
formatter = flock.agent("formatter").consumes(Summary).publishes(Report).does(format)

# Flow: Query → researcher → Findings → summarizer → Summary → formatter → Report
# No explicit routing config needed!
```

**Key Changes:**
- ❌ No `Router` class or route configuration
- ✅ Type system defines flow automatically
- ✅ Add/remove agents without touching router
- ✅ Natural composition through type matching

---

### 3. Execution & Result Retrieval

#### Before (0.4): Direct Access
```python
# Flock 0.4
context = FlockContext({"query": "AI trends"})
result = await flock.run(context, entry_agent="researcher")

# Direct access to result
findings = result.data.get("findings")
```

#### After (0.5): Store Queries
```python
# Flock 0.5
from flock.store import FilterConfig

# Publish input
await flock.publish(Query(text="AI trends"))

# Wait for completion
await flock.run_until_idle()

# Query the blackboard store
findings_artifacts = await flock.store.query_artifacts(
    FilterConfig(type_names={"Findings"}),
    limit=10
)

findings = findings_artifacts[0].payload
```

**Key Changes:**
- ❌ No direct result access via return value
- ✅ Results stored in persistent blackboard
- ✅ Query by type, producer, tags, time range, etc.
- ✅ Full audit trail of all artifacts

---

### 4. Tools & External Integration

#### Before (0.4): Modules
```python
# Flock 0.4
from flock import Module

class WebSearchModule(Module):
    async def search(self, query: str) -> list[str]:
        # Implementation
        pass

flock = FlockFactory.create(
    agents=[...],
    modules=[WebSearchModule()]
)
```

#### After (0.5): MCP Servers & Custom Tools
```python
# Flock 0.5 - Custom Tools
from flock import flock_tool

@flock_tool
async def web_search(query: str) -> list[str]:
    """Search the web for information."""
    # Implementation
    pass

# Or use MCP servers (external processes)
flock.with_mcp_server(
    name="brave-search",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-brave-search"]
)
```

**Key Changes:**
- ❌ No `Module` concept
- ✅ Simple `@flock_tool` decorator for custom tools
- ✅ MCP (Model Context Protocol) for external tools
- ✅ Tools run in separate processes (better isolation)

---

### 5. Configuration & Setup

#### Before (0.4): Factory Pattern
```python
# Flock 0.4
from flock import FlockFactory, TemporalConfig

flock = FlockFactory.create(
    agents=[agent1, agent2],
    router=router,
    temporal_config=TemporalConfig(
        host="localhost:7233",
        namespace="default"
    ),
    entry_agent="agent1"
)
```

#### After (0.5): Fluent Builder
```python
# Flock 0.5
from flock import Flock

flock = (
    Flock.builder()
    .with_agent(agent1)
    .with_agent(agent2)
    .with_tool(custom_tool)
    .with_mcp_server(name="brave", command="npx", args=[...])
    .build()
)

# Or use default orchestrator
await flock.publish(initial_artifact)
await flock.run_until_idle()
```

**Key Changes:**
- ❌ No `FlockFactory`, `TemporalConfig`
- ✅ Fluent builder: `Flock.builder().with_agent().with_tool().build()`
- ✅ No Temporal.io configuration (removed dependency)
- ✅ Simpler default setup

---

## New Features

### 1. Real-Time Dashboard

**Location:** `http://localhost:3000` (when running `flock dashboard`)

**Features:**
- **Dual Visualization Modes:**
  - **Agent View**: Network graph showing agent relationships and message flows
  - **Blackboard View**: Data lineage graph showing artifact transformations
- **WebSocket Streaming**: Zero-lag updates as agents execute
- **Trace Viewer**: 7 visualization modes (Timeline, Waterfall, Gantt, Flamegraph, Sunburst, Icicle, Sankey)
- **SQL Query Interface**: AI-queryable telemetry via DuckDB
- **Agent Metrics**: Real-time message counts, execution status, streaming tokens
- **Artifact Inspector**: Inspect artifact payloads, metadata, consumption chains

**Example:**
```bash
# Terminal 1: Start dashboard
flock dashboard

# Terminal 2: Run your agents
python my_agent_system.py

# Browser: Open http://localhost:3000
# Watch agents execute in real-time!
```

---

### 2. Type-Safe Contracts with @flock_type

**Pure Pydantic models** replace string-based signatures:

```python
from flock import flock_type
from pydantic import BaseModel, Field
from datetime import datetime

@flock_type
class UserRequest(BaseModel):
    """User's research request."""
    query: str = Field(description="Search query")
    max_results: int = Field(default=10, ge=1, le=100)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

@flock_type
class ResearchFindings(BaseModel):
    """Research results."""
    query: str
    sources: list[str]
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
```

**Benefits:**
- ✅ **Compile-time validation**: Catch type errors before runtime
- ✅ **Auto-generated docs**: Pydantic models document themselves
- ✅ **IDE support**: Full autocomplete and type checking
- ✅ **Canonical names**: `__main__.UserRequest` with aliases for flexibility

---

### 3. Visibility Controls (Zero-Trust Security)

**5 Visibility Types** for multi-tenant systems:

#### Public Visibility
```python
from flock.core.visibility import PublicVisibility

@flock_type
class PublicAnnouncement(BaseModel):
    message: str
    visibility: PublicVisibility = PublicVisibility()
# Any agent can consume this
```

#### Private Visibility
```python
from flock.core.visibility import PrivateVisibility

@flock_type
class PrivateNote(BaseModel):
    content: str
    visibility: PrivateVisibility = PrivateVisibility(producer_id="agent-123")
# Only the producer can consume this
```

#### Tenant Visibility
```python
from flock.core.visibility import TenantVisibility

@flock_type
class PatientData(BaseModel):
    patient_id: str
    diagnosis: str
    visibility: TenantVisibility = TenantVisibility(tenant_id="hospital-abc")
# Only agents with tenant_id="hospital-abc" can consume
```

#### Labelled Visibility
```python
from flock.core.visibility import LabelledVisibility

@flock_type
class InternalReport(BaseModel):
    data: dict
    visibility: LabelledVisibility = LabelledVisibility(required_labels={"clearance:secret", "dept:engineering"})
# Only agents with BOTH labels can consume
```

#### After Visibility
```python
from flock.core.visibility import AfterVisibility
from datetime import datetime, timedelta

@flock_type
class ScheduledMessage(BaseModel):
    content: str
    visibility: AfterVisibility = AfterVisibility(
        available_after=datetime.utcnow() + timedelta(hours=1)
    )
# Only visible after the specified timestamp
```

---

### 4. Persistent Blackboard Store

**SQLite-backed storage** with full audit trail:

```python
from flock.store import SQLiteBlackboardStore

store = SQLiteBlackboardStore(db_path=".flock/blackboard.db")

# Query artifacts by type
from flock.store import FilterConfig

artifacts = await store.query_artifacts(
    FilterConfig(
        type_names={"UserRequest"},
        tags={"priority:high"},
        start=datetime(2024, 1, 1),
        end=datetime(2024, 12, 31)
    ),
    limit=100
)

# Get consumption history
consumptions = await store.get_consumptions(artifact_id="artifact-123")
```

**Features:**
- ✅ Every artifact persisted with metadata
- ✅ Consumption tracking (who consumed what, when)
- ✅ Tag-based filtering
- ✅ Time-range queries
- ✅ Correlation ID tracking for request chains

---

### 5. Production Safety Features

#### Circuit Breakers
```python
from flock import Flock

flock = (
    Flock.builder()
    .with_agent(agent)
    .with_circuit_breaker(
        failure_threshold=5,
        timeout_seconds=30,
        half_open_after_seconds=60
    )
    .build()
)
```

#### Feedback Prevention
```python
agent = (
    flock.agent("analyzer")
    .consumes(Report)
    .publishes(Analysis)
    .prevents_feedback()  # Prevents consuming its own output
    .does(analyze)
)
```

#### Execution Limits
```python
await flock.run_until_idle(
    max_cycles=100,  # Prevent infinite loops
    timeout_seconds=300  # 5 minute timeout
)
```

---

### 6. AI-Queryable Telemetry (DuckDB + OpenTelemetry)

**DuckDB storage** for traces:

```python
# Dashboard SQL interface allows queries like:
SELECT
    service_name,
    span_name,
    AVG(duration_ns / 1000000) as avg_duration_ms,
    COUNT(*) as call_count
FROM spans
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY service_name, span_name
ORDER BY avg_duration_ms DESC
LIMIT 10;
```

**Features:**
- ✅ **10-100x faster than SQLite** for analytical queries
- ✅ **Jaeger-compatible traces** (OpenTelemetry)
- ✅ **SQL interface** in dashboard
- ✅ **AI-queryable**: LLMs can write queries to analyze system behavior

---

### 7. MCP (Model Context Protocol) Integration

**Extensible tool ecosystem:**

```python
# Use community MCP servers
flock.with_mcp_server(
    name="brave-search",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-brave-search"],
    env={"BRAVE_API_KEY": os.getenv("BRAVE_API_KEY")}
)

# Or build your own
@flock_tool
async def custom_tool(param: str) -> str:
    """Custom tool implementation."""
    return f"Processed: {param}"
```

**Benefits:**
- ✅ Tools run in separate processes (better isolation)
- ✅ Language-agnostic (write tools in any language)
- ✅ Community ecosystem (growing library of MCP servers)
- ✅ Hot-reload support (update tools without restarting)

---

## Migration Guide

### Step-by-Step Migration

#### Step 1: Update Dependencies

```bash
# Uninstall old version
pip uninstall flock-core

# Install new version
pip install flock-core==0.5.0
```

#### Step 2: Convert Types

**Before:**
```python
class MyAgent(Agent):
    def __init__(self):
        self.input_signature = "query: str, max_results: int"
        self.output_signature = "results: List[str], confidence: float"
```

**After:**
```python
from flock import flock_type
from pydantic import BaseModel

@flock_type
class Query(BaseModel):
    query: str
    max_results: int = 10

@flock_type
class Results(BaseModel):
    results: list[str]
    confidence: float
```

#### Step 3: Convert Agents

**Before:**
```python
class MyAgent(Agent):
    async def execute(self, context: FlockContext) -> str:
        data = context.data
        result = await self.process(data)
        context.set_result(result)
        return "next_agent"
```

**After:**
```python
async def my_handler(input: Query) -> Results:
    result = await process(input)
    return Results(results=result, confidence=0.9)

agent = (
    flock.agent("my_agent")
    .consumes(Query)
    .publishes(Results)
    .does(my_handler)
)
```

#### Step 4: Remove Router Configuration

**Before:**
```python
router = Router()
router.add_route("agent1", "agent2", condition)
router.add_route("agent2", "agent3", condition)
```

**After:**
```python
# No router needed! Define agents with type contracts:

agent1 = flock.agent("agent1").consumes(TypeA).publishes(TypeB).does(handler1)
agent2 = flock.agent("agent2").consumes(TypeB).publishes(TypeC).does(handler2)
agent3 = flock.agent("agent3").consumes(TypeC).publishes(TypeD).does(handler3)

# Flow emerges from type relationships: TypeA → TypeB → TypeC → TypeD
```

#### Step 5: Update Execution

**Before:**
```python
context = FlockContext({"query": "search term"})
result = await flock.run(context, entry_agent="researcher")
findings = result.data.get("findings")
```

**After:**
```python
from flock.store import FilterConfig

# Publish input
await flock.publish(Query(query="search term"))

# Wait for completion
await flock.run_until_idle()

# Query results
artifacts = await flock.store.query_artifacts(
    FilterConfig(type_names={"Results"}),
    limit=1
)
results = artifacts[0].payload  # Results object
```

#### Step 6: Replace Modules with Tools

**Before:**
```python
class SearchModule(Module):
    async def search(self, query: str) -> list[str]:
        # Implementation
```

**After:**
```python
@flock_tool
async def search(query: str) -> list[str]:
    """Search the web."""
    # Same implementation
```

---

### Complete Example Migration

#### Flock 0.4: Research Assistant
```python
# research_assistant_04.py (Flock 0.4)
from flock import FlockFactory, Agent, FlockContext, Router, Module

class WebSearchModule(Module):
    async def search(self, query: str) -> list[str]:
        # Web search implementation
        return ["result1", "result2"]

class ResearchAgent(Agent):
    def __init__(self):
        super().__init__("researcher")
        self.input_signature = "query: str"
        self.output_signature = "findings: List[str]"

    async def execute(self, context: FlockContext) -> str:
        query = context.data["query"]
        search = context.get_module(WebSearchModule)
        findings = await search.search(query)
        context.set_result({"findings": findings})
        return "summarizer"

class SummarizerAgent(Agent):
    def __init__(self):
        super().__init__("summarizer")
        self.input_signature = "findings: List[str]"
        self.output_signature = "summary: str"

    async def execute(self, context: FlockContext) -> str:
        findings = context.data["findings"]
        summary = " | ".join(findings)
        context.set_result({"summary": summary})
        return "END"

# Setup
router = Router()
router.add_route("researcher", "summarizer", lambda ctx: "findings" in ctx.data)

flock = FlockFactory.create(
    agents=[ResearchAgent(), SummarizerAgent()],
    modules=[WebSearchModule()],
    router=router,
    entry_agent="researcher"
)

# Execute
context = FlockContext({"query": "AI trends"})
result = await flock.run(context)
print(result.data["summary"])
```

#### Flock 0.5: Research Assistant
```python
# research_assistant_05.py (Flock 0.5)
from flock import Flock, flock, flock_type, flock_tool
from pydantic import BaseModel

# Types
@flock_type
class Query(BaseModel):
    text: str

@flock_type
class Findings(BaseModel):
    results: list[str]

@flock_type
class Summary(BaseModel):
    text: str

# Tools
@flock_tool
async def web_search(query: str) -> list[str]:
    """Search the web."""
    # Same implementation
    return ["result1", "result2"]

# Agents
async def research_handler(query: Query, tools) -> Findings:
    results = await tools.web_search(query.text)
    return Findings(results=results)

async def summarize_handler(findings: Findings) -> Summary:
    summary = " | ".join(findings.results)
    return Summary(text=summary)

researcher = flock.agent("researcher").consumes(Query).publishes(Findings).does(research_handler)
summarizer = flock.agent("summarizer").consumes(Findings).publishes(Summary).does(summarize_handler)

# Setup
orchestrator = (
    Flock.builder()
    .with_agent(researcher)
    .with_agent(summarizer)
    .with_tool(web_search)
    .build()
)

# Execute
from flock.store import FilterConfig

await orchestrator.publish(Query(text="AI trends"))
await orchestrator.run_until_idle()

# Get results
summaries = await orchestrator.store.query_artifacts(
    FilterConfig(type_names={"Summary"}),
    limit=1
)
print(summaries[0].payload.text)
```

**Key Differences:**
1. ❌ No `FlockFactory`, `FlockContext`, `Router`
2. ✅ Pydantic types with `@flock_type`
3. ✅ Simple functions instead of Agent classes
4. ✅ Fluent builder pattern
5. ✅ Store queries instead of direct access
6. ✅ Type-driven flow (no router config)

---

## Performance Improvements

### Resource Usage

| Metric | Flock 0.4 | Flock 0.5 | Improvement |
|--------|-----------|-----------|-------------|
| **Install Size** | ~3.2 GB | ~650 MB | **80% reduction** |
| **Dependencies** | 47 packages | 23 packages | **51% reduction** |
| **PyTorch** | Required | **Removed** | ✅ |
| **Agent Handoff** | ~100-500ms | <1ms | **100-500x faster** |
| **Routing Complexity** | O(n²) | O(n) | **Linear scaling** |

### Why So Much Faster?

1. **No PyTorch**: Removed 2.5GB dependency not needed for orchestration
2. **No Temporal.io**: Event-driven coordination is lightweight
3. **Zero-copy messaging**: Artifacts stored once, referenced by ID
4. **Parallel execution**: All matching agents run concurrently
5. **DuckDB**: 10-100x faster than SQLite for analytical queries

### Benchmark: 10-Agent Pipeline

| Metric | Flock 0.4 | Flock 0.5 |
|--------|-----------|-----------|
| **Sequential execution** | 5.2s | 0.8s |
| **With parallelism** | 3.1s | 0.2s |
| **Memory usage** | 450 MB | 90 MB |

---

## Deprecations & Removals

### Removed Components

#### Temporal.io Integration
- **Reason**: Heavy dependency, not needed for event-driven coordination
- **Migration**: Use `flock.publish()` + `run_until_idle()`

#### PyTorch Dependency
- **Reason**: Only needed for embeddings, not core orchestration
- **Migration**: Use external MCP servers for embeddings if needed

#### Router Class
- **Reason**: Type system provides automatic routing
- **Migration**: Define type contracts with `.consumes()` and `.publishes()`

#### FlockContext
- **Reason**: Mutable state doesn't fit event-driven model
- **Migration**: Use immutable `Artifact` objects, query store for results

#### Agent Base Class
- **Reason**: Functions are simpler than classes for agent logic
- **Migration**: Use async functions with `.does(handler)`

#### Module System
- **Reason**: MCP provides better tool isolation
- **Migration**: Use `@flock_tool` or MCP servers

#### String Signatures
- **Reason**: No type safety, error-prone
- **Migration**: Use Pydantic models with `@flock_type`

---

## Known Limitations

### Beta Features

1. **SQLiteBlackboardStore**: Marked as beta, may have performance issues at scale
2. **Dashboard OAuth**: No authentication yet (local use only)
3. **Redis Backend**: Not yet implemented (roadmap item)

### Not Yet Supported

1. **Kafka/RabbitMQ Integration**: Planned for 1.0
2. **Kubernetes-Native Deployment**: Planned for 1.0
3. **Multi-Tenant Dashboard**: Single tenant only
4. **Advanced Analytics**: Basic metrics only
5. **RBAC**: No role-based access control yet

### Migration Challenges

1. **No Backward Compatibility**: Complete rewrite required
2. **Async Everywhere**: Must use async/await throughout
3. **Learning Curve**: New patterns take time to internalize
4. **Example Dependencies**: Most examples require API keys

---

## Upgrade Recommendations

### When to Upgrade

#### ✅ **Upgrade Immediately If:**
- Starting a new project
- Need parallel agent execution (10+ agents)
- Require type safety and compile-time validation
- Want production observability (dashboard, traces)
- Building multi-tenant systems (need visibility controls)
- Resource constraints (80% reduction in dependencies)

#### ⏳ **Wait for 1.0 If You Need:**
- Enterprise persistence (Redis, Kafka)
- Kubernetes-native deployment
- OAuth/RBAC for dashboard
- Multi-tenant SaaS features
- Proven 99.99% uptime

#### ⚠️ **Stay on 0.4 If:**
- Heavily invested in Temporal.io workflows
- Sequential execution sufficient
- Production system is stable
- Migration cost > benefits
- Team has no bandwidth for rewrite

### Migration Timeline

| System Size | Agents | Est. Time | Complexity |
|-------------|--------|-----------|------------|
| **Small** | 1-5 | 1-2 days | Low |
| **Medium** | 6-20 | 1 week | Medium |
| **Large** | 21-50 | 2-3 weeks | High |
| **Enterprise** | 50+ | 4+ weeks | Very High |

**Factors affecting timeline:**
- Complexity of router logic
- Number of custom modules
- Amount of FlockContext usage
- Test coverage requirements
- Team familiarity with async/Pydantic

---

## FAQ

### Q: Is there ANY backward compatibility?

**A:** No. Flock 0.5 is a complete architectural rewrite with zero shared code.

### Q: Why not call this Flock 2.0?

**A:** The team considers 0.5 a "production-ready core" but reserves 1.0 for enterprise features (Kafka, K8s, OAuth, Redis). This follows semantic versioning where 0.x.x allows API evolution.

### Q: Can I run 0.4 and 0.5 side by side?

**A:** Yes, but not recommended. They use different package names internally, but share the `flock` namespace. Use separate virtual environments.

### Q: Where's the migration tooling?

**A:** No automated migration tools exist (yet). The architectural differences are too fundamental for code transformation.

### Q: What about Temporal workflows?

**A:** Temporal is completely removed. If you need durable workflows, consider staying on 0.4 or using Temporal separately.

### Q: How stable is the API?

**A:** Core API is stable. Minor changes may occur before 1.0, but no more ground-up rewrites.

### Q: Will you maintain 0.4?

**A:** Critical bug fixes only. No new features. Focus is on 0.5 → 1.0.

---

## Resources

- **API Documentation**: [docs.flock.io](https://docs.flock.io)
- **Examples**: [`examples/`](../../examples/) directory (34+ working examples)
- **Migration Support**: [GitHub Discussions](https://github.com/whiteducksoftware/flock/discussions)
- **Roadmap**: [ROADMAP.md](./ROADMAP.md)
- **Changelog**: This document
- **Release Notes**: [GitHub Releases](https://github.com/whiteducksoftware/flock/releases)

---

## Acknowledgments

This release represents **months of research** into production agent systems, blackboard architecture patterns, and modern multi-agent frameworks.

**Special thanks to:**
- The Hearsay-II team (1970s) for pioneering blackboard architecture
- LangGraph, AutoGen, and CrewAI for inspiring the original 0.4
- The MCP team for creating an extensible tool ecosystem
- Our early adopters who helped shape 0.5 through feedback

**Philosophy shift:**
> "Workflow orchestration made sense when we thought of agents as steps in a pipeline. But agents are more like microservices—they should communicate through events, not hardcoded calls."

The future of agent systems is **decentralized, type-safe, and observable**. Flock 0.5 gets us there.

---

*Built with ❤️ by the Flock team*
