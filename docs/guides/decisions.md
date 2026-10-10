---
tags:
  - decisions
  - subscriptions
  - routing
description: Route workflows with decision models - typed Choice options, .decides() and choice subscriptions
---

# Decision Models

A **decision model** reads a state plus a typed question and returns a calibrated probability for every option of a closed set, in one forward pass and without generating text. Examples are TypeSafe Jev, Cloudflare Clef (open weights) and Microsoft-Decision-1. For routing, classification and gating they are one to two orders of magnitude cheaper and faster than an LLM call.

In Flock a decision is a **shared fact on the blackboard**: one agent decides once and publishes the decision. Other agents subscribe to an **option** of that decision.

```python
from pydantic import BaseModel

from flock import Choice, Flock, flock_type


@flock_type
class Ticket(BaseModel):
    subject: str
    body: str


@flock_type
class Reply(BaseModel):
    team: str
    reply: str


class Route(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds"
    shipping = "Delivery, tracking, returns"
    tech = "Bugs, crashes, login problems"


flock = Flock("openai/gpt-4.1")

triage = (
    flock.agent("triage")
    .consumes(Ticket)
    .decides(Route, model="azure/decision-1", threshold=0.8)
)

flock.agent("billing").consumes(Route.billing).publishes(Reply)
flock.agent("tech").consumes(Route.tech).publishes(Reply)
flock.agent("supervisor").consumes(Route.UNSURE).publishes(Reply)
```

## Choice types

A `Choice` subclass is the question and its option set:

- The **docstring** is the question sent to the model.
- Every **string attribute** is an option. Its value describes the option and is sent as the option's criteria. Good descriptions matter as much as good prompts.
- Options are static. A Choice needs at least two and at most 255 options.
- `UNSURE` and `ANY` are reserved names.

After class creation each option is a subscription handle: `Route.billing`, `Route.tech`, plus `Route.UNSURE` and `Route.ANY`.

## Deciding: `.decides()`

```python
.decides(
    Route,
    model="azure/decision-1",   # or a DecisionProvider; default: DEFAULT_DECISION_MODEL
    threshold=0.8,              # optional; below it the decision is UNSURE
    instructions=None,          # optional; overrides the Choice docstring
    visibility=None,            # optional; overrides visibility inheritance
)
```

`.decides()` sets the agent's engine to a `DecisionEngine` and makes the agent publish `Decision.of(Route)`. Utilities, guards and tracing work as for any other agent. It cannot be combined with `.with_engines()`, and batch subscriptions are not supported.

The model sees the agent's inputs as its state, one line per input: `Ticket: {"subject": "...", "body": "..."}`.

Every execution publishes one `Decision.of(Route)` artifact:

| Field | Meaning |
|---|---|
| `choice` | The selected option, or `UNSURE` when its probability is below `threshold` |
| `best_guess` | The model's pick, also when unsure |
| `probabilities` | Probability per option |
| `confidence` | Confidence as reported by the model |
| `threshold` | The threshold that applied |
| `subject_ids` | Ids of the artifacts the decision is about |
| `model` | The model that answered (as reported by the provider) |
| `latency_ms` | Round trip of the decision request |

## Routing: choice subscriptions

```python
flock.agent("billing").consumes(Route.billing)    # one option
flock.agent("supervisor").consumes(Route.UNSURE)   # decisions below the threshold
flock.agent("logger").consumes(Route.ANY)          # every decision
flock.agent("orders").consumes(Route.billing).consumes(Route.shipping)  # OR
```

A choice subscription triggers on matching decisions but **delivers the decision's subject**: the `billing` agent receives the `Ticket`, so its engine signature is `Ticket -> Reply`, exactly as if it consumed `Ticket` directly. The decision is on the context:

```python
class BillingEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        ticket = inputs.first_as(Ticket)
        routed_with = ctx.decision.probabilities["billing"]
        ...
```

Consumption is recorded on the decision artifact, so lineage and the dashboard show `triage → billing`.

To work with the decision itself (for an audit log, for example), consume its type like any other artifact:

```python
flock.agent("auditor").consumes(Decision.of(Route)).publishes(AuditEntry)
```

A choice handle must be the only type in its `.consumes()` call. `where=` predicates on a choice subscription receive the decision.

## Thresholds and the UNSURE branch

With `threshold=0.8` the decision is firm only when the chosen option's probability is at least 0.8. Otherwise `choice` is `UNSURE` and only `Route.UNSURE` subscribers run, typically an LLM agent or a human-in-the-loop step. This is a confidence-gated cascade: keep the confident verdicts, escalate the rest.

Calibration is per task, not global. Pick each decider's threshold on that decider's own data. Recorded decisions (persistent store, traces) make it cheap to replay inputs against another model before switching.

## Visibility

A decision inherits the visibility of its subject, so routing never widens who can read data. Agents that may not see the ticket do not see its decision either and are not triggered. If a decider consumes several inputs with different visibilities, it fails instead of guessing; pass `visibility=` to `.decides()` to choose the decision's readership explicitly.

## Images

Decision models that accept images can decide about pictures. Put the picture into the artifact as a `flock.Image` field:

```python
from flock import Choice, Flock, Image, flock_type


@flock_type
class ProductPhoto(BaseModel):
    sku: str
    photo: Image


class Condition(Choice):
    """Is the product in the photo damaged?"""

    intact = "No visible damage"
    damaged = "Cracks, dents, tears or broken parts"


flock.agent("inspector").consumes(ProductPhoto).decides(Condition, model="openai/gpt-6-luna")

await flock.publish(ProductPhoto(sku="A-17", photo=Image.from_file("a17.jpg")))
```

- `Image` holds the picture as a base64 `data:image/...` URL, so it round-trips through stores, the REST API and the dashboard. Only inline data is accepted: Flock never fetches an image from a URL or a file path named in an artifact.
- `Image.from_file()`, `Image.from_bytes()` and `Image.from_pil()` scale the picture down to `max_side` (default 1024 px) and re-encode it as JPEG (PNG when it has transparency). Re-encoding drops EXIF metadata such as GPS positions. Smaller images are faster: a local Clef model took 1.3 s for a 108 KB photo and 11 s for 1 MB.
- The decider sends every `Image` in its inputs (also nested, in order) to the model; the text state shows `<image 1>`, `<image 2>`, ... in their place.
- A text-only provider refuses image inputs with a clear error instead of dropping the images.

| Provider | Images |
|---|---|
| `openai/<model>` | yes (`input_image` parts) |
| `local/<name>` | yes, if the served model has vision support (top-level `images`, raw base64) |
| `azure/<deployment>` (Microsoft-Decision-1) | no |
| `jev/<model>` | no |

In the dashboard, a decider's options show lanes with thumbnails of the latest images sorted into each option, and a decision artifact shows the decided image next to its probabilities. Image fields render as thumbnails instead of base64 text.

<p align="center">
  <img alt="A decider's option lanes filling with sorted images" src="../../assets/images/decisions/decision-lanes.gif" width="360">
</p>

In the Blackboard View every image artifact shows its thumbnail, and each decision shows the image it decided on, its probabilities and the threshold:

<p align="center">
  <img alt="Image artifacts, decisions with the decided image, and the bins they routed to" src="../../assets/images/decisions/decision-blackboard.png" width="900">
</p>

## Providers

| Model string | Protocol | Configuration |
|---|---|---|
| `jev/<model>` | `POST /v1/systemone` | `JEV_API_KEY` (`JEV_API_BASE` overrides the endpoint) |
| `local/<name>` | `POST /v1/systemone` | `DECISION_API_BASE`, default `http://127.0.0.1:8080` |
| `azure/<deployment>` | `POST /v1/systemone` on Azure AI Foundry (Microsoft-Decision-1) | `AZURE_API_BASE`, `AZURE_API_KEY`; `AZURE_DECISION` overrides the path (default `/providers/microsoft/v1/systemone`) or sets a full URL; `azure/` alone uses `AZURE_DECISION_DEPLOYMENT` |
| `openai/<model>` | `POST /v1/decisions` | `OPENAI_API_KEY` |

Set `DEFAULT_DECISION_MODEL` to use a model string without passing `model=`.

The live tests (`FLOCK_LIVE_DECISIONS=1 uv run pytest tests/decisions/test_live_providers.py`) run against `azure/decision-1` by default and add the other providers when their configuration is present.

### Local models

Any server that speaks `POST /v1/systemone` works with `local/`. llama.cpp's server runs Clef GGUF files with the decision head:

```bash
llama serve -m Clef-Flash-Q8_0.gguf -b 4096 -ub 4096 -ngl 99
```

The model evaluates the whole prompt in one batch, so `-b` and `-ub` must cover the longest request.

### Errors

Provider failures (unreachable server, HTTP errors, answers with unknown options) fail the decider's execution and publish a `WorkflowError`. Error messages name the provider and the HTTP status only, never the response body, because a body can echo the decided data.

## Testing

`FakeDecider` answers with fixed probabilities or with a function of the state and records every call:

```python
from flock.decisions import FakeDecider

decider = FakeDecider({"billing": 0.9, "shipping": 0.05, "tech": 0.05})
flock.agent("triage").consumes(Ticket).decides(Route, model=decider)

await flock.publish(ticket)
await flock.run_until_idle()

state, question = decider.calls[0]
```

## What decision models are good at

They judge well when the answer can be read off the supplied state: routing, intent and topic classification, policy checks against given text. They are weak at reference-free judgments of taste or quality, where their confidence stops predicting their errors. They give no reasons, so let an LLM explain the low-confidence and failing cases. A decision model should not be the only gate that allows a risky action; let it deny or escalate, and let allowlists or people allow.

## Example

[`examples/15-decisions/01_ticket_triage.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/15-decisions/01_ticket_triage.py) routes support tickets with Microsoft-Decision-1 (or any other provider) and sends ambiguous tickets to a supervisor. [`02_arxiv_race.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/15-decisions/02_arxiv_race.py) races an LLM against the available decision models on 100 arXiv abstracts. [`03_color_sorter.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/15-decisions/03_color_sorter.py) sorts generated shapes into color bins from their images.
