"""
Decision Models: Long Documents in Sections

A long document can exceed what a decision model reads well in one request,
and a checklist answer for the whole document does not say where the
evidence is. `sections=` splits a text field into sections at paragraph
boundaries, asks every question about each section and combines the answers:
a checklist item is "yes" if any section shows it, a choice takes the most
confident section. The decision records which section answered.

This example builds one security manual per organisation from the compliance
documents (each manual holds all documents of the organisation) and checks
every manual against the 100 controls twice:

- `whole` decides on the manual in one piece
- `sectioned` decides on sections of at most MAX_CHARS characters

The report compares both with the ground truth and shows, for one manual,
which section showed each control.

🎯 Key Concepts:
- `.decides(Controls, sections=Sections(field="text", max_chars=...))`
- `decision.sections`: the field, the sections' spans and `answered_by`
  (per checklist item, or per question, the section whose answer was kept)
- Requests grow with the sections: one per section (per 100 questions)

🎛️  CONFIGURATION:
- DECISION_MODEL: Microsoft-Decision-1 on Azure AI Foundry (AZURE_API_BASE,
  AZURE_API_KEY) or DEFAULT_DECISION_MODEL
- MAX_CHARS: the longest section
- USE_DASHBOARD = True serves the dashboard; decisions name their sections.

Data: data/compliance_*.json (made by data/make_compliance_data.py).
"""

import asyncio
import json
import os
from pathlib import Path

from pydantic import BaseModel

from flock import Checklist, Decision, Flock, Sections
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
DECISION_MODEL = os.getenv("DEFAULT_DECISION_MODEL", "azure/decision-1")
THRESHOLD = 0.8
MAX_CHARS = 800
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
class SecurityManual(BaseModel):
    """All security documents of one organisation, as one long text."""

    organisation: str
    text: str


flock = Flock(
    decision_model=DECISION_MODEL, decision_rate_limit="100/min", no_output=True
)
flock.agent("whole").consumes(SecurityManual).decides(Controls, threshold=THRESHOLD)
flock.agent("sectioned").consumes(SecurityManual).decides(
    Controls,
    threshold=THRESHOLD,
    sections=Sections(field="text", max_chars=MAX_CHARS),
)


def manuals() -> list[SecurityManual]:
    texts: dict[str, list[str]] = {}
    for document in DOCUMENTS:
        texts.setdefault(document["organisation"], []).append(document["text"])
    return [
        SecurityManual(organisation=org, text="\n\n".join(parts))
        for org, parts in texts.items()
    ]


def truth() -> dict[str, dict[str, str]]:
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
    books = manuals()
    lengths = [len(book.text) for book in books]
    print(
        f"\n📚 {len(books)} manuals of {min(lengths)}-{max(lengths)} characters, "
        f"{len(CATALOG)} controls, {DECISION_MODEL}, sections of at most "
        f"{MAX_CHARS} characters\n"
    )
    for book in books:
        await flock.publish(book)
    await flock.run_until_idle()

    store = await flock.store.list()
    orgs = {
        str(a.id): a.payload["organisation"]
        for a in store
        if a.type == type_registry.name_for(SecurityManual)
    }
    model = Decision.of(Controls)
    decisions = [
        (a.produced_by, model(**a.payload))
        for a in store
        if a.type == type_registry.name_for(model)
    ]
    expected = truth()
    print(
        f"{'decider':<10} {'requests':>8} {'yes':>5} {'no':>5} {'?':>4}  precision  recall"
    )
    for name in ("whole", "sectioned"):
        tp = fp = fn = unsure = yes = no = requests = 0
        for producer, decision in decisions:
            if producer != name:
                continue
            requests += len(decision.sections["spans"]) if decision.sections else 1
            truth_org = expected[orgs[decision.subject_ids[0]]]
            for control, result in decision.results.items():
                if result == "UNSURE":
                    unsure += 1
                    continue
                yes += result == "yes"
                no += result == "no"
                if result == "yes":
                    tp += truth_org[control] == "yes"
                    fp += truth_org[control] != "yes"
                elif truth_org[control] == "yes":
                    fn += 1
        print(
            f"{name:<10} {requests:>8} {yes:>5} {no:>5} {unsure:>4}  "
            f"{tp / max(1, tp + fp):>9.2f}  {tp / max(1, tp + fn):>6.2f}"
        )

    # Where one manual shows its controls
    _, sample = next(
        (producer, d)
        for producer, d in decisions
        if producer == "sectioned" and len(d.sections["spans"]) > 2
    )
    org = orgs[sample.subject_ids[0]]
    text = next(book.text for book in books if book.organisation == org)
    spans = sample.sections["spans"]
    print(f"\n{org}: {len(text)} characters in {len(spans)} sections")
    for index, (start, end) in enumerate(spans):
        shown = [
            control
            for control, section in sample.sections["answered_by"].items()
            if section == index and sample.results[control] == "yes"
        ]
        first_line = text[start:end].strip().splitlines()[0][:48]
        print(f"  section {index + 1} [{start}:{end}] {first_line!r}")
        print(f"      shows {', '.join(shown) or '-'}")


async def main_dashboard() -> None:
    async def feed():
        await asyncio.sleep(5)
        for book in manuals():
            await flock.publish(book)
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
