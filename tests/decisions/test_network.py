"""Decision networks: gathering decisions about one subject, runtime options."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, PrivateAttr

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.decisions import UNSURE, Checklist, Choice, Decision, YesNo
from flock.decisions.providers import FakeDecider
from flock.models.system_artifacts import WorkflowError
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@flock_type
class Case(BaseModel):
    text: str


@flock_type
class Handled(BaseModel):
    by: str


class Desk(Choice):
    """Which desk handles the case?"""

    billing = "Charges"
    tech = "Bugs"


class Rush(YesNo):
    """Does the case need an answer today?"""


Letter = Choice.from_options(
    "Letter",
    {letter: f"The letter {letter}" for letter in "abcdefgh"},
    question="Which letter fits best?",
)
FirstHalf = Checklist.from_items(
    "FirstHalf", {letter: f"Mentions {letter}" for letter in "abcd"}, question="Fits?"
)
SecondHalf = Checklist.from_items(
    "SecondHalf", {letter: f"Mentions {letter}" for letter in "efgh"}, question="Fits?"
)


class Recorder(EngineComponent):
    _seen: list = PrivateAttr(default_factory=list)

    @property
    def seen(self) -> list:
        return self._seen

    async def evaluate(self, agent, ctx, inputs, output_group):
        self._seen.append((list(inputs.artifacts), ctx.decisions))
        return EvalResult.from_object(Handled(by=agent.name), agent=agent)


@pytest.fixture
def flock() -> Flock:
    return Flock()


def listener(flock: Flock, name: str, *handles) -> Recorder:
    engine = Recorder()
    flock.agent(name).consumes(*handles).with_engines(engine).publishes(Handled)
    return engine


async def decisions_of(flock: Flock, question):
    name = type_registry.name_for(Decision.of(question))
    return [a for a in await flock.store.list() if a.type == name]


# --- several handles: AND about the same subject -----------------------------


async def test_handles_of_one_decider_combine_with_and(flock):
    answers = {"Desk": {"billing": 0.9, "tech": 0.1}, "Rush": {"yes": 0.8, "no": 0.2}}
    flock.agent("triage").consumes(Case).decides(Desk, Rush, model=FakeDecider(answers))
    urgent_billing = listener(flock, "urgent_billing", Desk.billing, Rush.yes)
    urgent_tech = listener(flock, "urgent_tech", Desk.tech, Rush.yes)

    case = await flock.publish(Case(text="Refund today please"))
    await flock.run_until_idle()

    ((inputs, decisions),) = urgent_billing.seen
    assert [a.id for a in inputs] == [case.id]  # the subject, once
    assert sorted(d.question for d in decisions) == ["Desk", "Rush"]
    assert urgent_tech.seen == []


async def test_gathering_waits_for_every_decider_per_subject(flock):
    flock.agent("desk").consumes(Case).decides(
        Desk,
        model=FakeDecider(
            lambda state: {"billing": 1.0, "tech": 0.0}
            if "refund" in state
            else {"billing": 0.0, "tech": 1.0}
        ),
    )
    flock.agent("rush").consumes(Case).decides(
        Rush, model=FakeDecider({"yes": 0.7, "no": 0.3})
    )
    gatherer = listener(flock, "gatherer", Desk.ANY, Rush.ANY)

    refund = await flock.publish(Case(text="refund"))
    crash = await flock.publish(Case(text="crash"))
    await flock.run_until_idle()

    assert len(gatherer.seen) == 2
    by_subject = {inputs[0].id: decisions for inputs, decisions in gatherer.seen}
    assert set(by_subject) == {refund.id, crash.id}
    desk_for = {
        subject: next(d.choice for d in decisions if d.question == "Desk")
        for subject, decisions in by_subject.items()
    }
    assert desk_for == {refund.id: "billing", crash.id: "tech"}


def test_handles_of_the_same_question_cannot_be_combined(flock):
    with pytest.raises(ValueError, match="same question"):
        flock.agent("a").consumes(Desk.billing, Desk.tech)


def test_handles_cannot_be_mixed_with_types(flock):
    with pytest.raises(ValueError, match="handles"):
        flock.agent("a").consumes(Case, Desk.billing)


# --- runtime options ----------------------------------------------------------


async def test_options_restrict_the_question_per_execution(flock):
    decider = FakeDecider({"Letter": dict.fromkeys("abcdefgh", 1 / 8) | {"c": 0.6}})
    flock.agent("pick").consumes(Case).decides(
        Letter, model=decider, options=lambda ctx: ["b", "c", "f"]
    )

    await flock.publish(Case(text="..."))
    await flock.run_until_idle()

    ((_state, (question,)),) = decider.requests
    assert list(question.options) == ["b", "c", "f"]
    (decision,) = await decisions_of(flock, Letter)
    assert decision.payload["choice"] == "c"
    assert set(decision.payload["probabilities"]) == {"b", "c", "f"}
    assert decision.payload["candidates"] == ["b", "c", "f"]


async def test_without_candidates_the_decision_is_unsure(flock):
    decider = FakeDecider({"Letter": {"a": 1.0}})
    flock.agent("pick").consumes(Case).decides(
        Letter, model=decider, options=lambda ctx: []
    )

    await flock.publish(Case(text="..."))
    await flock.run_until_idle()

    assert decider.requests == []
    (decision,) = await decisions_of(flock, Letter)
    assert decision.payload["choice"] == UNSURE
    assert decision.payload["best_guess"] is None
    assert decision.payload["candidates"] == []


async def test_a_single_candidate_wins_without_a_request(flock):
    decider = FakeDecider({"Letter": {"a": 1.0}})
    flock.agent("pick").consumes(Case).decides(
        Letter, model=decider, options=lambda ctx: ["g"], threshold=0.9
    )

    await flock.publish(Case(text="..."))
    await flock.run_until_idle()

    assert decider.requests == []
    (decision,) = await decisions_of(flock, Letter)
    assert decision.payload["choice"] == "g"
    assert decision.payload["probabilities"] == {"g": 1.0}


async def test_unknown_options_fail_the_execution(flock):
    flock.agent("pick").consumes(Case).decides(
        Letter, model=FakeDecider({"Letter": {"a": 1.0}}), options=lambda ctx: ["zz"]
    )

    await flock.publish(Case(text="..."))
    await flock.run_until_idle()

    assert await decisions_of(flock, Letter) == []
    errors = [
        a
        for a in await flock.store.list()
        if a.type == type_registry.name_for(WorkflowError)
    ]
    assert errors
    assert "zz" in errors[0].payload["error_message"]


async def test_options_restrict_checklist_items(flock):
    decider = FakeDecider({"FirstHalf": {"a": 0.9, "b": 0.1, "c": 0.9, "d": 0.1}})
    flock.agent("check").consumes(Case).decides(
        FirstHalf, model=decider, options=lambda ctx: ["a", "b"]
    )

    await flock.publish(Case(text="..."))
    await flock.run_until_idle()

    ((_state, questions),) = decider.requests
    assert [q.item for q in questions] == ["a", "b"]
    (decision,) = await decisions_of(flock, FirstHalf)
    assert decision.payload["results"] == {"a": "yes", "b": "no"}


def test_options_need_a_single_choice_or_checklist(flock):
    with pytest.raises(ValueError, match="options="):
        flock.agent("a").consumes(Case).decides(
            Rush,
            model=FakeDecider({"yes": 1.0, "no": 0.0}),
            options=lambda ctx: ["yes"],
        )
    with pytest.raises(ValueError, match="options="):
        flock.agent("b").consumes(Case).decides(
            Desk, Rush, model=FakeDecider({}), options=lambda ctx: ["billing"]
        )


# --- a screening network ------------------------------------------------------


async def test_screens_pass_candidates_to_a_ranker(flock):
    def mentions(state: str) -> dict[str, float]:
        return {
            letter: 0.95 if f"<{letter}>" in state else 0.05 for letter in "abcdefgh"
        }

    decider = FakeDecider({
        "FirstHalf": mentions,
        "SecondHalf": mentions,
        "Letter": lambda state: {
            letter: (0.9 if letter == "g" else 0.1) for letter in "abcdefgh"
        },
    })
    for screen in (FirstHalf, SecondHalf):
        flock.agent(f"screen_{screen.__name__}").consumes(Case).decides(
            screen, model=decider, threshold=0.5
        )

    def passes(ctx) -> list[str]:
        return [
            item
            for d in ctx.decisions
            for item, result in d.results.items()
            if result == "yes"
        ]

    ranker = Recorder()
    flock.agent("ranker").consumes(FirstHalf.ANY, SecondHalf.ANY).decides(
        Letter, model=decider, options=passes
    )
    flock.agent("winner_g").consumes(Letter.g).with_engines(ranker).publishes(Handled)

    case = await flock.publish(Case(text="mentions <b> and <g>"))
    await flock.run_until_idle()

    (decision,) = await decisions_of(flock, Letter)
    assert decision.produced_by == "ranker"
    assert decision.payload["candidates"] == ["b", "g"]
    assert decision.payload["choice"] == "g"
    assert decision.payload["subject_ids"] == [str(case.id)]
    ((inputs, _decisions),) = ranker.seen
    assert [a.id for a in inputs] == [case.id]


async def test_decision_views_show_the_candidates(flock):
    from flock.api.collector import DashboardEventCollector
    from flock.api.graph_builder import GraphAssembler
    from flock.components.server.models.graph import GraphRequest

    flock.is_dashboard = True
    flock.agent("pick").consumes(Case).decides(
        Letter,
        model=FakeDecider({"Letter": dict.fromkeys("abcdefgh", 1 / 8)}),
        options=lambda ctx: ["b", "c"],
    )
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    await flock.publish(Case(text="..."))
    await flock.run_until_idle()

    graph = await GraphAssembler(flock.store, collector, flock).build_snapshot(
        GraphRequest(view_mode="blackboard")
    )
    (view,) = [n.data["decision"] for n in graph.nodes if "decision" in n.data]
    assert view["candidates"] == ["b", "c"]

