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
    .decides(Route, model="jev/jev-latest", threshold=0.8)
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
    model="local/clef-flash",   # or a DecisionProvider; default: DEFAULT_DECISION_MODEL
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

## Providers

| Model string | Protocol | Configuration |
|---|---|---|
| `jev/<model>` | `POST /v1/systemone` | `JEV_API_KEY` (`JEV_API_BASE` overrides the endpoint) |
| `local/<name>` | `POST /v1/systemone` | `DECISION_API_BASE`, default `http://127.0.0.1:8080` |

Set `DEFAULT_DECISION_MODEL` to use a model string without passing `model=`.

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

[`examples/15-decisions/01_ticket_triage.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/15-decisions/01_ticket_triage.py) routes support tickets with a local Clef model or Jev and sends ambiguous tickets to a supervisor.
