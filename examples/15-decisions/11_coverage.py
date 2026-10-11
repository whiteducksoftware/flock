"""
Decision Models: Coverage Across Documents

A single document rarely shows all 100 controls of a catalog, so a checklist
per document almost always fails. The useful question is per organisation:
is each control shown by *any* of its documents?

- `audit` checks every document against the 100 controls (one checklist
  decision per document, as in 05_compliance_checklist.py)
- `coverage` consumes those decisions and `.aggregates()` them by
  organisation: a control is "yes" once any document of the organisation shows
  it. It publishes the organisation's `Coverage` after every document.

The report compares each organisation's coverage with the ground truth (a
control counts as shown if any of its documents shows it).

🎯 Key Concepts:
- `.consumes(Controls.ANY).aggregates(by="organisation", combine="any")`
- `Coverage.of(Controls)`: `group`, `results` per control, `evidence` (the
  documents that showed each control), `subject_ids`, `decision_ids`
- `combine="all"` instead asks whether *every* document shows a control
- Coverage keeps the documents' visibility (or `visibility=`)

🎛️  CONFIGURATION:
- DECISION_MODEL: Microsoft-Decision-1 on Azure AI Foundry (AZURE_API_BASE,
  AZURE_API_KEY) or DEFAULT_DECISION_MODEL
- USE_DASHBOARD = True serves the dashboard and publishes one document every
  two seconds; the coverage agent counts passed and failed organisations.

Data: data/compliance_*.json (made by data/make_compliance_data.py), 100
controls and 24 fictional documents of 12 organisations with ground truth.
"""

import asyncio
import json
import os
from pathlib import Path

from pydantic import BaseModel

from flock import Checklist, Flock
from flock.decisions.coverage import Coverage
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


flock = Flock(
    decision_model=DECISION_MODEL, decision_rate_limit="100/min", no_output=True
)
flock.agent("audit").consumes(ComplianceDocument).decides(Controls, threshold=THRESHOLD)
flock.agent("coverage").consumes(Controls.ANY).aggregates(
    by="organisation", combine="any"
)


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


def truth() -> dict[str, dict[str, str]]:
    """Per organisation: yes for a control any of its documents shows."""
    shown: dict[str, dict[str, str]] = {}
    for document in DOCUMENTS:
        org = shown.setdefault(
            document["organisation"], {c["id"]: "no" for c in CATALOG}
        )
        for control, label in document["labels"].items():
            if label == "yes":
                org[control] = "yes"
    return shown


async def main_cli() -> None:
    print(
        f"\n☑️  {len(DOCUMENTS)} documents of {len(truth())} organisations, "
        f"{len(CATALOG)} controls, {DECISION_MODEL} (threshold {THRESHOLD})\n"
    )
    for document in documents():
        await flock.publish(document)
    await flock.run_until_idle()

    model = Coverage.of(Controls)
    latest: dict[str, dict] = {}  # per organisation, the highest revision
    for artifact in await flock.store.list():
        if artifact.type == type_registry.name_for(model):
            group = artifact.payload["group"]
            if artifact.payload["revision"] > latest.get(group, {}).get("revision", 0):
                latest[group] = artifact.payload

    expected = truth()
    totals = {"tp": 0, "fp": 0, "fn": 0, "unsure": 0}
    print(
        f"{'organisation':<26} {'docs':>4} {'yes':>4} {'no':>4} {'?':>3}  truth yes  agrees"
    )
    for org in sorted(latest):
        coverage = latest[org]
        results = coverage["results"]
        counts = [
            sum(r == v for r in results.values()) for v in ("yes", "no", "UNSURE")
        ]
        agree = 0
        for control, result in results.items():
            if result == "UNSURE":
                totals["unsure"] += 1
                totals["fn"] += expected[org][control] == "yes"  # missed
                continue
            agree += result == expected[org][control]
            if result == "yes":
                totals["tp" if expected[org][control] == "yes" else "fp"] += 1
            elif expected[org][control] == "yes":
                totals["fn"] += 1
        truth_yes = sum(v == "yes" for v in expected[org].values())
        decided = len(results) - counts[2]
        print(
            f"{org:<26} {len(coverage['subject_ids']):>4} {counts[0]:>4} {counts[1]:>4} "
            f"{counts[2]:>3}  {truth_yes:>9}  {agree:>3}/{decided}"
        )
    tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
    print(
        f"\nCoverage 'shown': precision {tp / max(1, tp + fp):.2f}, recall "
        f"{tp / max(1, tp + fn):.2f} (unsure counts as missed); "
        f"{totals['unsure']} controls still unsure"
    )


async def main_dashboard() -> None:
    async def feed():
        await asyncio.sleep(5)
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
