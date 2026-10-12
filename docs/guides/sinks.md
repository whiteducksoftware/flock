---
title: Sinks
description: Deliver artifacts to external systems over HTTP, with endpoints, secrets, retries, ordering and receipts on the blackboard
tags:
  - sinks
  - publishing
  - integrations
  - http
search:
  boost: 2.0
---

# Sinks

A **sink** is an external system as a consumer on the blackboard. It subscribes like an agent, delivers what it consumes over HTTP, and publishes a receipt for every delivery: `Delivered` or `DeliveryFailed`. Because the receipts are artifacts, the workflow can react to them, the dashboard shows them, and the trace records them.

```python
from flock import Bearer, Endpoint, Flock

flock = Flock(
    "openai/gpt-4.1",
    endpoints={"myapp": Endpoint("https://myapp.example", auth=Bearer(env="MYAPP_TOKEN"))},
)

flock.sink("billing-api").consumes(Reply, where=lambda r: r.team == "billing").post("myapp:/billing")
```

A runnable example without API keys: [`examples/16-sinks/01_billing_sink.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/16-sinks/01_billing_sink.py).

---

## Endpoints

`Flock(endpoints=...)` names the systems sinks deliver to. A sink then says only `"myapp:/billing"`: the endpoint's base URL plus a path.

```python
from flock import Bearer, Endpoint, Header, Hmac

Endpoint(
    "https://myapp.example",
    auth=Bearer(env="MYAPP_TOKEN"),           # Authorization: Bearer <secret>
    # auth=Header("X-Api-Key", env="MYAPP_KEY"),  # the secret in a header of its own
    sign=Hmac(env="MYAPP_SIGNING_SECRET"),    # X-Flock-Signature: sha256=<hex of the body>
    headers={"X-Source": "flock"},            # further headers, without secrets
    timeout=10.0,                             # seconds per request
    retries=5,                                # see Retries
    rate_limit="100/min",                     # shared by every sink of the endpoint
)
```

| Setting | Default | Meaning |
|---|---|---|
| `auth` | none | `Bearer(env=...)` or `Header(name, env=...)` |
| `sign` | none | `Hmac(env=...)` signs every body with HMAC-SHA256, as [webhook deliveries](webhooks.md) do |
| `headers` | none | Headers sent with every request |
| `timeout` | 10 s | Per request |
| `retries` | 5 | Retries after a timeout, a connection error, HTTP 408, 429 or 5xx; 0 fails on the first |
| `rate_limit` | none | `"N/s"`, `"N/min"` or `"N/h"`; requests over the budget wait |

**Secrets are named, never stored.** `Bearer`, `Header` and `Hmac` take the name of an environment variable and read it for each request. The value appears nowhere else: not in the sink's configuration, its `repr`, its receipts or its trace. A variable that is not set, or whose value holds a line break, fails the delivery with a `DeliveryFailed` that names it, before any request is sent. An error that quotes a secret (a transport error, a target that echoes what it got) shows `***` in its place.

A target can also be a full URL, which needs no endpoint and uses the default settings: `.post("https://hooks.example/notify")`.

---

## Declaring a sink

`flock.sink(name)` returns a builder. `.consumes()` takes everything an agent's subscription takes (`where=`, `from_agents=`, `tags=`, `batch=`, `join=`, decision handles, ...), and several calls are OR. `.post()`, `.put()` or `.patch()` names the target and registers the sink.

```python
flock.sink("crm").consumes(Reply).post(
    "myapp:/notes",
    body=lambda artifact: {"note": artifact.payload["text"]},   # the target's schema
    response=CrmRecord,                                         # publish its answer
)
```

| Argument | Meaning |
|---|---|
| `body` | Maps each artifact to the JSON the target expects. By default the artifact's envelope: `id`, `type`, `payload`, `produced_by`, `correlation_id`, `created_at` |
| `response` | Parses the target's JSON answer into this type and publishes it, in the delivery's correlation |

A sink has no engine and no `.publishes()`: it publishes only its receipts (and the response). `.labels(...)` and `.tenant(...)` let it see artifacts with [labelled or tenant visibility](visibility.md), as for agents; `.description(...)` sets the text of its card.

### The shorthand on `publishes()`

An agent can send its own output somewhere directly:

```python
flock.agent("support").consumes(Ticket).publishes(Reply, post="myapp:/audit")
```

This creates a sink named `support-reply-post` that consumes `Reply` from `support` only, shown as a node of its own on the dashboard. `put=` and `patch=` work the same way; with several types, each gets its own sink. For `body=`, `response=` or other filters, declare the sink with `flock.sink(...)`.

---

## What goes out

Every execution of a sink sends **one request**: one artifact as an object, a batch (`batch=BatchSpec(...)`) as a list, also when a timeout flushes a batch of one. Payloads are JSON-encoded as pydantic does it (sets as lists, enums as their values). The request carries:

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `Idempotency-Key` | The artifact's ID (for a batch, a key derived from all IDs), the same on every retry |
| `X-Flock-Correlation-Id` | The artifact's correlation ID |
| `Authorization`, your header, `X-Flock-Signature` | From the endpoint's `auth` and `sign` |

### Retries

A timeout, a connection error, HTTP 408, 429 and 5xx are retried, up to `retries` times. The wait is the target's advice (`Retry-After`, `retry-after-ms`) plus an exponential backoff with jitter (0.5-1 s, then 1-2 s, ...), at most 60 s. Other answers, such as 400 or 404, fail at once. The idempotency key lets the target drop a retried request it already processed.

### Order

Deliveries of **one correlation** go out one after another, in the order they were scheduled: a game's moves reach the target in the order they were made, also when one waits for a retry. Deliveries of **different correlations** go out concurrently. The endpoint's `rate_limit` spaces their requests out, and each endpoint keeps up to 100 connections open; `flock.shutdown()` closes them.

---

## Receipts

Every delivery ends with one receipt, in the delivery's correlation, readable by those who could read what was delivered (a batch of mixed visibilities gives its receipt to the sink alone):

```python
from flock import Delivered, DeliveryFailed
```

| `Delivered` | |
|---|---|
| `sink`, `method`, `target` | Who sent what where (`"myapp:/billing"`) |
| `status` | The HTTP status (2xx) |
| `attempts`, `latency_ms` | Requests sent, and the time from the first to the answer |
| `artifact_ids` | The delivered artifacts |
| `response_error` | Why the answer did not parse into the `response` type, else `None` |

| `DeliveryFailed` | |
|---|---|
| `sink`, `method`, `target`, `artifact_ids` | As above |
| `status` | The last HTTP status, `None` without an answer |
| `attempts` | Requests sent (0 when a secret was missing) |
| `error` | What went wrong, with the start of the target's answer |

Receipts are artifacts like any other, so agents can consume them, for example to escalate failed deliveries:

```python
flock.agent("ops").consumes(DeliveryFailed).publishes(Incident)
```

The dashboard's activity timeline counts a `DeliveryFailed` as an error, as it does a workflow error.

---

## Sinks and webhooks

[Webhook notifications](webhooks.md) send every artifact of a REST publish request to the URL that request names: the caller chooses where it hears back. A sink is declared in the flock: it chooses what it delivers with a subscription, sends it to a named system with that system's secrets, keeps the order per correlation and leaves a receipt on the blackboard. The two work side by side.

---

## Testing

Sinks send with [httpx](https://www.python-httpx.org/), so [respx](https://lundberg.github.io/respx/) mocks their targets:

```python
import httpx
import respx


async def test_billing_replies_reach_myapp():
    flock = Flock(endpoints={"myapp": Endpoint("https://myapp.test")})
    flock.sink("billing-api").consumes(Reply).post("myapp:/billing")

    with respx.mock() as router:
        route = router.post("https://myapp.test/billing").mock(return_value=httpx.Response(200))
        await flock.publish(Reply(customer="ada", text="Refunded"))
        await flock.run_until_idle()

    assert route.call_count == 1
```
