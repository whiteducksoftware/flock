---
title: Microsoft Foundry Hosted Agents
description: Deploy a Flock application as a Microsoft Foundry hosted agent with the optional foundry extra
tags:
  - hosting
  - azure
  - foundry
---

# Microsoft Foundry hosted agents

`flock.integrations.foundry` hosts a
[`FlockApplication`](applications.md) behind Foundry's hosted-agent
**Responses** protocol. It uses the official
[`azure-ai-agentserver-responses`](https://pypi.org/project/azure-ai-agentserver-responses/)
host for HTTP, SSE, response storage, background mode, polling and
cancellation, and maps every request to one isolated Flock workflow. Your
agents, typed artifacts and subscriptions stay unchanged.

```bash
uv add "flock-core[foundry]"         # adds the Azure AgentServer SDK
uv add "flock-core[azure,foundry]"   # plus azure-identity for managed-identity model calls
```

Like the [Dapr store](dapr-state-store.md), the integration ships with
`flock-core` and its dependencies are an optional extra: without the extra,
`flock-core` never installs Azure packages, and `import flock` never imports
them (`flock.integrations.foundry` loads the SDK only when an adapter symbol is
used). Hosting in
Foundry does not require a Foundry-hosted model: model choice stays in your
engines.

## Minimal agent

```python
from flock.integrations.foundry import FoundryResponsesAdapter

host = FoundryResponsesAdapter(
    application,                       # your FlockApplication
    history_mode="conversation",       # or "stateless"
    input_mapper=lambda turn: IncidentRequest(
        report=turn.text,                  # current user text
        history=turn.history_dicts(),      # earlier messages, roles preserved
    ),
    output_mapper=lambda summary: summary.summary,  # default: JSON text
)

if __name__ == "__main__":
    host.run()          # 0.0.0.0, $PORT or 8088, SIGTERM-aware
```

`host.app` is the ASGI application (the SDK host itself). Serve it as the
root application - mounting it under another app skips its lifespan (task
manager and graceful shutdown).

A complete, deployable sample lives in
[`examples/14-foundry/incident-triage`](https://github.com/whiteducksoftware/flock/tree/main/examples/14-foundry/incident-triage) (official Foundry sample layout; `azure.yaml` validates against the azd schema).

## How requests map to workflows

| Foundry | Flock |
|---|---|
| `response_id` | `WorkflowContext.workflow_id` - one workflow per response |
| `conversation` id | `session_id` (turns of one conversation can be serialized with `history="conversation"` on the application) |
| `x-agent-user-id` (`platform_context.user_id_key`) | `principal_id` through `IdentityPolicy` - an opaque per-user partition key, not an Entra tenant id, never forwarded |
| `x-agent-foundry-call-id` | `attributes["foundry.call_id"]`; forward it on Foundry calls with `foundry_headers(context)` |
| Sandbox session (`agent_session_id`) | `attributes["foundry.session_id"]` - a third, separate identity |
| Stored history (`get_history()`) | `TextTurn.history` in conversation mode; historical inputs are never re-run |
| Each public output | One assistant message output item (streamed per artifact) |

## Response modes and outcomes

All four modes are handled by the SDK host: non-streaming, streaming (SSE),
background (`background: true`, needs `store: true`, poll with
`GET /responses/{id}`) and background + streaming. A disconnected background
stream keeps running; `POST /responses/{id}/cancel` cancels it. A foreground
client disconnect cancels only its own workflow.

| Workflow result | Response |
|---|---|
| `succeeded` | `completed` |
| `failed` | `failed`, `server_error` with a safe failure code (never exception text) |
| `timed_out` | `failed`, "did not finish in time" |
| `cancelled` | `cancelled` |
| unsupported request | `failed`, `invalid_prompt` - before any agent runs |

Unsupported and rejected explicitly: tools and `tool_choice` other than
`auto`/`none`, non-text input (images, files, tool outputs), non-user input
roles, `instructions`, `max_output_tokens`, `temperature`, `top_p`,
`reasoning`, structured `text.format`. Client-driven function-tool round trips
and steerable conversations are not implemented.

## Identity

Inside Foundry the gateway sets `x-agent-user-id`; requests without it are
rejected instead of falling back to a shared principal. Applications that
partition nothing by principal (public outputs, no per-user history) can opt
out with `IdentityPolicy(required=False)`; such requests run with
`principal_id=None`. The header is trusted only inside a Foundry hosted
container. For local runs enable
`IdentityPolicy(local_development=True)` explicitly - it is refused when
`FOUNDRY_HOSTING_ENVIRONMENT` is set. Map the user key to your own principal
with `IdentityPolicy(resolve=...)`.

## Model access with managed identity

Each hosted agent runs as its own Microsoft Entra **agent identity** (the
project's managed identity only pulls images). Give the agent identity access
to the model it calls:

- Calls through the Foundry **project endpoint** need no extra role.
- Calls to an account-level Azure OpenAI endpoint need **Cognitive Services
  OpenAI User** (or **Foundry User**) on that resource.

Flock already supports Entra ID for LiteLLM/DSPy models - create the token
provider **once per process** and share it across workflows:

```python
from flock import DSPyEngine
from flock.engines.auth.azure import get_default_azure_token_provider
from flock.integrations.foundry import foundry_headers

TOKEN_PROVIDER = get_default_azure_token_provider()   # renewable, one per process


def build_flock(context):
    engine = DSPyEngine(
        model="azure/prod-reasoning",
        max_completion_tokens=4000,        # reasoning models reject max_tokens
        max_retries=3,
        no_output=True,
        stream=False,
        lm_kwargs={
            "azure_ad_token_provider": TOKEN_PROVIDER,
            "extra_headers": foundry_headers(context),
        },
    )
    ...
```

To call models through the Foundry project endpoint (as the official samples
do), pass `api_base=os.environ["FOUNDRY_PROJECT_ENDPOINT"]` and
`api_version="v1"` in `lm_kwargs` and create the provider with
`scopes=("https://ai.azure.com/.default",)`: LiteLLM then calls
`<project endpoint>/openai/v1`, exactly like `AIProjectClient.get_openai_client()`.
For an account-level `*.openai.azure.com` endpoint use the default
`AZURE_COGNITIVE_SERVICES_SCOPE`. Never persist tokens or rely on a one-time
token: the provider refreshes them.

## Telemetry

The Foundry host configures OpenTelemetry (Azure Monitor) by default
(`observability="sdk"`). Importing Flock would otherwise install its own tracer
provider first, so set `FLOCK_AUTO_TRACE=false` (the sample does) or
`FLOCK_DISABLE_TELEMETRY_AUTOSETUP=1` before importing Flock. The adapter logs
a warning when it detects the conflict. Use `observability="none"` to own
telemetry yourself. `host.run()` also disables DSPy's in-memory LM history.

## Capacity

Every request builds its own Flock instance and runs its own model calls, so
bound the work one replica accepts:

```python
application = FlockApplication(..., max_active_workflows=8)
```

Requests beyond the limit are answered immediately with `failed` /
`rate_limit_exceeded` (the client retries) instead of queueing or exhausting
the container's memory. The adapter logs a warning when the application admits
unlimited workflows. Size the limit to the container resources in `azure.yaml`
and to your model deployment's quota; Foundry scales replicas horizontally.

## Readiness and shutdown

`GET /readiness` returns 503 until the application validated its contract
(on the first probe) and again while it drains. On `SIGTERM` the SDK stops
accepting requests; running workflows get `drain_timeout` seconds to finish,
then they are cancelled. Interrupted work is never reported as successful.

## Compatibility and limits

| | |
|---|---|
| SDK | `azure-ai-agentserver-responses` 2.1.x (with `azure-ai-agentserver-core` 2.1.x) |
| Protocol | Container Responses protocol `2.0.0` (1.0.0 is blocked by the platform) |
| Runtime | Linux AMD64 image, plain HTTP on port 8088 |
| Service status | Hosted agents are generally available; long-running resilience (`resilient_background`) is preview - check [regional availability](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents) |
| flock-core | ≥ 0.5.612 with the `foundry` extra (OpenTelemetry ≥ 1.43) |
| Client SDK | `azure-ai-projects` ≥ 2.5 needs `openai>=3`, which cannot share an environment with flock-core's LiteLLM; run the client elsewhere or pin `azure-ai-projects>=2.3,<2.5` |

## Not included: crash recovery

Stored background responses are **not** crash-resumable. The SDK can persist
response state, but a Flock workflow's tasks, partial joins and batches and
external tool effects are not checkpointed. If the process is killed without a
graceful shutdown, affected responses stay `in_progress` in storage: treat
them as failed after your client timeout and resubmit with a new request (the
SDK logs this at start-up as "resilience: DISABLED"). Checkpoint/resume is a
separate, future capability.

## Calling a deployed agent

```python
from azure.ai.projects import AIProjectClient   # separate environment, see above
from azure.identity import DefaultAzureCredential

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project,
    project.get_openai_client(agent_name="flock-incident-triage") as client,
):
    conversation = client.conversations.create()
    response = client.responses.create(
        input="Checkout requests are timing out.",
        extra_body={"conversation": conversation.id},
    )
    print(response.output_text)
```

Reuse the conversation id for the next turn - never the response id.
