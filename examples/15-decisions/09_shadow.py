"""
Decision Models: Shadow Mode

Before switching a decider to another decision model, let the candidate run
in the shadow: it answers every question too, its answer is recorded next to
the live decision, and it never routes anything. The live workflow is
unchanged while the candidate is evaluated on real traffic.

This example sorts 100 arXiv abstracts into nine research fields:

- `sorter` decides with LIVE and records SHADOW's answer in every decision
- `inbox` takes the papers the live model was unsure about

The report compares the two models on the same papers: how often the shadow
would have routed the same way, where it would have routed differently, and
how often each agrees with arXiv's primary category.

🎯 Key Concepts:
- `.decides(ResearchField, model=LIVE, shadow=SHADOW, threshold=...)`
- `decision.shadow`: the shadow's model, choice (under the same threshold),
  best guess, probabilities and latency; or its error, which never fails the
  live decision
- Shadow answers are stored, not routed: `ResearchField.UNSURE` and the other
  handles see only the live choice

🎛️  CONFIGURATION:
- LIVE: Microsoft-Decision-1 on Azure AI Foundry (AZURE_API_BASE,
  AZURE_API_KEY); SHADOW: OpenAI Decisions (OPENAI_API_KEY)
- USE_DASHBOARD = True serves the dashboard and publishes one paper every
  two seconds; the decider shows how often the shadow agrees, every decision
  what the shadow chose.

Data: data/arxiv_abstracts.json, 100 recent abstracts with their primary
category (arXiv metadata, CC0).
"""

import asyncio
import json
import statistics
from pathlib import Path

from pydantic import BaseModel

from flock import Choice, Decision, EngineComponent, EvalResult, Flock
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
LIVE = "azure/decision-1"
SHADOW = "openai/gpt-6-luna"
THRESHOLD = 0.8
DATA = Path(__file__).parent / "data" / "arxiv_abstracts.json"
# ============================================================================


@flock_type
class Paper(BaseModel):
    """An arXiv paper to sort into a research field."""

    arxiv_id: str
    title: str
    abstract: str


@flock_type
class Parked(BaseModel):
    """A paper the live model was not sure about, parked for a person."""

    title: str


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


class Park(EngineComponent):
    """Parks a paper for a person; stands in for a real review queue."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        paper = Paper(**inputs.artifacts[0].payload)
        return EvalResult.from_object(Parked(title=paper.title), agent=agent)


flock = Flock(decision_rate_limit="100/min", no_output=True)
(
    flock.agent("sorter")
    .description("Sorts papers into fields; a candidate model runs in the shadow")
    .consumes(Paper)
    .decides(ResearchField, model=LIVE, shadow=SHADOW, threshold=THRESHOLD)
)
flock.agent("inbox").consumes(ResearchField.UNSURE).with_engines(Park()).publishes(
    Parked
)


def paper_of(paper: dict) -> Paper:
    return Paper(
        arxiv_id=paper["arxiv_id"], title=paper["title"], abstract=paper["abstract"]
    )


async def main_cli(papers: list[dict]) -> None:
    print(f"\n⚖️  {len(papers)} papers, live {LIVE}, shadow {SHADOW}, ")
    print(f"   threshold {THRESHOLD}\n")
    for paper in papers:
        await flock.publish(paper_of(paper))
    await flock.run_until_idle()

    store = await flock.store.list()
    truth = {}
    for artifact in store:
        if artifact.type == type_registry.name_for(Paper):
            source = next(
                p for p in papers if p["arxiv_id"] == artifact.payload["arxiv_id"]
            )
            truth[str(artifact.id)] = (source["title"], source["field"])
    model = Decision.of(ResearchField)
    decisions = [
        model(**a.payload) for a in store if a.type == type_registry.name_for(model)
    ]
    compared = [d for d in decisions if d.shadow and "error" not in d.shadow]
    failed = len(decisions) - len(compared)

    def row(name: str, picks: list[tuple[str, str]], latencies: list[float]) -> None:
        firm = [(pick, sid) for pick, sid in picks if pick != "UNSURE"]
        agree = sum(pick == truth[sid][1] for pick, sid in firm)
        median = statistics.median(latencies) if latencies else 0.0
        print(f"{name:<26}{len(firm):>6}{agree:>8}{median:>10.0f} ms")

    print(f"{'':<26}{'firm':>6}{'agree':>8}{'median':>13}")
    row(
        f"live   {LIVE}",
        [(d.choice, d.subject_ids[0]) for d in compared],
        [d.latency_ms or 0.0 for d in compared],
    )
    row(
        f"shadow {SHADOW}",
        [(d.shadow["choice"], d.subject_ids[0]) for d in compared],
        [d.shadow["latency_ms"] for d in compared],
    )
    same = sum(d.shadow["choice"] == d.choice for d in compared)
    print(
        f"\nThe shadow would have routed {same} of {len(compared)} papers the same way."
    )
    if failed:
        print(f"The shadow failed on {failed} papers (recorded as errors).")

    print("\nPapers the shadow would have routed differently:")
    for d in compared:
        if d.shadow["choice"] == d.choice:
            continue
        title, field = truth[d.subject_ids[0]]
        print(f"  {title[:58]:<58}  arXiv {field}")
        print(f"      live: {d.choice} · shadow: {d.shadow['choice']}")


async def main_dashboard(papers: list[dict]) -> None:
    async def feed():
        await asyncio.sleep(5)
        for paper in papers:
            await flock.publish(paper_of(paper))
            await asyncio.sleep(2)

    feeder = asyncio.create_task(feed())
    try:
        await flock.serve(dashboard=True)
    finally:
        feeder.cancel()


async def main():
    papers = json.loads(DATA.read_text())
    if USE_DASHBOARD:
        await main_dashboard(papers)
    else:
        await main_cli(papers)


if __name__ == "__main__":
    asyncio.run(main())
