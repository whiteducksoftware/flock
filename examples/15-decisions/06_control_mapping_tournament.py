"""
Decision Models: Mapping Evidence to One of 100 Controls with a Tournament

Which control does a sentence from a security document provide evidence for?
That is one option out of 100. Two deciders answer it for the same sentences:

- `flat` asks one choice question with all 100 controls
- `tournament` asks in rounds: 5 groups of 20 controls in one request, the 3
  most probable controls of each group survive, then a final question about
  the 15 survivors

Decision models accept at most 255 options per question, so catalogs such as
the BSI IT-Grundschutz-Kompendium (well over 1,000 requirements) can only be
asked as a tournament. With 100 controls both fit, which makes the cost of the
tournament visible: one extra round trip, and the risk that the right control
drops out of an early round.

Hosted decision models have rate limits: the default Microsoft-Decision-1
deployment allows 100 requests per minute, and this example sends three per
sentence (one flat, two for the tournament). Decisions that hit the limit fail
with HTTP 429.

The evidence sentences and their controls come from
`data/compliance_documents.json` (see `05_compliance_checklist.py`). The
deciders only see the sentence.

🎯 Key Concepts:
- `Choice.from_options(...)`: a Choice built from a catalog
- `.decides(Control, tournament=Tournament(group_size=20, keep=3))`
- `Flock(decision_model=...)`: one decision model for every decider
- The decision's `rounds` records candidates and survivors per round

🎛️  CONFIGURATION:
- USE_DASHBOARD = True serves the dashboard and publishes one sentence per second.
- DECISION_MODEL below, or DEFAULT_DECISION_MODEL in your environment
  (default "azure/decision-1").
"""

import asyncio
import json
import os
import statistics
from pathlib import Path

from pydantic import BaseModel

from flock import Choice, Decision, Flock, Tournament
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
DECISION_MODEL = os.getenv("DEFAULT_DECISION_MODEL", "azure/decision-1")
SENTENCES = 25  # flat: 1 request per sentence, tournament: 2
TOURNAMENT = Tournament(group_size=20, keep=3)
# ============================================================================

DATA = Path(__file__).parent / "data"
CATALOG = json.loads((DATA / "compliance_controls.json").read_text())
DOCUMENTS = json.loads((DATA / "compliance_documents.json").read_text())

Control = Choice.from_options(
    "Control",
    {control["id"]: control["text"] for control in CATALOG},
    question="Which control does this statement show to be implemented?",
)


@flock_type
class EvidenceSentence(BaseModel):
    """One sentence from a security document."""

    text: str


def sample() -> list[dict]:
    """Every n-th evidence sentence of the generated documents, with its control."""
    evidence = [item for document in DOCUMENTS for item in document["evidence"]]
    step = max(1, len(evidence) // SENTENCES)
    return evidence[::step][:SENTENCES]


flock = Flock(decision_model=DECISION_MODEL, no_output=True)

flat = (
    flock.agent("flat")
    .description("One choice question with all 100 controls")
    .consumes(EvidenceSentence)
    .decides(Control)
    .max_concurrency(1)  # one sentence at a time keeps hosted rate limits happy
)
tournament = (
    flock.agent("tournament")
    .description("Groups of 20 controls, 3 survivors each, then a final question")
    .consumes(EvidenceSentence)
    .decides(Control, tournament=TOURNAMENT)
    .max_concurrency(1)
)


async def main_cli():
    evidence = sample()
    print(
        f"\n🏆 Mapping {len(evidence)} evidence sentences to one of {len(CATALOG)} "
        f"controls with {DECISION_MODEL}\n"
    )
    for item in evidence:
        await flock.publish(EvidenceSentence(text=item["text"]))
    await flock.run_until_idle()

    store = await flock.store.list()
    texts = {
        str(a.id): a.payload["text"]
        for a in store
        if a.type == type_registry.name_for(EvidenceSentence)
    }
    truth = {item["text"]: item["control"] for item in evidence}
    model = Decision.of(Control)
    results: dict[str, list] = {"flat": [], "tournament": []}
    for artifact in store:
        if artifact.type == type_registry.name_for(model):
            decision = model(**artifact.payload)
            results[artifact.produced_by].append(decision)

    print(f"{'decider':<12} {'right':>7} {'median':>9} {'requests':>9}")
    for name, decisions in results.items():
        right = sum(d.best_guess == truth[texts[d.subject_ids[0]]] for d in decisions)
        median = statistics.median(d.latency_ms for d in decisions)
        requests = 1 + (len(decisions[0].rounds) if decisions else 0)
        print(
            f"{name:<12} {right:>3}/{len(decisions):<3} {median:>6.0f} ms {requests:>9}"
        )

    survived = sum(
        truth[texts[d.subject_ids[0]]] in d.rounds[0]["survivors"]
        for d in results["tournament"]
        if d.rounds
    )
    print(
        f"\nRight control among the {len(results['tournament'][0].rounds[0]['survivors'])} "
        f"finalists: {survived}/{len(results['tournament'])}"
    )
    flat_by_text = {texts[d.subject_ids[0]]: d.best_guess for d in results["flat"]}
    disagreements = [
        (texts[d.subject_ids[0]], flat_by_text[texts[d.subject_ids[0]]], d.best_guess)
        for d in results["tournament"]
        if d.best_guess != flat_by_text[texts[d.subject_ids[0]]]
    ]
    if disagreements:
        print("\nWhere the two disagree:")
        for text, flat_pick, tournament_pick in disagreements[:8]:
            print(
                f"  {text[:60]:<60}  flat {flat_pick:<8} tournament {tournament_pick:<8} "
                f"(truth {truth[text]})"
            )


async def main_dashboard():
    async def feed():
        await asyncio.sleep(5)  # let the dashboard start
        for item in sample():
            await flock.publish(EvidenceSentence(text=item["text"]))
            await asyncio.sleep(1)

    feeder = asyncio.create_task(feed())
    try:
        await flock.serve(dashboard=True)
    finally:
        feeder.cancel()


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
