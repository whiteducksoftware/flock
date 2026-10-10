"""
Decision Models: LLM vs Decision Models Race on 100 arXiv Abstracts

Several agents sort the same 100 arXiv abstracts into research fields at the
same time:

- `llm_sorter`: a normal LLM agent that publishes `LLMField` (LLM_MODEL)
- one decision agent per entry in DECISION_MODELS, each `.decides(ResearchField)`;
  by default Microsoft-Decision-1 on Azure AI Foundry, more can be enabled

Every agent works through the papers one at a time (CONCURRENCY = 1), so the
race compares time per paper rather than how well a backend absorbs parallel
requests; a local model serves one request at a time anyway. All contenders
get the same field descriptions. Live progress bars show the race. The report
lists total time, time per paper and agreement with arXiv's primary category
for every contender, plus the papers where anyone disagreed with arXiv.

Before the race every decision model gets one warm-up request. Models whose
keys are missing or whose server does not answer are skipped.

Each paper is published with its own correlation id, and the LLM agent runs
without conversation context, so no contender sees another one's answer.

🎛️  CONFIGURATION:
- LLM_MODEL (DEFAULT_MODEL, default openai/gpt-4.1)
- DECISION_MODELS: which decision models race
  - azure/decision-1: AZURE_API_BASE, AZURE_API_KEY
  - openai/gpt-6-luna: OPENAI_API_KEY
  - jev/jev-latest: JEV_API_KEY
  - local/clef-flash: see 01_ticket_triage.py for serving it with llama.cpp
- CONCURRENCY: parallel runs per agent (same for every contender)

Data: data/arxiv_abstracts.json, 100 recent abstracts from 18 arXiv categories
with their primary category (arXiv metadata, CC0).
"""

import asyncio
import json
import os
import statistics
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from flock import Choice, Decision, DSPyEngine, Flock
from flock.decisions.providers import DecisionQuestion, resolve_provider
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
LLM_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-4.1")
DECISION_MODELS = [
    "azure/decision-1",
    # More contenders (each needs its configuration, see the docstring):
    # "openai/gpt-6-luna",
    # "jev/jev-latest",
    # "local/clef-flash",
]
CONCURRENCY = 1
DATA = Path(__file__).parent / "data" / "arxiv_abstracts.json"
# ============================================================================

console = Console()


@flock_type
class Paper(BaseModel):
    """An arXiv paper to sort into a research field."""

    arxiv_id: str
    title: str
    abstract: str


class ResearchField(Choice):
    """Which research field is this arXiv paper's primary field?"""

    machine_learning = (
        "Machine learning: learning algorithms, deep learning theory, "
        "reinforcement learning, ML safety and interpretability"
    )
    computer_vision = "Computer vision: images, video, 3D scenes, visual generation"
    language = (
        "Natural language processing: language models, text, tokenization, "
        "efficient LLM inference"
    )
    robotics = "Robotics: robot control, motion planning, manipulation, autonomy"
    astrophysics = "Astrophysics: stars, galaxies, interstellar matter, cosmology"
    quantum_physics = "Quantum physics and quantum information theory"
    biology = "Biology and neuroscience: brains, neurons, cognition, evolution, genes"
    economics = "Economics: markets, firms, labour, finance, development"
    mathematics = "Pure mathematics: number theory, algebra, geometry, combinatorics"


FieldName = Literal[
    "machine_learning",
    "computer_vision",
    "language",
    "robotics",
    "astrophysics",
    "quantum_physics",
    "biology",
    "economics",
    "mathematics",
]


@flock_type
class LLMField(BaseModel):
    """The research field the LLM picked for a paper."""

    field: FieldName = Field(description="The paper's primary research field")


FIELD_GUIDE = "\n".join(
    f"- {name}: {description}"
    for name, description in ResearchField.__options__.items()
)


def agent_name(model: str) -> str:
    return "decide_" + model.replace("/", "_").replace("-", "_").replace(".", "_")


async def ready_models() -> list[str]:
    """Warm up every decision model once; keep the ones that answer."""
    question = DecisionQuestion(
        name=ResearchField.__name__,
        instructions=ResearchField.__question__,
        options=ResearchField.__options__,
    )
    ready = []
    for model in DECISION_MODELS:
        try:
            await resolve_provider(model).decide(
                "Paper: A new bound on prime gaps.", question
            )
            ready.append(model)
        except Exception as exc:
            console.print(f"[dim]skipping {model}: {exc}[/dim]")
    return ready


def build_flock(models: list[str]) -> Flock:
    flock = Flock(LLM_MODEL, no_output=True)
    (
        flock.agent("llm_sorter")
        .description(
            "Classify the arXiv paper into its primary research field.\n" + FIELD_GUIDE
        )
        .consumes(Paper)
        # No conversation context: the LLM must not see the decision models'
        # answers about the same paper (they share its correlation id).
        .with_engines(DSPyEngine(model=LLM_MODEL, enable_context=False))
        .publishes(LLMField)
        .max_concurrency(CONCURRENCY)
    )
    for model in models:
        (
            flock.agent(agent_name(model))
            .consumes(Paper)
            .decides(ResearchField, model=model)
            .max_concurrency(CONCURRENCY)
        )
    return flock


async def picks(flock: Flock) -> dict[str, dict[str, object]]:
    """contender -> paper id -> output artifact."""
    llm_type = type_registry.name_for(LLMField)
    decision_type = type_registry.name_for(Decision.of(ResearchField))
    out: dict[str, dict[str, object]] = {}
    for artifact in await flock.store.list():
        if artifact.type in (llm_type, decision_type):
            out.setdefault(artifact.produced_by, {})[artifact.correlation_id] = artifact
    return out


def pick_of(artifact) -> str:
    return artifact.payload.get("field") or artifact.payload["choice"]


async def race(flock: Flock, contenders: dict[str, str], papers: list[dict]) -> float:
    """Publish all papers, run every agent, show live progress; return start time."""
    done = asyncio.Event()

    async def watch() -> None:
        with Progress(
            TextColumn("{task.description}"),
            BarColumn(bar_width=36),
            TextColumn("{task.completed:>3}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            tasks = {
                agent: progress.add_task(label, total=len(papers))
                for agent, label in contenders.items()
            }
            while True:
                current = await picks(flock)
                for agent, task in tasks.items():
                    completed = len(current.get(agent, {}))
                    progress.update(task, completed=completed)
                    if completed == len(papers):
                        progress.stop_task(task)
                if done.is_set():
                    break
                await asyncio.sleep(0.05)

    started = time.time()
    for paper in papers:
        await flock.publish(
            Paper(
                arxiv_id=paper["arxiv_id"],
                title=paper["title"],
                abstract=paper["abstract"],
            ),
            correlation_id=paper["arxiv_id"],
        )
    watcher = asyncio.create_task(watch())
    await flock.run_until_idle()
    done.set()
    await watcher
    return started


async def report(
    flock: Flock, contenders: dict[str, str], papers: list[dict], started: float
) -> None:
    results = await picks(flock)
    truth = {p["arxiv_id"]: p["field"] for p in papers}
    n = len(papers)

    summary = Table(title=f"{n} arXiv abstracts, {CONCURRENCY} at a time per agent")
    summary.add_column("Contender")
    summary.add_column("Done", justify="right")
    summary.add_column("Total s", justify="right")
    summary.add_column("ms / paper", justify="right")
    summary.add_column("Request p50 ms", justify="right")
    summary.add_column("Agrees with arXiv", justify="right")
    finish_times = {}
    for agent, label in contenders.items():
        outputs = results.get(agent, {})
        if not outputs:
            summary.add_row(label, "0", "—", "—", "—", "—")
            continue
        total = max(a.created_at.timestamp() for a in outputs.values()) - started
        finish_times[label] = total
        hits = sum(pick_of(a) == truth[cid] for cid, a in outputs.items())
        latencies = [a.payload.get("latency_ms") for a in outputs.values()]
        request_p50 = f"{statistics.median(latencies):.0f}" if all(latencies) else "—"
        summary.add_row(
            label,
            f"{len(outputs)}",
            f"{total:.1f}",
            f"{total / len(outputs) * 1000:.0f}",
            request_p50,
            f"{hits}/{len(outputs)}",
        )
    console.print(summary)

    disagreements = Table(title="Papers where a contender disagreed with arXiv")
    disagreements.add_column("Paper", max_width=40, no_wrap=True)
    disagreements.add_column("arXiv")
    for label in contenders.values():
        disagreements.add_column(label.split()[-1], no_wrap=True)
    for paper in papers:
        cid = paper["arxiv_id"]
        row = []
        for agent in contenders:
            artifact = results.get(agent, {}).get(cid)
            pick = pick_of(artifact) if artifact else "—"
            row.append(pick if pick == truth[cid] else f"[yellow]{pick}[/yellow]")
        if any("[yellow]" in cell for cell in row):
            disagreements.add_row(paper["title"], truth[cid], *row)
    console.print(disagreements)

    if finish_times:
        winner = min(finish_times, key=finish_times.get)
        console.print(f"🏁 First across the line: {winner}")


async def main():
    papers = json.loads(DATA.read_text())
    models = await ready_models()
    flock = build_flock(models)
    contenders = {"llm_sorter": f"🧠 LLM      {LLM_MODEL}"}
    contenders |= {agent_name(m): f"⚖️  Decision {m}" for m in models}
    started = await race(flock, contenders, papers)
    await report(flock, contenders, papers, started)


if __name__ == "__main__":
    asyncio.run(main())
