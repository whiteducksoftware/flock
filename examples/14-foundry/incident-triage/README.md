# Incident triage — a Flock application as a Foundry hosted agent

Two Flock agents (`triage` → `summarizer`) behind the Foundry Responses
protocol. Each request is its own isolated workflow; only `IncidentSummary`
is returned. Model calls use the hosted agent's managed identity and a
bounded completion-token limit.

Layout follows the official Foundry bring-your-own Responses samples:
`azure.yaml` at the top, the agent in `src/flock-incident-triage/` (`main.py`,
`Dockerfile`, `requirements.txt`, `.env.example`).

## Run locally

No model needed (`FLOCK_SAMPLE_OFFLINE=1` swaps in deterministic engines):

```bash
FLOCK_SAMPLE_OFFLINE=1 FLOCK_FOUNDRY_LOCAL_DEV=1 \
  uv run --extra azure --extra foundry python examples/14-foundry/incident-triage/src/flock-incident-triage/main.py

curl localhost:8088/readiness
curl -N localhost:8088/responses -H 'content-type: application/json' \
  -d '{"input": "Checkout requests are timing out.", "stream": true}'
curl localhost:8088/responses -H 'content-type: application/json' \
  -d '{"input": "Checkout requests are timing out.", "background": true}'
curl localhost:8088/responses/<id>             # poll
curl -X POST localhost:8088/responses/<id>/cancel
```

`FLOCK_FOUNDRY_LOCAL_DEV=1` enables local-development identity (no gateway
user header). Never set it in Foundry - the adapter refuses it there. With a
real model, drop `FLOCK_SAMPLE_OFFLINE`, `az login`, and set
`FOUNDRY_PROJECT_ENDPOINT` and `AZURE_AI_MODEL_DEPLOYMENT_NAME` (see
`.env.example`).

Locally the SDK's Azure resource detector logs an IMDS (169.254.169.254)
connection error; that is expected outside Azure.

## Model access

Like the official samples, the agent calls models through the project:
`<FOUNDRY_PROJECT_ENDPOINT>/openai/v1` with an Entra token for
`https://ai.azure.com/.default` from `DefaultAzureCredential` (the agent
identity in Foundry). Flock's `DSPyEngine` gets `api_base=<project endpoint>`,
`api_version="v1"` and a token provider created once per process; LiteLLM
refreshes the token per request. `max_completion_tokens` bounds the output
(reasoning deployments reject `max_tokens`).

## Build the image

`requirements.txt` installs `flock-core[azure,foundry]` from PyPI - or, before a
release, from a wheel you drop into `wheels/`:

```bash
# from the repository root, only needed until this flock-core version is on PyPI
uv build --wheel -o examples/14-foundry/incident-triage/src/flock-incident-triage/wheels
cd examples/14-foundry/incident-triage/src/flock-incident-triage
docker build --platform linux/amd64 -t flock-incident-triage .
```

On Apple silicon, run the amd64 image in Foundry (or build a native image for
local runs); QEMU emulation of the amd64 image may crash locally.

## Deploy

1. `azd up` from this folder (Azure Developer CLI with the `azure.ai.agents`
   extension). `azure.yaml` provisions a `gpt-5.4-mini` deployment, builds the
   image remotely (`docker.remoteBuild`) and declares the Responses protocol
   `2.0.0`. It validates against the azd `v1.0` schema.
2. Permissions: deploying needs **Foundry Project Manager** on the project;
   the agent's own Entra **agent identity** calls the model through the
   project endpoint (no extra role).
3. Configuration: `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `MAX_COMPLETION_TOKENS`,
   `MAX_ACTIVE_WORKFLOWS` (concurrent workflows per replica, default 8);
   `FOUNDRY_PROJECT_ENDPOINT` and `APPLICATIONINSIGHTS_CONNECTION_STRING` are
   injected by the platform.

## Operate

- **Readiness**: `GET /readiness` is 503 until the Flock contract validated
  and while draining.
- **Logs/traces**: the Foundry host exports to Azure Monitor when
  `APPLICATIONINSIGHTS_CONNECTION_STRING` is set; Flock auto-tracing is off
  (`FLOCK_AUTO_TRACE=false`) so request payloads are not added to spans.
- **Shutdown**: on `SIGTERM` new requests get 503, running workflows get 5 s
  (`drain_timeout`) to finish and are then cancelled; they never report success.
- **Crashes**: responses in flight during a hard kill stay `in_progress` in
  storage - there is no recovery. Clients should time out and resubmit.

## Call the deployed agent

Use a separate Python environment (`azure-ai-projects` ≥ 2.5 needs
`openai>=3`, which cannot be installed next to flock-core):

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project,
    project.get_openai_client(agent_name="flock-incident-triage") as client,
):
    conversation = client.conversations.create()
    first = client.responses.create(
        input="Checkout requests are timing out.",
        extra_body={"conversation": conversation.id},
    )
    follow_up = client.responses.create(
        input="Which component was it?",
        extra_body={"conversation": conversation.id},  # same conversation, new response
    )
    print(follow_up.output_text)
```
