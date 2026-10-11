"""Long documents: a text field split into sections, decided one by one (#474)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.decisions import UNSURE, Checklist, Choice, Decision, FakeDecider, Sections
from flock.decisions.sections import split_sections
from flock.decisions.tournament import Tournament
from flock.registry import flock_type, type_registry


@flock_type
class SecManual(BaseModel):
    title: str
    text: str


SecControls = Checklist.from_items(
    "SecControls",
    {"mfa": "MFA is enforced", "backup": "Backups are tested"},
    question="Does the document show that this control is implemented?",
)


class SecTopic(Choice):
    """What is this document mainly about?"""

    access = "Access control"
    backup = "Backups and recovery"


MANUAL = "Access\n\nMFA is enforced for all staff.\n\nBackups\n\nRestores are tested monthly."


def split_answers(state: str) -> dict:
    """Each section shows one control; a model only sees its section."""
    if "MFA" in state:
        return {"mfa": 0.97, "backup": 0.05}
    if "Restores" in state:
        return {"mfa": 0.04, "backup": 0.96}
    return {"mfa": 0.03, "backup": 0.04}


async def _decide(question, source, **kwargs):
    model = FakeDecider({question.__name__: source}, label="fake")
    flock = Flock()
    flock.agent("audit").consumes(SecManual).decides(question, model=model, **kwargs)
    await flock.publish(SecManual(title="Security manual", text=MANUAL))
    await flock.run_until_idle()
    name = type_registry.name_for(Decision.of(question))
    (decision,) = [a.payload for a in await flock.store.list() if a.type == name]
    return decision, model


def test_sections_follow_paragraphs_up_to_the_limit():
    text = "aaaa\n\nbbbb\n\ncccc"

    assert split_sections(text, max_chars=10) == [(0, 10), (12, 16)]
    assert split_sections(text, max_chars=100) == [(0, 16)]


def test_a_paragraph_longer_than_the_limit_is_split():
    spans = split_sections("x" * 25, max_chars=10)

    assert spans == [(0, 10), (10, 20), (20, 25)]


def test_a_trailing_space_makes_no_empty_section():
    assert split_sections("aa ", max_chars=2) == [(0, 2)]


async def test_a_refused_section_keeps_an_item_from_being_no():
    def refuse_restores(state: str) -> dict:
        return {"mfa": 0.97, "backup": 0.02}

    model = FakeDecider(
        {"SecControls": refuse_restores}, refuse={"SecControls.backup"}, label="fake"
    )
    flock = Flock()
    flock.agent("audit").consumes(SecManual).decides(
        SecControls,
        model=model,
        threshold=0.9,
        sections=Sections(field="text", max_chars=40),
    )
    await flock.publish(SecManual(title="Security manual", text=MANUAL))
    await flock.run_until_idle()

    name = type_registry.name_for(Decision.of(SecControls))
    (decision,) = [a.payload for a in await flock.store.list() if a.type == name]
    # Every section refused backup: no section says no for sure
    assert decision["results"]["backup"] == UNSURE


async def test_a_refusal_in_one_section_keeps_the_item_unsure():
    class OneRefusal(FakeDecider):
        async def decide_many(self, state, questions, images=()):
            answers = await super().decide_many(state, questions, images)
            if "Restores" in state:  # this section refuses backup
                from dataclasses import replace

                return {
                    name: replace(a, refused=True, choice=None, probabilities={})
                    if name == "SecControls_1"
                    else a
                    for name, a in answers.items()
                }
            return answers

    model = OneRefusal({"SecControls": {"mfa": 0.97, "backup": 0.02}}, label="fake")
    flock = Flock()
    flock.agent("audit").consumes(SecManual).decides(
        SecControls,
        model=model,
        threshold=0.9,
        sections=Sections(field="text", max_chars=40),
    )
    await flock.publish(SecManual(title="Security manual", text=MANUAL))
    await flock.run_until_idle()

    name = type_registry.name_for(Decision.of(SecControls))
    (decision,) = [a.payload for a in await flock.store.list() if a.type == name]
    # One section says no, the other refused: not every section says no
    assert decision["results"]["backup"] == UNSURE


async def test_too_many_sections_are_refused_before_any_request():
    model = FakeDecider({"SecControls": split_answers})
    flock = Flock()
    flock.agent("audit").consumes(SecManual).decides(
        SecControls,
        model=model,
        sections=Sections(field="text", max_chars=10, max_sections=3),
    )
    await flock.publish(SecManual(title="Security manual", text=MANUAL))
    await flock.run_until_idle()

    assert model.requests == []
    errors = [a for a in await flock.store.list() if "WorkflowError" in a.type]
    assert "max_sections" in errors[0].payload["error_message"]


async def test_section_requests_run_with_bounded_concurrency(monkeypatch):
    import asyncio

    monkeypatch.setattr("flock.decisions.engine.SECTION_CONCURRENCY", 2)

    class Counting(FakeDecider):
        running = peak = 0

        async def decide_many(self, state, questions, images=()):
            Counting.running += 1
            Counting.peak = max(Counting.peak, Counting.running)
            await asyncio.sleep(0.01)
            Counting.running -= 1
            return await super().decide_many(state, questions, images)

    model = Counting({"SecControls": split_answers})
    flock = Flock()
    flock.agent("audit").consumes(SecManual).decides(
        SecControls, model=model, sections=Sections(field="text", max_chars=10)
    )
    await flock.publish(SecManual(title="Security manual", text=MANUAL))
    await flock.run_until_idle()

    assert len(model.requests) > 2
    assert Counting.peak == 2


async def test_a_checklist_item_is_yes_if_any_section_shows_it():
    decision, model = await _decide(
        SecControls,
        split_answers,
        threshold=0.9,
        sections=Sections(field="text", max_chars=40),
    )

    assert decision["results"] == {"mfa": "yes", "backup": "yes"}
    assert decision["choice"] == "passed"
    assert len(model.requests) == len(decision["sections"]["spans"]) == 2


async def test_the_decision_points_to_the_section_that_answered():
    decision, _ = await _decide(
        SecControls,
        split_answers,
        threshold=0.9,
        sections=Sections(field="text", max_chars=40),
    )

    sections = decision["sections"]
    assert sections["field"] == "text"
    first, second = sections["spans"]
    assert "MFA" in MANUAL[first[0] : first[1]]
    assert "Restores" in MANUAL[second[0] : second[1]]
    assert sections["answered_by"] == {"mfa": 0, "backup": 1}


async def test_an_item_is_no_only_if_every_section_says_no():
    def nowhere(state: str) -> dict:
        return {"mfa": 0.02, "backup": 0.6 if "Restores" in state else 0.02}

    decision, _ = await _decide(
        SecControls,
        nowhere,
        threshold=0.9,
        sections=Sections(field="text", max_chars=40),
    )

    assert decision["results"] == {"mfa": "no", "backup": UNSURE}


async def test_a_choice_takes_the_most_confident_section():
    def topic(state: str) -> dict:
        if "MFA" in state:
            return {"access": 0.7, "backup": 0.3}
        return {"access": 0.05, "backup": 0.95}

    decision, _ = await _decide(
        SecTopic, topic, threshold=0.9, sections=Sections(field="text", max_chars=40)
    )

    assert decision["choice"] == "backup"
    assert decision["probabilities"]["backup"] == pytest.approx(0.95)
    assert decision["sections"]["answered_by"] == {"SecTopic": 1}


async def test_a_short_text_is_one_section():
    decision, model = await _decide(
        SecControls, split_answers, threshold=0.9, sections=Sections(field="text")
    )

    assert decision["sections"]["spans"] == [[0, len(MANUAL)]]
    assert len(model.requests) == 1


async def test_without_sections_a_decision_has_none():
    decision, _ = await _decide(SecControls, split_answers, threshold=0.9)

    assert decision["sections"] is None


async def test_escalation_asks_the_next_tier_per_section():
    def unsure(state: str) -> dict:
        return {"mfa": 0.6, "backup": 0.6}

    second = FakeDecider({"SecControls": split_answers}, label="strong")
    decision, _ = await _decide(
        SecControls,
        unsure,
        threshold=0.9,
        sections=Sections(field="text", max_chars=40),
        escalate=[second],
    )

    assert decision["results"] == {"mfa": "yes", "backup": "yes"}
    assert len(second.requests) == 2
    assert decision["sections"]["answered_by"] == {"mfa": 0, "backup": 1}


async def test_a_missing_field_fails_with_a_clear_error():
    flock = Flock()
    flock.agent("audit").consumes(SecManual).decides(
        SecControls,
        model=FakeDecider({"SecControls": split_answers}),
        sections=Sections(field="body"),
    )
    await flock.publish(SecManual(title="Security manual", text=MANUAL))
    await flock.run_until_idle()

    errors = [a for a in await flock.store.list() if "WorkflowError" in a.type]
    assert "'body'" in errors[0].payload["error_message"]


def test_sections_need_a_positive_limit():
    with pytest.raises(ValueError):
        Sections(field="text", max_chars=0)


def test_sections_cannot_be_combined_with_ensembles_or_tournaments():
    sections = Sections(field="text")
    with pytest.raises(ValueError, match="sections="):
        Flock().agent("a").consumes(SecManual).decides(
            SecControls,
            models=[FakeDecider({}), FakeDecider({})],
            sections=sections,
        )
    with pytest.raises(ValueError, match="sections="):
        Flock().agent("b").consumes(SecManual).decides(
            SecTopic,
            model=FakeDecider({}),
            tournament=Tournament(group_size=2, keep=1),
            sections=sections,
        )
