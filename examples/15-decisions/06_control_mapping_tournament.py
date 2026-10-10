"""
Decision Models: Three Ways to Pick One of 100 Controls

Which control does a sentence from a security document provide evidence for?
That is one option out of 100. Three contenders answer it for the same
sentences:

1. `flat`: one choice question with all 100 controls.
2. `tournament`: one node that asks in rounds. Five groups of 20 controls go
   out in one request, the 3 most probable controls of each group survive,
   then a final question about the 15 survivors.
3. A screening network of separate nodes. Four `screen_*` nodes each check 25
   controls with a yes/no checklist, in parallel. The `ranker` node waits for
   all four screens of a sentence, receives the sentence itself, and asks a
   final choice question about the controls that passed a screen.

```
                  ┌── screen_001_025 ──┐
EvidenceSentence ─┼── screen_026_050 ──┼──> ranker ──> Decision[Control]
                  ├── screen_051_075 ──┤
                  └── screen_076_100 ──┘
```

Decision models accept at most 255 options per question, so catalogs such as
the BSI IT-Grundschutz-Kompendium (well over 1,000 requirements) need a
tournament or a network. With 100 controls all three fit, which makes their
cost visible:

- The tournament needs one round trip more than `flat`.
- The network needs one request per screen (in parallel) plus the ranker. In
  exchange, every screen is its own node with its own model, threshold and
  scaling, and the graph shows every step.

The screens use yes/no checklists, not choices. A choice spreads its
probability over its own 25 controls, so an unrelated screen would still pass
some control. Yes/no answers are comparable across screens, which a threshold
needs.

Hosted decision models have rate limits: the default Microsoft-Decision-1
deployment allows 100 requests per minute, and this example sends eight per
sentence. Decisions that hit the limit fail with HTTP 429.

The evidence sentences and their controls come from
`data/compliance_documents.json` (see `05_compliance_checklist.py`). The
deciders only see the sentence.

🎯 Key Concepts:
- `Choice.from_options(...)` / `Checklist.from_items(...)` from a catalog
- `.decides(Control, tournament=Tournament(group_size=20, keep=3))`
- `.consumes(*(screen.ANY for screen in SCREENS))`: wait for every screen's
  decision about the same sentence; the sentence is delivered once, the
  decisions are in `ctx.decisions`
- `.decides(Control, options=passes)`: a final question about a subset of the
  catalog, chosen at runtime
- `Flock(decision_model=...)`: one decision model for every decider

🎛️  CONFIGURATION:
- USE_DASHBOARD = True serves the dashboard and publishes one sentence every
  two seconds.
- DECISION_MODEL below, or DEFAULT_DECISION_MODEL in your environment
  (default "azure/decision-1").
"""

import asyncio
import json
import os
import statistics
from pathlib import Path

from pydantic import BaseModel

from flock import Checklist, Choice, Decision, Flock, Tournament
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
DECISION_MODEL = os.getenv("DEFAULT_DECISION_MODEL", "azure/decision-1")
SENTENCES = 10  # 8 requests per sentence: flat 1, tournament 2, network 4 + 1
TOURNAMENT = Tournament(group_size=20, keep=3)
SCREEN_SIZE = 25
SCREEN_THRESHOLD = 0.5
# ============================================================================

DATA = Path(__file__).parent / "data"
CATALOG = json.loads((DATA / "compliance_controls.json").read_text())
DOCUMENTS = json.loads((DATA / "compliance_documents.json").read_text())
ORDER = {control["id"]: index for index, control in enumerate(CATALOG)}

Control = Choice.from_options(
    "Control",
    {control["id"]: control["text"] for control in CATALOG},
    question="Which control does this statement show to be implemented?",
)

SCREENS = [
    Checklist.from_items(
        f"Screen_{start + 1:03d}_{start + SCREEN_SIZE:03d}",
        {c["id"]: c["text"] for c in CATALOG[start : start + SCREEN_SIZE]},
        question="Does this statement show that this control is implemented?",
    )
    for start in range(0, len(CATALOG), SCREEN_SIZE)
]


@flock_type
class EvidenceSentence(BaseModel):
    """One sentence from a security document."""

    text: str


def passes(ctx) -> list[str]:
    """Controls that cleared a screen's threshold, in catalog order."""
    passed = [
        control
        for decision in ctx.decisions
        for control, result in decision.results.items()
        if result == "yes"
    ]
    return sorted(passed, key=ORDER.__getitem__)


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
for screen in SCREENS:
    (
        flock.agent(screen.__name__.lower())
        .description(f"Yes/no screen for {len(screen.__options__)} controls")
        .consumes(EvidenceSentence)
        .decides(screen, threshold=SCREEN_THRESHOLD)
        .max_concurrency(1)
    )
ranker = (
    flock.agent("ranker")
    .description("Ranks the controls that passed a screen")
    .consumes(*(screen.ANY for screen in SCREENS))
    .decides(Control, options=passes)
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
    results: dict[str, list] = {"flat": [], "tournament": [], "ranker": []}
    for artifact in store:
        if artifact.type == type_registry.name_for(model):
            results[artifact.produced_by].append(model(**artifact.payload))

    # A sentence's network time: its slowest screen, then the ranker
    screen_ms: dict[str, float] = {}
    for screen in SCREENS:
        screen_type = type_registry.name_for(Decision.of(screen))
        for artifact in store:
            if artifact.type == screen_type:
                sid = artifact.payload["subject_ids"][0]
                screen_ms[sid] = max(
                    screen_ms.get(sid, 0.0), artifact.payload["latency_ms"]
                )

    def subject(decision) -> str:
        return decision.subject_ids[0]

    rows = [
        ("flat", results["flat"], lambda d: d.latency_ms, lambda _: 1),
        (
            "tournament",
            results["tournament"],
            lambda d: d.latency_ms,
            lambda d: 1 + len(d.rounds),
        ),
        (
            "network",
            results["ranker"],
            lambda d: screen_ms.get(subject(d), 0.0) + d.latency_ms,
            lambda d: len(SCREENS) + (1 if len(d.candidates or []) > 1 else 0),
        ),
    ]
    print(f"{'contender':<12} {'right':>7} {'median':>9} {'requests':>9}")
    for name, decisions, latency, requests in rows:
        if not decisions:
            print(f"{name:<12} no decisions")
            continue
        right = sum(d.best_guess == truth[texts[subject(d)]] for d in decisions)
        median = statistics.median(latency(d) for d in decisions)
        median_requests = statistics.median(requests(d) for d in decisions)
        print(
            f"{name:<12} {right:>3}/{len(decisions):<3} {median:>6.0f} ms "
            f"{median_requests:>9.0f}"
        )

    tournament_found = sum(
        truth[texts[subject(d)]] in d.rounds[0]["survivors"]
        for d in results["tournament"]
        if d.rounds
    )
    network_found = sum(
        truth[texts[subject(d)]] in (d.candidates or []) for d in results["ranker"]
    )
    passed = [len(d.candidates or []) for d in results["ranker"]]
    print(
        f"\nRight control among the tournament's finalists: "
        f"{tournament_found}/{len(results['tournament'])}"
    )
    if passed:
        print(
            f"Right control among the network's passes: "
            f"{network_found}/{len(results['ranker'])} "
            f"(median {statistics.median(passed):.0f} passes per sentence)"
        )


async def main_dashboard():
    async def feed():
        await asyncio.sleep(5)  # let the dashboard start
        for item in sample():
            await flock.publish(EvidenceSentence(text=item["text"]))
            await asyncio.sleep(2)

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
