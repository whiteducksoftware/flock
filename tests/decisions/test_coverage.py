"""Coverage: checklist results combined across the artifacts of a group (#474)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from flock.core import Flock
from flock.core.visibility import PrivateVisibility
from flock.decisions import UNSURE, Checklist, Choice, FakeDecider
from flock.decisions.coverage import Coverage
from flock.registry import flock_type, type_registry


@flock_type
class CovDocument(BaseModel):
    org: str
    text: str


CovControls = Checklist.from_items(
    "CovControls",
    {"mfa": "MFA is enforced", "backup": "Backups are tested", "logs": "Logs are kept"},
    question="Does the document show that this control is implemented?",
)


class CovRoute(Choice):
    """Which team?"""

    a = "A"
    b = "B"


@flock_type
class CovAliased(BaseModel):
    org_name: str = Field(alias="orgName")
    text: str


# Per document text: probability of "yes" per control
ANSWERS = {
    "access policy": {"mfa": 0.97, "backup": 0.02, "logs": 0.6},
    "backup runbook": {"mfa": 0.03, "backup": 0.96, "logs": 0.02},
    "logging standard": {"mfa": 0.02, "backup": 0.03, "logs": 0.98},
}


COMPLETE = {"complete manual": {"mfa": 0.97, "backup": 0.96, "logs": 0.98}}


def by_text(state: str) -> dict[str, float]:
    answers = {**ANSWERS, **COMPLETE}
    return next(answer for text, answer in answers.items() if text in state)


def _flock(combine: str = "any", **aggregates) -> Flock:
    flock = Flock()
    flock.agent("audit").consumes(CovDocument).decides(
        CovControls, model=FakeDecider({"CovControls": by_text}), threshold=0.9
    )
    flock.agent("coverage").consumes(CovControls.ANY).aggregates(
        by="org", combine=combine, **aggregates
    )
    return flock


async def _coverages(flock: Flock) -> list:
    name = type_registry.name_for(Coverage.of(CovControls))
    return [a for a in await flock.store.list() if a.type == name]


async def _latest(flock: Flock, group: str) -> dict:
    """The current coverage of a group: the highest revision."""
    group_coverages = [
        a.payload for a in await _coverages(flock) if a.payload["group"] == group
    ]
    return max(group_coverages, key=lambda c: c["revision"])


async def test_any_document_can_show_a_control():
    flock = _flock()
    for text in ("access policy", "backup runbook"):
        await flock.publish(CovDocument(org="acme", text=text))
    await flock.run_until_idle()

    coverage = await _latest(flock, "acme")
    # mfa from the policy, backup from the runbook; logs: one unsure, one no
    assert coverage["results"] == {"mfa": "yes", "backup": "yes", "logs": UNSURE}
    assert coverage["choice"] == UNSURE
    assert coverage["combine"] == "any"
    assert len(coverage["subject_ids"]) == 2
    assert len(coverage["decision_ids"]) == 2


async def test_coverage_passes_once_every_control_is_shown():
    flock = _flock()
    for text in ("access policy", "backup runbook", "logging standard"):
        await flock.publish(CovDocument(org="acme", text=text))
    await flock.run_until_idle()

    coverage = await _latest(flock, "acme")
    assert coverage["results"] == {"mfa": "yes", "backup": "yes", "logs": "yes"}
    assert coverage["choice"] == "passed"


async def test_evidence_names_the_documents_that_show_each_control():
    flock = _flock()
    for text in ("access policy", "backup runbook"):
        await flock.publish(CovDocument(org="acme", text=text))
    await flock.run_until_idle()

    documents = {
        a.payload["text"]: str(a.id)
        for a in await flock.store.list()
        if a.type == type_registry.name_for(CovDocument)
    }
    coverage = await _latest(flock, "acme")
    assert coverage["evidence"] == {
        "mfa": [documents["access policy"]],
        "backup": [documents["backup runbook"]],
    }


async def test_groups_are_kept_apart():
    flock = _flock()
    await flock.publish(CovDocument(org="acme", text="access policy"))
    await flock.publish(CovDocument(org="globex", text="backup runbook"))
    await flock.run_until_idle()

    assert (await _latest(flock, "acme"))["results"]["mfa"] == "yes"
    assert (await _latest(flock, "acme"))["results"]["backup"] == "no"
    assert (await _latest(flock, "globex"))["results"]["backup"] == "yes"


async def test_all_needs_every_document_to_show_a_control():
    flock = _flock(combine="all")
    for text in ("access policy", "backup runbook"):
        await flock.publish(CovDocument(org="acme", text=text))
    await flock.run_until_idle()

    coverage = await _latest(flock, "acme")
    assert coverage["results"] == {"mfa": "no", "backup": "no", "logs": "no"}
    assert coverage["choice"] == "failed"


async def test_a_coverage_is_published_per_arrival_with_a_growing_revision():
    flock = _flock()
    for text in ANSWERS:
        await flock.publish(CovDocument(org="acme", text=text))
    await flock.run_until_idle()

    coverages = [c.payload for c in await _coverages(flock)]
    assert len(coverages) == 3
    # A revision counts the combined decisions (history included); whatever
    # order the coverages were stored in, the highest one has everything
    assert all(c["revision"] == len(c["decision_ids"]) for c in coverages)
    current = max(coverages, key=lambda c: c["revision"])
    assert current["revision"] == 3


async def test_a_callable_key_groups_by_anything():
    flock = Flock()
    flock.agent("audit").consumes(CovDocument).decides(
        CovControls, model=FakeDecider({"CovControls": by_text}), threshold=0.9
    )
    flock.agent("coverage").consumes(CovControls.ANY).aggregates(
        by=lambda document: document.org.upper()
    )
    await flock.publish(CovDocument(org="acme", text="access policy"))
    await flock.run_until_idle()

    assert (await _latest(flock, "ACME"))["results"]["mfa"] == "yes"


async def test_history_only_counts_decisions_that_reach_the_aggregator():
    flock = Flock()
    flock.agent("audit").consumes(CovDocument).decides(
        CovControls, model=FakeDecider({"CovControls": by_text}), threshold=0.9
    )
    # Only failed checklists reach this aggregator
    flock.agent("coverage").consumes(CovControls.failed).aggregates(by="org")
    await flock.publish(CovDocument(org="acme", text="complete manual"))  # passed
    await flock.run_until_idle()
    await flock.publish(CovDocument(org="acme", text="backup runbook"))  # failed
    await flock.run_until_idle()

    coverage = await _latest(flock, "acme")
    assert coverage["revision"] == 1  # the passed decision stays out


def test_a_callable_key_works_for_alias_only_models():
    from flock.core.artifacts import Artifact
    from flock.decisions.coverage import AggregateEngine

    engine = AggregateEngine(
        question=CovControls, by=lambda document: document.org_name
    )
    # Stored payloads use field names, not aliases
    subject = Artifact(
        type=type_registry.name_for(CovAliased),
        payload={"org_name": "acme", "text": "access policy"},
        produced_by="external",
    )

    assert engine._key(subject) == "acme"


async def test_coverage_keeps_the_documents_visibility():
    flock = _flock()
    private = PrivateVisibility(agents={"audit", "coverage"})
    await flock.publish(
        CovDocument(org="acme", text="access policy"), visibility=private
    )
    await flock.run_until_idle()

    (coverage,) = await _coverages(flock)
    assert coverage.visibility.agents == {"audit", "coverage"}


async def test_documents_with_different_visibilities_need_an_explicit_readership():
    flock = _flock()
    await flock.publish(
        CovDocument(org="acme", text="access policy"),
        visibility=PrivateVisibility(agents={"audit", "coverage"}),
    )
    await flock.publish(CovDocument(org="acme", text="backup runbook"))
    await flock.run_until_idle()

    errors = [a for a in await flock.store.list() if "WorkflowError" in a.type]
    assert ".aggregates()" in errors[0].payload["error_message"]


async def test_aggregates_visibility_sets_the_readership():
    flock = _flock(visibility=PrivateVisibility(agents={"ciso"}))
    await flock.publish(
        CovDocument(org="acme", text="access policy"),
        visibility=PrivateVisibility(agents={"audit", "coverage"}),
    )
    await flock.publish(CovDocument(org="acme", text="backup runbook"))
    await flock.run_until_idle()

    coverage = (await _coverages(flock))[-1]
    assert coverage.visibility.agents == {"ciso"}


def test_aggregates_needs_one_checklist_handle():
    with pytest.raises(ValueError, match="checklist"):
        Flock().agent("x").consumes(CovDocument).aggregates(by="org")
    with pytest.raises(ValueError, match="checklist"):
        Flock().agent("x").consumes(CovRoute.ANY).aggregates(by="org")


def test_unknown_combine_is_rejected():
    with pytest.raises(ValueError, match="combine="):
        Flock().agent("x").consumes(CovControls.ANY).aggregates(
            by="org", combine="most"
        )


def test_aggregates_cannot_be_combined_with_publishes():
    with pytest.raises(ValueError, match="publishes"):
        Flock().agent("x").consumes(CovControls.ANY).publishes(CovDocument).aggregates(
            by="org"
        )


def test_an_aggregator_cannot_publish_or_take_engines_or_batches_later():
    from flock.core.subscription import BatchSpec
    from flock.engines.dspy_engine import DSPyEngine

    builder = Flock().agent("x").consumes(CovControls.ANY).aggregates(by="org")

    with pytest.raises(ValueError, match="coverage"):
        builder.publishes(CovDocument)
    with pytest.raises(ValueError, match="aggregates"):
        builder.with_engines(DSPyEngine())
    with pytest.raises(ValueError, match="batch"):
        builder.consumes(CovControls.failed, batch=BatchSpec(size=2))


def test_only_handles_of_the_same_checklist_can_be_added_later():
    builder = Flock().agent("x").consumes(CovControls.ANY).aggregates(by="org")

    builder.consumes(CovControls.failed)  # the same checklist: fine
    with pytest.raises(ValueError, match="handle"):
        builder.consumes(CovDocument)
    with pytest.raises(ValueError, match="handle"):
        builder.consumes(CovRoute.a)
