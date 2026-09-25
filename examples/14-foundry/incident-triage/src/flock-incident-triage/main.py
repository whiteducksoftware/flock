"""Incident triage as a Microsoft Foundry hosted agent.

One Flock application, two agents, one public output. Every Responses request
runs as its own isolated Flock workflow; model inference uses the hosted
agent's managed identity (no API keys) and a bounded completion-token limit.

Model access follows the official Foundry samples: the platform injects
``FOUNDRY_PROJECT_ENDPOINT``; calls go to ``<endpoint>/openai/v1`` with an Entra
token for ``https://ai.azure.com/.default`` from the agent identity.

Local smoke test (no Azure needed):
    FLOCK_SAMPLE_OFFLINE=1 FLOCK_FOUNDRY_LOCAL_DEV=1 uv run --extra azure --extra foundry \
        python examples/14-foundry/incident-triage/src/flock-incident-triage/main.py
    curl -N localhost:8088/responses -H 'content-type: application/json' \
        -d '{"input": "Checkout requests are timing out.", "stream": true}'
"""

from __future__ import annotations

import os


# Let the Foundry host own OpenTelemetry: must be set before importing flock.
os.environ.setdefault("FLOCK_AUTO_TRACE", "false")

from pydantic import BaseModel, Field  # noqa: E402

from flock import (  # noqa: E402
    DSPyEngine,
    Flock,
    FlockApplication,
    WorkflowContext,
    flock_type,
)
from flock.components.agent import EngineComponent  # noqa: E402
from flock.integrations.foundry import (  # noqa: E402
    FoundryResponsesAdapter,
    IdentityPolicy,
    foundry_headers,
)
from flock.utils.runtime import EvalResult  # noqa: E402


@flock_type
class IncidentRequest(BaseModel):
    report: str
    history: list[dict[str, str]] = Field(default_factory=list)


@flock_type
class IncidentTriage(BaseModel):
    """Internal: severity and affected component. Never returned to callers."""

    severity: str = Field(description="low, medium, high or critical")
    component: str = Field(description="The affected system component")


@flock_type
class IncidentSummary(BaseModel):
    summary: str = Field(description="Two sentences for the on-call engineer")


OFFLINE = os.environ.get("FLOCK_SAMPLE_OFFLINE") == "1"
PROJECT_ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
DEPLOYMENT = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-5.4-mini")
MODEL = f"azure/{DEPLOYMENT}"
MAX_COMPLETION_TOKENS = int(os.environ.get("MAX_COMPLETION_TOKENS", "4000"))
# Bounded per replica: a burst beyond it is answered with rate_limit_exceeded
# instead of exhausting the container (1 CPU / 2 GiB in azure.yaml).
MAX_ACTIVE_WORKFLOWS = int(os.environ.get("MAX_ACTIVE_WORKFLOWS", "8"))
FOUNDRY_SCOPE = "https://ai.azure.com/.default"


def _token_provider():
    """Created ONCE per process and shared by every workflow.

    ``DefaultAzureCredential`` uses the hosted agent's Entra agent identity in
    Foundry and ``az login`` locally. A provider per workflow would mean a new
    credential, a token fetch and a cached LiteLLM client per request.
    """
    from flock.engines.auth.azure import get_default_azure_token_provider

    return get_default_azure_token_provider(scopes=(FOUNDRY_SCOPE,))


if not OFFLINE and not PROJECT_ENDPOINT:
    raise SystemExit(
        "FOUNDRY_PROJECT_ENDPOINT is not set (it is injected in Foundry). "
        "Set it for local runs, or use FLOCK_SAMPLE_OFFLINE=1."
    )
TOKEN_PROVIDER = None if OFFLINE else _token_provider()


class OfflineEngine(EngineComponent):
    """Deterministic stand-in so the sample runs without a model."""

    async def evaluate(self, agent, ctx, inputs, output_group) -> EvalResult:
        payload = inputs.artifacts[0].payload
        if agent.name == "triage":
            severity = "high" if "timing out" in payload["report"].lower() else "low"
            result = IncidentTriage(severity=severity, component="checkout")
        else:
            result = IncidentSummary(
                summary=f"{payload['severity'].upper()} incident in {payload['component']}."
            )
        return EvalResult.from_object(result, agent=agent)


def _engine(context: WorkflowContext) -> EngineComponent:
    if OFFLINE:
        return OfflineEngine()
    return DSPyEngine(
        model=MODEL,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        max_retries=3,
        no_output=True,
        stream=False,
        lm_kwargs={
            # LiteLLM's Azure v1 path calls <project endpoint>/openai/v1 - the
            # same URL AIProjectClient.get_openai_client() uses - and re-invokes
            # the token provider per request.
            "api_base": PROJECT_ENDPOINT,
            "api_version": "v1",
            "azure_ad_token_provider": TOKEN_PROVIDER,
            # Correlates model calls with this Foundry request (not an auth key).
            "extra_headers": foundry_headers(context),
        },
    )


def build_flock(context: WorkflowContext) -> Flock:
    """Called once per request: a fresh, isolated blackboard per workflow."""
    flock = Flock(MODEL, no_output=True)
    flock.agent("triage").description(
        "Classify the incident report; use the conversation history for context."
    ).consumes(IncidentRequest).publishes(IncidentTriage).with_engines(_engine(context))
    flock.agent("summarizer").description(
        "Write a short, actionable summary for the on-call engineer."
    ).consumes(IncidentTriage).publishes(IncidentSummary).with_engines(_engine(context))
    return flock


application = FlockApplication(
    factory=build_flock,
    input_type=IncidentRequest,
    output_types=(IncidentSummary,),
    required_output_types=(IncidentSummary,),
    default_timeout=120,
    max_active_workflows=MAX_ACTIVE_WORKFLOWS,
)

host = FoundryResponsesAdapter(
    application,
    history_mode="conversation",
    input_mapper=lambda turn: IncidentRequest(
        report=turn.text, history=turn.history_dicts()
    ),
    output_mapper=lambda summary: summary.summary,
    identity=IdentityPolicy(
        local_development=os.environ.get("FLOCK_FOUNDRY_LOCAL_DEV") == "1"
    ),
    drain_timeout=5,
)
app = host.app  # ASGI entry point for other servers (keep it the root app)


if __name__ == "__main__":
    host.run()
