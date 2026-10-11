"""
Decision Models: Ensembles and Voting

Several decision models answer the same question and a vote decides. A paper
the models disagree about goes to UNSURE instead of being sorted by whichever
model happened to be asked.

This example sorts 100 arXiv abstracts into nine research fields:

- `sorter` asks every model in MODELS about every paper and votes
- `inbox` takes the papers the vote did not settle (`ResearchField.UNSURE`)

The decision records every model's answer in `votes`, so the report can show
each model on its own next to the ensemble: how many papers each one sorted
firmly and how many of those agree with arXiv's primary category.

🎯 Key Concepts:
- `.decides(ResearchField, models=[...], vote="majority", threshold=...)`
- `vote="majority"`: more than half of the models give the same firm answer
  (the threshold applies per model); `"unanimous"`: all of them; `"mean"`:
  the threshold applies to the mean probabilities
- `decision.votes`: every model's answer, in the order of `models=`
- `decision.probabilities`: the mean over the models that answered

🎛️  CONFIGURATION:
- MODELS below: Microsoft-Decision-1 on Azure AI Foundry (AZURE_API_BASE,
  AZURE_API_KEY), TypeSafe Jev (JEV_API_KEY) and OpenAI Decisions
  (OPENAI_API_KEY)
- VOTE: "majority", "unanimous" or "mean" (or the VOTE environment variable)
- USE_DASHBOARD = True serves the dashboard and publishes one paper every
  two seconds; every decision shows its votes.

Data: data/arxiv_abstracts.json, 100 recent abstracts with their primary
category (arXiv metadata, CC0).
"""

import asyncio
import json
import os
from pathlib import Path

from pydantic import BaseModel

from flock import Choice, Decision, EngineComponent, EvalResult, Flock
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
MODELS = ["azure/decision-1", "jev/jev-latest", "openai/gpt-6-luna"]
VOTE = os.getenv("VOTE", "majority")
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
    """A paper the vote did not settle, parked for a person."""

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
    .description("Sorts papers into fields by a vote of several decision models")
    .consumes(Paper)
    .decides(ResearchField, models=MODELS, vote=VOTE, threshold=THRESHOLD)
)
flock.agent("inbox").consumes(ResearchField.UNSURE).with_engines(Park()).publishes(
    Parked
)


def firm(vote: dict) -> str | None:
    """A model's firm answer, None when it refused or stayed below the threshold."""
    if vote["refused"] or not vote["choice"]:
        return None
    p = vote["probabilities"].get(vote["choice"], vote["confidence"] or 0.0)
    return vote["choice"] if p >= THRESHOLD else None


def paper_of(paper: dict) -> Paper:
    return Paper(
        arxiv_id=paper["arxiv_id"], title=paper["title"], abstract=paper["abstract"]
    )


async def main_cli(papers: list[dict]) -> None:
    print(f"\n⚖️  {len(papers)} papers, vote={VOTE} of {', '.join(MODELS)}, ")
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

    print(f"{'':<22}{'firm':>6}{'agree':>8}")
    for index, name in enumerate(MODELS):
        picks = [(firm(d.votes[index]), d) for d in decisions]
        sorted_ = [(pick, d) for pick, d in picks if pick is not None]
        agree = sum(pick == truth[d.subject_ids[0]][1] for pick, d in sorted_)
        print(f"{name:<22}{len(sorted_):>6}{agree:>8}")
    settled = [d for d in decisions if d.choice != "UNSURE"]
    agree = sum(d.choice == truth[d.subject_ids[0]][1] for d in settled)
    print(f"{'vote: ' + VOTE:<22}{len(settled):>6}{agree:>8}")
    print(f"{'UNSURE (inbox)':<22}{len(decisions) - len(settled):>6}\n")

    print("Papers the models disagree about:")
    for d in decisions:
        picks = [firm(vote) for vote in d.votes]
        if len(set(picks)) == 1:
            continue
        title, field = truth[d.subject_ids[0]]
        answers = " · ".join(
            f"{vote['model']}: {pick or 'unsure'}"
            for vote, pick in zip(d.votes, picks, strict=True)
        )
        print(f"  {title[:58]:<58}  arXiv {field}")
        print(f"      {answers} → {d.choice}")


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
