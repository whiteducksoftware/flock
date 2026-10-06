"""Shared incident-triage application used by the examples in this folder.

The engines are deterministic so the examples run without a model API key.
Swap them for ``DSPyEngine(...)`` (or drop ``.with_engines``) to use an LLM -
nothing else about the application changes.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from flock import Flock, FlockApplication, flock_type
from flock.components.agent import EngineComponent
from flock.utils.runtime import EvalInputs, EvalResult


@flock_type
class IncidentRequest(BaseModel):
    """What the caller sends."""

    report: str
    history: list[dict[str, str]] = Field(default_factory=list)


@flock_type
class IncidentTriage(BaseModel):
    """Internal intermediate artifact - never exposed to callers."""

    severity: str
    component: str


@flock_type
class IncidentSummary(BaseModel):
    """The public result."""

    summary: str


class TriageEngine(EngineComponent):
    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        request = IncidentRequest(**inputs.artifacts[0].payload)
        await asyncio.sleep(0.2)  # pretend to think
        severity = "high" if "timing out" in request.report.lower() else "low"
        return EvalResult.from_object(
            IncidentTriage(severity=severity, component="checkout"), agent=agent
        )


class SummaryEngine(EngineComponent):
    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        triage = IncidentTriage(**inputs.artifacts[0].payload)
        await asyncio.sleep(0.2)
        return EvalResult.from_object(
            IncidentSummary(
                summary=f"{triage.severity.upper()} severity incident in {triage.component}."
            ),
            agent=agent,
        )


def build_flock() -> Flock:
    """Called once per workflow: every run gets its own isolated blackboard."""
    flock = Flock(no_output=True)
    flock.agent("triage").consumes(IncidentRequest).publishes(
        IncidentTriage
    ).with_engines(TriageEngine())
    flock.agent("summarizer").consumes(IncidentTriage).publishes(
        IncidentSummary
    ).with_engines(SummaryEngine())
    return flock


application = FlockApplication(
    factory=build_flock,
    input_type=IncidentRequest,
    output_types=(IncidentSummary,),
    required_output_types=(IncidentSummary,),
)
