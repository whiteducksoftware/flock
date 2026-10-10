"""
Decision Models: Checking Documents Against 100 Controls

A `Checklist` asks the same yes/no question for every item of a catalog, here
"does the document show that this control is implemented?" for 100 security
controls, and publishes one decision per document with an answer per control.

The data (`data/compliance_*.json`, made by `data/make_compliance_data.py`):

- 100 controls written for this example, loosely modelled on the topics of
  ISO/IEC 27001, NIS2 and BSI IT-Grundschutz (not quotes from them)
- 24 fictional documents (policies, procedures, audit reports) with ground
  truth: which controls each one shows as implemented

Downstream agents subscribe to outcomes and single controls:

- `remediation` gets every document with at least one control answered "no"
- `review` gets documents with controls the model was not sure about: a
  `where=` predicate on `Controls.ANY`, because the outcome is `failed` as
  soon as one control is a clear "no"
- `restore_owner` gets documents where restore tests are not shown (`bcm_06`)

The handlers only log, so the decision model is the only model called: one
request per document with 100 questions.

🎯 Key Concepts:
- `Checklist.from_items(...)`: a question class built from a catalog
- `.decides(Controls, threshold=0.8)`: one decision per document, `results`
  holds yes / no / UNSURE per control
- `.consumes(Controls.failed)`, `.consumes(Controls.bcm_06.no)` and
  `.consumes(Controls.ANY, where=...)` on the decision's `results`

🎛️  CONFIGURATION:
- USE_DASHBOARD = True serves the dashboard and publishes one document every
  two seconds.
- DECISION_MODEL below, or DEFAULT_DECISION_MODEL in your environment
  (default "azure/decision-1"; see 01_ticket_triage.py for the others).
"""

import asyncio
import json
import os
from pathlib import Path

from pydantic import BaseModel

from flock import Checklist, Decision, EngineComponent, EvalResult, Flock
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
DECISION_MODEL = os.getenv("DEFAULT_DECISION_MODEL", "azure/decision-1")
THRESHOLD = 0.8
# ============================================================================

DATA = Path(__file__).parent / "data"
CATALOG = json.loads((DATA / "compliance_controls.json").read_text())
DOCUMENTS = json.loads((DATA / "compliance_documents.json").read_text())

Controls = Checklist.from_items(
    "Controls",
    {control["id"]: control["text"] for control in CATALOG},
    question="Does the document show that this control is implemented?",
)


@flock_type
class ComplianceDocument(BaseModel):
    """A policy, procedure or audit report to check."""

    doc_id: str
    title: str
    organisation: str
    text: str


@flock_type
class Finding(BaseModel):
    """What a handler noted about a document."""

    handler: str
    doc_id: str
    controls: int = 0  # how many controls had the result the handler looks for


class LogHandler(EngineComponent):
    """Logs the controls with the given result; stands in for a real handler."""

    result: str = "no"

    async def evaluate(self, agent, ctx, inputs, output_group):
        document = ComplianceDocument(**inputs.artifacts[0].payload)
        controls = [
            control
            for control, result in ctx.decision.results.items()
            if result == self.result
        ]
        print(
            f"  {agent.name:<13} ← {document.doc_id} {document.title[:34]:<34} "
            f"{len(controls):>3} controls {self.result}"
        )
        return EvalResult.from_object(
            Finding(handler=agent.name, doc_id=document.doc_id, controls=len(controls)),
            agent=agent,
        )


flock = Flock(no_output=True)  # the handlers print one line each

audit = (
    flock.agent("audit")
    .description("Checks every document against the control catalog")
    .consumes(ComplianceDocument)
    .decides(Controls, model=DECISION_MODEL, threshold=THRESHOLD)
)


def has_unsure_controls(decision) -> bool:
    return "UNSURE" in decision.results.values()


for name, handle, where, result in (
    ("remediation", Controls.failed, None, "no"),
    ("review", Controls.ANY, has_unsure_controls, "UNSURE"),
    ("restore_owner", Controls.bcm_06.no, None, "no"),
):
    flock.agent(name).consumes(handle, where=where).with_engines(
        LogHandler(result=result)
    ).publishes(Finding)


def documents() -> list[ComplianceDocument]:
    return [
        ComplianceDocument(
            doc_id=d["id"],
            title=d["title"],
            organisation=d["organisation"],
            text=d["text"],
        )
        for d in DOCUMENTS
    ]


async def main_cli():
    print(
        f"\n☑️  {len(DOCUMENTS)} documents, {len(CATALOG)} controls each, "
        f"with {DECISION_MODEL} (threshold {THRESHOLD})\n"
    )
    for document in documents():
        await flock.publish(document)
    await flock.run_until_idle()

    store = await flock.store.list()
    doc_ids = {
        str(a.id): a.payload["doc_id"]
        for a in store
        if a.type == type_registry.name_for(ComplianceDocument)
    }
    truth = {d["id"]: d["labels"] for d in DOCUMENTS}
    titles = {d["id"]: d["title"] for d in DOCUMENTS}
    model = Decision.of(Controls)
    decisions = sorted(
        (model(**a.payload) for a in store if a.type == type_registry.name_for(model)),
        key=lambda d: doc_ids[d.subject_ids[0]],
    )

    totals = {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "unsure": 0}
    print("\n" + "=" * 92)
    print(
        f"{'document':<46} {'outcome':<8} {'yes':>4} {'no':>4} {'?':>3}  agrees  latency"
    )
    for decision in decisions:
        doc_id = doc_ids[decision.subject_ids[0]]
        results = decision.results
        agree = 0
        for control, result in results.items():
            expected = truth[doc_id][control]
            if result == "UNSURE":
                totals["unsure"] += 1
                continue
            agree += result == expected
            key = ("t" if result == expected else "f") + (
                "p" if result == "yes" else "n"
            )
            totals[key] += 1
        counts = [
            sum(r == v for r in results.values()) for v in ("yes", "no", "UNSURE")
        ]
        decided = len(results) - counts[2]
        print(
            f"{doc_id} {titles[doc_id][:39]:<39} {decision.choice:<8} "
            f"{counts[0]:>4} {counts[1]:>4} {counts[2]:>3}  {agree:>3}/{decided:<3} "
            f"{decision.latency_ms:>5.0f} ms"
        )
    tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
    print(
        f"\nAll answers: precision {tp / max(1, tp + fp):.2f}, recall {tp / max(1, tp + fn):.2f} "
        f"for 'implemented'; {totals['unsure']} answers below the threshold"
    )


async def main_dashboard():
    async def feed():
        await asyncio.sleep(5)  # let the dashboard start
        for document in documents():
            await flock.publish(document)
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
