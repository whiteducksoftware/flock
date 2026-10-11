"""
Decision Models: Calibrating Thresholds

One global threshold rarely fits every question: some controls are easy to
recognise, others are often answered wrongly with high confidence. With
labels (the right answers) for some decided artifacts, `calibrate()` suggests
per question, and per checklist item, the lowest threshold whose firm answers
reach a target precision.

This example checks the 24 compliance documents against the 100 controls:

1. `audit` decides every document with one global threshold (0.8)
2. thresholds per control are calibrated on half of the documents, with their
   ground truth as labels, for a target precision of 0.95
3. `calibrated` decides the other half again with those `item_thresholds`

The report compares the held-out half with the global threshold and with the
calibrated ones: precision and recall of "shown", and how many answers stayed
unsure. Calibrating and measuring on the same documents would only show how
well the thresholds fit the data they came from.

🎯 Key Concepts:
- `calibrate(decisions, labels, target_precision=0.95, min_support=3)`
- `.decides(Controls, threshold=0.8, item_thresholds={...})`
- Labels can also come from human reviews: `flock-flow decisions calibrate DB`
  reads the reviews in a SQLite store

🎛️  CONFIGURATION:
- DECISION_MODEL: Microsoft-Decision-1 on Azure AI Foundry (AZURE_API_BASE,
  AZURE_API_KEY) or DEFAULT_DECISION_MODEL
- TARGET_PRECISION, MIN_SUPPORT

Data: data/compliance_*.json (made by data/make_compliance_data.py).
"""

import asyncio
import json
import os
from pathlib import Path

from pydantic import BaseModel

from flock import Checklist, Decision, Flock
from flock.decisions.calibration import calibrate
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
DECISION_MODEL = os.getenv("DEFAULT_DECISION_MODEL", "azure/decision-1")
THRESHOLD = 0.8
TARGET_PRECISION = 0.95
MIN_SUPPORT = 3
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
    text: str


def document(d: dict) -> ComplianceDocument:
    return ComplianceDocument(doc_id=d["id"], title=d["title"], text=d["text"])


async def decide(documents: list[dict], **decides) -> dict[str, dict]:
    """doc_id -> checklist decision payload, from a fresh flock."""
    flock = Flock(
        decision_model=DECISION_MODEL, decision_rate_limit="100/min", no_output=True
    )
    flock.agent("audit").consumes(ComplianceDocument).decides(
        Controls, threshold=THRESHOLD, **decides
    )
    for d in documents:
        await flock.publish(document(d))
    await flock.run_until_idle()
    store = await flock.store.list()
    doc_ids = {
        str(a.id): a.payload["doc_id"]
        for a in store
        if a.type == type_registry.name_for(ComplianceDocument)
    }
    name = type_registry.name_for(Decision.of(Controls))
    return {
        doc_ids[a.payload["subject_ids"][0]]: a.payload for a in store if a.type == name
    }


def score(decisions: dict[str, dict]) -> tuple[float, float, int]:
    """Precision and recall of "shown" against the ground truth (an unsure
    answer about a shown control is a miss), and the unsure answers."""
    truth = {d["id"]: d["labels"] for d in DOCUMENTS}
    tp = fp = fn = unsure = 0
    for doc_id, decision in decisions.items():
        for control, result in decision["results"].items():
            expected = truth[doc_id][control]
            if result == "UNSURE":
                unsure += 1
                fn += expected == "yes"  # an unsure answer misses a shown control
            elif result == "yes":
                tp += expected == "yes"
                fp += expected != "yes"
            elif expected == "yes":
                fn += 1
    return tp / max(1, tp + fp), tp / max(1, tp + fn), unsure


async def main() -> None:
    calibration_half, held_out = DOCUMENTS[::2], DOCUMENTS[1::2]
    print(
        f"\n☑️  {len(DOCUMENTS)} documents, {len(CATALOG)} controls, "
        f"{DECISION_MODEL}; calibrating on {len(calibration_half)}, "
        f"measuring on {len(held_out)}\n"
    )
    decisions = await decide(DOCUMENTS)

    # Calibrate per control on half of the documents, with their ground truth
    by_doc = {d["id"]: d for d in DOCUMENTS}
    labels = {
        decision["subject_ids"][0]: {"Controls": by_doc[doc_id]["labels"]}
        for doc_id, decision in decisions.items()
        if doc_id in {d["id"] for d in calibration_half}
    }
    suggestions = calibrate(
        decisions.values(), labels, TARGET_PRECISION, min_support=MIN_SUPPORT
    )
    item_thresholds = {
        s.item: s.threshold for s in suggestions if s.item and s.threshold is not None
    }
    lower = sum(t < THRESHOLD for t in item_thresholds.values())
    print(
        f"Calibrated {len(item_thresholds)} of {len(CATALOG)} controls for "
        f"precision {TARGET_PRECISION}: {lower} below {THRESHOLD}, "
        f"{len(item_thresholds) - lower} at or above it\n"
    )

    # The held-out half: the global threshold against the calibrated ones
    held_out_ids = {d["id"] for d in held_out}
    global_run = {k: v for k, v in decisions.items() if k in held_out_ids}
    calibrated_run = await decide(held_out, item_thresholds=item_thresholds)
    print(f"{'held-out documents':<28} {'precision':>9} {'recall':>7} {'unsure':>7}")
    for name, run in (
        ("global threshold 0.8", global_run),
        ("calibrated", calibrated_run),
    ):
        precision, recall, unsure = score(run)
        print(f"{name:<28} {precision:>9.2f} {recall:>7.2f} {unsure:>7}")


if __name__ == "__main__":
    asyncio.run(main())
