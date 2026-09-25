---
title: Applications (Hosting Flock)
description: Run a Flock application behind your own worker, ASGI service or agent runtime with FlockApplication
tags:
  - hosting
  - applications
  - workflows
---

# Applications: run Flock behind your own host

`flock.serve()` hosts one long-lived blackboard with Flock's own REST API and
dashboard. When Flock is *embedded* - a queue worker, your own ASGI service,
or an agent runtime such as [Microsoft Foundry](foundry.md) - you need
something else: a way to run one request as one isolated workflow, stream its
public results, and get an unambiguous outcome. That is `FlockApplication`.

```python
from flock import Flock, FlockApplication, WorkflowContext, flock_type


def build_flock() -> Flock:
    flock = Flock("azure/gpt-4.1", no_output=True)
    flock.agent("triage").consumes(IncidentRequest).publishes(IncidentTriage)
    flock.agent("summarizer").consumes(IncidentTriage).publishes(IncidentSummary)
    return flock


application = FlockApplication(
    factory=build_flock,
    input_type=IncidentRequest,
    output_types=(IncidentSummary,),          # explicit public allowlist
    required_output_types=(IncidentSummary,),  # success needs one of these
)

async with application.stream(
    IncidentRequest(report="Checkout requests are timing out."),
    context=WorkflowContext(workflow_id="job-42", principal_id="customer-a"),
    timeout=60,
) as workflow:
    async for event in workflow:
        print(event.value)            # IncidentSummary, as soon as it is published
    result = await workflow.result()  # always check the terminal outcome
    result.raise_for_status()
```

`application.run(...)` is the non-streaming shortcut returning the
`WorkflowResult`. Nothing in this API depends on a web framework or on Azure.

## Model

| Concept | Meaning |
|---|---|
| **Workflow** | One execution (a job, a turn). Its `workflow_id` becomes the correlation id of everything it publishes. Not the same as an agent *run* (`Context.task_id`). |
| **Factory** | Builds a fresh `Flock(no_output=True)` per workflow - `factory()` or `factory(context)`, sync or async. Every workflow gets its own blackboard, scheduler state, counters and MCP sessions. |
| **Output contract** | `input_type`, public `output_types`, `required_output_types`, optional `access_policy`. Outputs are never inferred from the agent graph. |
| **WorkflowContext** | `workflow_id`, trusted `principal_id`, optional `session_id`, opaque `attributes`. Resolved by the host from verified identity - never from untrusted payload fields. |
| **WorkflowResult** | `status` (`succeeded`, `failed`, `cancelled`, `timed_out`), `outputs`, a safe `failure` code, `diagnostics`. |

## What counts as an output

A published artifact becomes a `WorkflowEvent` only if all of these hold:

1. its type is in `output_types`;
2. it was produced by one of the application's own agents (not the input);
3. the access policy allows it. By default an artifact is exposed when its
   visibility admits the caller - public artifacts and `TenantVisibility`
   for the caller's `principal_id`; agent-private artifacts never are.

Events are emitted right after the artifact is persisted, in store order.
Streaming is per **artifact** - an output appears when it is published, not
token by token.

## When a workflow is done

By default a workflow is complete when its cascade is quiescent: no agent
task is running and no timer is active.

- **Batches** that are still partial when nothing else is running are flushed
  (no producer remains, so waiting for `BatchSpec.timeout` would only add
  latency). `diagnostics["partial_batches_flushed"]` counts them.
- **Joins and AND gates** that are still incomplete are not waited for; they
  are counted in `diagnostics["incomplete_joins"]`. Use
  `required_output_types` to make such a workflow fail.
- **Scheduled agents** run open-ended, so an application with timers needs an
  explicit `CompletionPolicy(until=...)` and relies on the deadline.

```python
from flock import CompletionPolicy
from flock.core.conditions import Until

application = FlockApplication(
    factory=build_flock,
    input_type=Query,
    output_types=(Hypothesis,),
    completion=CompletionPolicy(
        until=Until.any_field(Hypothesis, field="confidence", predicate=lambda v: v >= 0.9),
        on_condition="stop",   # cancel the remaining work ("drain" lets it finish)
        on_error="stop",       # first agent failure ends the workflow
    ),
)
```

`until` is bound to the workflow automatically (no correlation id needed).
`Until.idle()` is rejected - completion already waits for all of the
workflow's own work.

### Outcomes

| Status | When |
|---|---|
| `succeeded` | Quiescent (or `until` met), every required output produced |
| `failed` | An agent failed (`agent_failed`), work failed outside an agent (`internal_error`), a required output is missing, `until` was not met, the output limit or an iteration limit was hit, a timer or the factory failed |
| `timed_out` | The deadline passed; remaining work was cancelled |
| `cancelled` | `workflow.cancel()`, leaving the `async with` block early, caller cancellation or application shutdown |

Failure messages are fixed, safe text - never exception text, which may
contain private input.

## Cancellation, deadlines and cleanup

The `async with application.stream(...)` block owns the workflow. Leaving it
while the workflow runs cancels it and waits for teardown, in this order:
stop scheduling, component shutdown hooks (timers), cancel and await agent
tasks (bounded by `cancel_grace`), background tasks, MCP connections.
Finishing one workflow never touches another workflow's instance.

Work that blocks the event loop cannot be interrupted: synchronous tools,
synchronous engine paths or thread-bound calls finish (or keep running) on
their own. Prefer async tools. `diagnostics["leftover_tasks"]` reports tasks
that did not stop within the grace period.

## Identity, sessions and retries

- `workflow_id` must be unique. Active ids - and finished ids for
  `id_retention` (default 15 minutes) - are rejected with
  `WorkflowIdConflict`, so a transport retry never launches the same work
  twice. Rejections before a workflow starts (bad input, capacity, draining)
  are raised as `WorkflowRejected` subclasses and leave the id reusable.
- `history="conversation"` requires a `session_id` and runs turns of the same
  principal and session one at a time; other sessions stay concurrent. The
  host maps prior messages into the typed input - historical inputs are never
  republished or re-run.
- `max_active_workflows` (or a custom `AdmissionController`) rejects work
  instead of queueing it.

## Hosting checklist

- **Static models**: define artifact models once, at module level, with unique
  names. The type registry is process-wide.
- **Shared resources outside the factory**: create credentials, Azure token
  providers and persistent stores once and capture them in the factory. A
  token provider per workflow means a new credential, a token fetch and a
  cached LiteLLM client per request.
- **`no_output=True`** is required; the factory must return a fresh instance.
- **Bound concurrency**: set `max_active_workflows` for request-driven hosts; every
  workflow builds its own instance and runs its own model calls.
- **Telemetry**: `FLOCK_AUTO_TRACE` defaults to on and installs a tracer
  provider at import. If your host owns OpenTelemetry, set
  `FLOCK_DISABLE_TELEMETRY_AUTOSETUP=1` (or `FLOCK_AUTO_TRACE=false`) before
  importing Flock. Auto-traced spans include payloads.
- **LM history**: DSPy keeps recent prompts and responses in memory
  process-wide; call `dspy.configure(disable_history=True)` in multi-tenant hosts.
- **MCP**: each workflow opens its own MCP sessions (one per agent execution);
  stdio servers start a process per session.
- **Dashboard**: do not serve the dashboard in the same process - it would
  receive every workflow's live output.
- **Persistent stores**: supported, but agent context is always restricted to
  the workflow's own correlation id; the store itself still holds every
  principal's artifacts, so keep administrative APIs private.

## Not included

Artifact streaming is not model-token streaming. Conversation history is
supplied by the host, not restored from the blackboard. Durable domain memory
needs its own storage. There is no crash recovery: a workflow interrupted by a
process restart is not resumed.

## See also

- [Microsoft Foundry hosted agents](foundry.md) - the `foundry` extra builds on this API
- [Workflow Control](workflow-control.md) - `Until` conditions
- Examples: `examples/13-applications/`
