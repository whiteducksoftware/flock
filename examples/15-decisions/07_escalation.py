"""
Decision Models: Escalation Cascades

A decision agent asks a first decision model. Papers it is not sure about
(top probability below the threshold, or refused) go one tier up to the next
model in `escalate=`; only what is still unsure after the last tier routes to
UNSURE. Most papers are answered by the first tier, so the stronger model is
asked only about the hard ones.

This example sorts 100 arXiv abstracts into nine research fields:

- `sorter` decides a `ResearchField` with the first model in TIERS and
  escalates to the others, in order
- `inbox` takes the papers every tier was unsure about (`ResearchField.UNSURE`)

The report lists how many papers each tier answered and how often the answer
agrees with arXiv's primary category, plus the escalated papers with their
trail (every tier's best guess and probability).

🎯 Key Concepts:
- `.decides(ResearchField, model=..., escalate=[...], threshold=...)`
- `decision.tier`: which tier answered (0 is `model=`)
- `decision.attempts`: the earlier tiers' answers, oldest first
- With several questions (or a Checklist), only the unsure questions (or
  items) go up

🎛️  CONFIGURATION:
- TIERS below: the first entry is the decider's model, the rest escalate.
  Defaults to Microsoft-Decision-1 on Azure AI Foundry (AZURE_API_BASE,
  AZURE_API_KEY), then OpenAI Decisions (OPENAI_API_KEY). A local Clef model
  in front makes a cheap first tier (see 01_ticket_triage.py).
- USE_DASHBOARD = True serves the dashboard and publishes one paper every
  two seconds; escalated decisions show their trail.

Data: data/arxiv_abstracts.json, 100 recent abstracts with their primary
category (arXiv metadata, CC0).
"""

import asyncio
import json
from pathlib import Path

from pydantic import BaseModel

from flock import Choice, Decision, EngineComponent, EvalResult, Flock
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
TIERS = [
    # "local/clef-flash",  # a cheap local first tier
    "azure/decision-1",
    "openai/gpt-6-luna",
]
THRESHOLD = 0.9
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
    """A paper no tier was sure about, parked for a person."""

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
    .description("Sorts papers into fields; asks a stronger model when unsure")
    .consumes(Paper)
    .decides(ResearchField, model=TIERS[0], escalate=TIERS[1:], threshold=THRESHOLD)
)
flock.agent("inbox").consumes(ResearchField.UNSURE).with_engines(Park()).publishes(
    Parked
)


def guess(attempt: dict) -> str:
    if attempt["refused"] or not attempt["choice"]:
        return f"{attempt['model']}: refused"
    p = attempt["probabilities"].get(attempt["choice"], attempt["confidence"] or 0.0)
    return f"{attempt['model']}: {attempt['choice']} {p:.2f}"


async def main_cli(papers: list[dict]) -> None:
    print(
        f"\n⚖️  {len(papers)} papers, cascade {' → '.join(TIERS)}, threshold {THRESHOLD}\n"
    )
    for paper in papers:
        await flock.publish(
            Paper(
                arxiv_id=paper["arxiv_id"],
                title=paper["title"],
                abstract=paper["abstract"],
            )
        )
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

    print(f"{'tier':<6}{'model':<22}{'answered':>9}{'agree':>8}")
    for tier, name in enumerate(TIERS):
        answered = [d for d in decisions if d.tier == tier and d.choice != "UNSURE"]
        agree = sum(d.choice == truth[d.subject_ids[0]][1] for d in answered)
        print(f"{tier:<6}{name:<22}{len(answered):>9}{agree:>8}")
    unsure = [d for d in decisions if d.choice == "UNSURE"]
    print(f"{'':<6}{'UNSURE (inbox)':<22}{len(unsure):>9}")
    asked = sum(len(d.attempts) + 1 for d in decisions)
    print(
        f"\n{asked} requests for {len(decisions)} papers; the last tier was asked "
        f"{sum(d.tier == len(TIERS) - 1 for d in decisions)} times.\n"
    )

    print("Escalated papers:")
    for d in sorted(decisions, key=lambda d: -d.tier):
        if not d.attempts:
            continue
        title, field = truth[d.subject_ids[0]]
        trail = " → ".join(guess(a) for a in d.attempts)
        if d.refused:
            final = "refused"
        elif d.choice == "UNSURE":
            final = f"UNSURE ({d.best_guess}) {d.probabilities[d.best_guess]:.2f}"
        else:
            final = f"{d.choice} {d.probabilities[d.choice]:.2f}"
        print(f"  {title[:58]:<58}  arXiv {field}")
        print(f"      {trail} → {d.model}: {final}")


async def main_dashboard(papers: list[dict]) -> None:
    async def feed():
        await asyncio.sleep(5)
        for paper in papers:
            await flock.publish(
                Paper(
                    arxiv_id=paper["arxiv_id"],
                    title=paper["title"],
                    abstract=paper["abstract"],
                )
            )
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
