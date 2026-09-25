"""Shared fixtures: a deterministic Flock application behind the real SDK host."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest
from pydantic import BaseModel, Field


os.environ.setdefault("FLOCK_AUTO_TRACE", "false")

from azure.ai.agentserver.responses import InMemoryResponseProvider  # noqa: E402

from flock import Flock, FlockApplication, WorkflowContext, flock_type  # noqa: E402
from flock.components.agent import EngineComponent  # noqa: E402
from flock.integrations.foundry import (  # noqa: E402
    FoundryResponsesAdapter,
    IdentityPolicy,
)
from flock.utils.runtime import EvalResult  # noqa: E402


@flock_type(name="FoundryQuestion")
class Question(BaseModel):
    text: str
    history: list[dict[str, str]] = Field(default_factory=list)


@flock_type(name="FoundryAnswer")
class Answer(BaseModel):
    answer: str


class Recorder:
    """What the fake agent saw, per workflow."""

    def __init__(self) -> None:
        self.inputs: list[Question] = []
        self.contexts: list[WorkflowContext] = []
        self.cancelled = 0
        self.release = asyncio.Event()
        self.started = asyncio.Event()


class AnswerEngine(EngineComponent):
    recorder: Any = None

    async def evaluate(self, agent, ctx, inputs, output_group) -> EvalResult:
        question = Question(**inputs.artifacts[0].payload)
        self.recorder.inputs.append(question)
        if question.text.startswith("slow"):
            self.recorder.started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                self.recorder.cancelled += 1
                raise
        if question.text.startswith("fail"):
            raise RuntimeError("private detail that must not leak")
        return EvalResult.from_object(
            Answer(answer=f"echo:{question.text}"), agent=agent
        )


def make_adapter(
    recorder: Recorder,
    *,
    history_mode: str = "stateless",
    identity: IdentityPolicy | None = None,
    application: FlockApplication | None = None,
    app_options: dict[str, Any] | None = None,
    **kwargs: Any,
) -> FoundryResponsesAdapter:
    def factory(context: WorkflowContext) -> Flock:
        recorder.contexts.append(context)
        flock = Flock(no_output=True)
        flock.agent("answerer").consumes(Question).publishes(Answer).with_engines(
            AnswerEngine(recorder=recorder)
        )
        return flock

    app = application or FlockApplication(
        factory,
        input_type=Question,
        output_types=(Answer,),
        required_output_types=(Answer,),
        **(app_options or {}),
    )
    return FoundryResponsesAdapter(
        app,
        input_mapper=lambda turn: Question(
            text=turn.text, history=turn.history_dicts()
        ),
        output_mapper=lambda answer: answer.answer,
        history_mode=history_mode,
        identity=identity or IdentityPolicy(local_development=True),
        observability="none",
        store=InMemoryResponseProvider(),
        **kwargs,
    )


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()
