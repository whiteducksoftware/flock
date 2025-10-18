"""Concrete demo wiring matching the design document."""

from __future__ import annotations

import sys
from pathlib import Path


if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.store import BlackboardStore
from flock.registry import flock_tool, flock_type, type_registry
from flock.utils.runtime import EvalInputs, EvalResult
from flock.utils.utilities import LoggingUtility, MetricsUtility


if TYPE_CHECKING:
    from flock.core import AgentBuilder


@flock_type
class Idea(BaseModel):
    topic: str
    genre: str


@flock_type
class Movie(BaseModel):
    fun_title: str = Field(description="Fun title in CAPS")
    runtime: int = Field(ge=60, le=400)
    synopsis: str


@flock_type
class Tagline(BaseModel):
    line: str


@flock_tool
def announce(tagline: Tagline) -> dict[str, str]:
    return {"announced": tagline.line}


class MovieEngine(EngineComponent):
    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        idea = Idea(**inputs.artifacts[0].payload)
        synopsis = f"{idea.topic} told as a {idea.genre} adventure."
        movie = Movie(fun_title=idea.topic.upper(), runtime=120, synopsis=synopsis)
        artifact = Artifact(
            type=type_registry.name_for(Movie),
            payload=movie.model_dump(),
            produced_by=agent.name,
        )
        return EvalResult(artifacts=[artifact])


class TaglineEngine(EngineComponent):
    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        movie = Movie(**inputs.artifacts[0].payload)
        tagline = Tagline(line=f"Don't miss {movie.fun_title}!")
        artifact = Artifact(
            type=type_registry.name_for(Tagline),
            payload=tagline.model_dump(),
            produced_by=agent.name,
        )
        return EvalResult(artifacts=[artifact])


def create_demo_orchestrator(
    model: str | None = None,
    *,
    store: BlackboardStore | None = None,
) -> tuple[Flock, dict[str, AgentBuilder]]:
    orchestrator = Flock(model, store=store)

    movie = (
        orchestrator.agent("movie")
        .description("Generate a movie concept.")
        .consumes(Idea)
        .publishes(Movie)
        .only_for("tagline", "presenter")
        .with_utilities(MetricsUtility(), LoggingUtility())
        .with_engines(MovieEngine())
    )

    tagline = (
        orchestrator.agent("tagline")
        .description("Generate a tagline.")
        .consumes(Movie, where=lambda m: 60 <= m.runtime <= 200, from_agents={"movie"})
        .publishes(Tagline)
        .with_engines(TaglineEngine())
    )

    presenter = (
        orchestrator.agent("presenter")
        .description("Announce the winner.")
        .consumes(Tagline, mode="both")
        .calls(announce)
    )

    return orchestrator, {"movie": movie, "tagline": tagline, "presenter": presenter}


__all__ = [
    "Idea",
    "Movie",
    "Tagline",
    "announce",
    "create_demo_orchestrator",
]

if __name__ == "__main__":
    import asyncio

    async def _demo_run() -> None:
        orchestrator, agents = create_demo_orchestrator()
        idea = Idea(topic="AI agents collaborating", genre="comedy")
        outputs = await orchestrator.arun(agents["movie"], idea)
        await orchestrator.run_until_idle()
        for artifact in outputs:
            print(f"{artifact.type}: {artifact.payload}")

    asyncio.run(_demo_run())
