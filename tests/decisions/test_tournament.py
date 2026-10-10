"""Tournaments: choices with many options, narrowed down in rounds."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, PrivateAttr

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.decisions import UNSURE, Choice, Decision, Tournament, YesNo
from flock.decisions.providers import FakeDecider
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@flock_type
class Statement(BaseModel):
    text: str


@flock_type
class Ack(BaseModel):
    by: str


Requirement = Choice.from_options(
    "Requirement",
    {f"req_{i:03d}": f"Requirement number {i}" for i in range(100)},
    question="Which requirement does the statement implement?",
)

Huge = Choice.from_options(
    "Huge", {f"h_{i:04d}": f"Option {i}" for i in range(1000)}, question="Which one?"
)


def peaked(winner: str, options) -> dict[str, float]:
    """A distribution with most mass on ``winner`` and a little everywhere else."""
    rest = (1.0 - 0.6) / (len(options) - 1)
    return {option: 0.6 if option == winner else rest for option in options}


class Recorder(EngineComponent):
    _seen: list = PrivateAttr(default_factory=list)

    @property
    def seen(self) -> list:
        return self._seen

    async def evaluate(self, agent, ctx, inputs, output_group):
        self._seen.append((list(inputs.artifacts), ctx.decision))
        return EvalResult.from_object(Ack(by=agent.name), agent=agent)


@pytest.fixture
def flock() -> Flock:
    return Flock()


async def decisions_of(flock: Flock, question):
    name = type_registry.name_for(Decision.of(question))
    return [a.payload for a in await flock.store.list() if a.type == name]


# --- definition and validation ---------------------------------------------


def test_choices_may_define_more_than_255_options():
    assert len(Huge.__options__) == 1000


def test_large_choices_need_a_tournament(flock):
    with pytest.raises(ValueError, match="255 options.*tournament"):
        flock.agent("mapper").consumes(Statement).decides(
            Huge, model=FakeDecider({"h_0000": 1.0})
        )


@pytest.mark.parametrize(("group_size", "keep"), [(1, 1), (20, 0), (20, 20), (300, 3)])
def test_tournament_settings_are_validated(group_size, keep):
    with pytest.raises(ValueError):
        Tournament(group_size=group_size, keep=keep)


def test_a_tournament_takes_exactly_one_choice(flock):
    class Urgent(YesNo):
        """Urgent?"""

    decider = FakeDecider({"Requirement": peaked("req_057", Requirement.__options__)})
    with pytest.raises(ValueError, match="one Choice"):
        flock.agent("a").consumes(Statement).decides(
            Requirement, Urgent, model=decider, tournament=Tournament()
        )
    with pytest.raises(ValueError, match="one Choice"):
        flock.agent("b").consumes(Statement).decides(
            Urgent, model=decider, tournament=Tournament()
        )


# --- rounds -----------------------------------------------------------------


async def test_groups_then_a_final_round(flock):
    decider = FakeDecider({"Requirement": peaked("req_057", Requirement.__options__)})
    flock.agent("mapper").consumes(Statement).decides(
        Requirement, model=decider, tournament=Tournament(group_size=20, keep=3)
    )

    statement = await flock.publish(Statement(text="We rotate keys yearly."))
    await flock.run_until_idle()

    # Round 1: five groups of 20 in one request; final: the 15 survivors
    assert [len(questions) for _state, questions in decider.requests] == [5, 1]
    group_sizes = [len(q.options) for q in decider.requests[0][1]]
    assert group_sizes == [20] * 5
    (final,) = decider.requests[1][1]
    assert len(final.options) == 15
    assert final.instructions == "Which requirement does the statement implement?"

    (decision,) = await decisions_of(flock, Requirement)
    assert decision["choice"] == "req_057"
    assert set(decision["probabilities"]) == set(final.options)
    assert decision["subject_ids"] == [str(statement.id)]
    (round_one,) = decision["rounds"]
    assert round_one["candidates"] == 100
    assert round_one["groups"] == 5
    assert round_one["refused_groups"] == 0
    assert len(round_one["survivors"]) == 15
    assert "req_057" in round_one["survivors"]


async def test_large_choices_take_several_rounds(flock):
    decider = FakeDecider({"Huge": peaked("h_0777", Huge.__options__)})
    flock.agent("mapper").consumes(Statement).decides(
        Huge, model=decider, tournament=Tournament(group_size=20, keep=2)
    )

    await flock.publish(Statement(text="..."))
    await flock.run_until_idle()

    # 1000 -> 50 groups -> 100 survivors -> 5 groups -> 10 -> final
    assert [len(questions) for _state, questions in decider.requests] == [50, 5, 1]
    (decision,) = await decisions_of(flock, Huge)
    assert [r["candidates"] for r in decision["rounds"]] == [1000, 100]
    assert decision["choice"] == "h_0777"


async def test_small_choices_skip_the_rounds(flock):
    class Team(Choice):
        """Which team?"""

        billing = "Charges"
        tech = "Bugs"

    decider = FakeDecider({"Team": {"billing": 0.8, "tech": 0.2}})
    flock.agent("mapper").consumes(Statement).decides(
        Team, model=decider, tournament=Tournament(group_size=20, keep=3)
    )

    await flock.publish(Statement(text="..."))
    await flock.run_until_idle()

    assert len(decider.requests) == 1
    (decision,) = await decisions_of(flock, Team)
    assert decision["choice"] == "billing"
    assert decision["rounds"] == []


async def test_threshold_applies_to_the_final_round(flock):
    flat = dict.fromkeys(Requirement.__options__, 1 / 100)
    flock.agent("mapper").consumes(Statement).decides(
        Requirement,
        model=FakeDecider({"Requirement": flat}),
        tournament=Tournament(group_size=20, keep=3),
        threshold=0.5,
    )

    await flock.publish(Statement(text="..."))
    await flock.run_until_idle()

    (decision,) = await decisions_of(flock, Requirement)
    assert decision["choice"] == UNSURE
    assert decision["best_guess"] in decision["rounds"][0]["survivors"]


async def test_option_subscribers_receive_the_subject(flock):
    decider = FakeDecider({"Requirement": peaked("req_057", Requirement.__options__)})
    flock.agent("mapper").consumes(Statement).decides(
        Requirement, model=decider, tournament=Tournament(group_size=20, keep=3)
    )
    engine = Recorder()
    flock.agent("owner").consumes(Requirement.req_057).with_engines(engine).publishes(
        Ack
    )

    statement = await flock.publish(Statement(text="..."))
    await flock.run_until_idle()

    ((inputs, decision),) = engine.seen
    assert [a.id for a in inputs] == [statement.id]
    assert decision.choice == "req_057"


async def test_refused_groups_keep_no_survivors(flock):
    decider = FakeDecider(
        {"Requirement": peaked("req_057", Requirement.__options__)},
        refuse=set(),
    )
    original = decider._answer

    def refuse_first_group(state, question):
        if question.name.endswith("_r0_g0"):
            from flock.decisions.providers import DecisionAnswer

            return DecisionAnswer(choice=None, probabilities={}, refused=True)
        return original(state, question)

    decider._answer = refuse_first_group
    flock.agent("mapper").consumes(Statement).decides(
        Requirement, model=decider, tournament=Tournament(group_size=20, keep=3)
    )

    await flock.publish(Statement(text="..."))
    await flock.run_until_idle()

    (decision,) = await decisions_of(flock, Requirement)
    (round_one,) = decision["rounds"]
    assert round_one["refused_groups"] == 1
    assert len(round_one["survivors"]) == 12
    assert not any(s < "req_020" for s in round_one["survivors"])


async def test_rounds_record_the_top_candidates_of_every_group(flock):
    decider = FakeDecider({"Requirement": peaked("req_057", Requirement.__options__)})
    flock.agent("mapper").consumes(Statement).decides(
        Requirement, model=decider, tournament=Tournament(group_size=20, keep=3)
    )

    await flock.publish(Statement(text="..."))
    await flock.run_until_idle()

    (decision,) = await decisions_of(flock, Requirement)
    (round_one,) = decision["rounds"]
    assert round_one["group_size"] == 20
    groups = round_one["group_results"]
    assert [g["size"] for g in groups] == [20] * 5
    assert all(not g["refused"] for g in groups)
    for group, start in zip(groups, range(0, 15, 3), strict=True):
        # Survivors first, then the two strongest eliminated options
        assert len(group["top"]) == 5
        probabilities = [p for _option, p in group["top"]]
        assert probabilities == sorted(probabilities, reverse=True)
        assert [o for o, _p in group["top"][:3]] == round_one["survivors"][
            start : start + 3
        ]
    winner_group = groups[2]  # req_040 .. req_059
    assert winner_group["top"][0][0] == "req_057"
    assert winner_group["top"][0][1] == pytest.approx(0.6 / (0.6 + 19 * 0.4 / 99))


# --- groups of one ------------------------------------------------------------

Odd = Choice.from_options(
    "Odd", {f"odd_{i:02d}": f"Option {i}" for i in range(21)}, question="Which one?"
)


@pytest.mark.parametrize(
    ("question", "tournament"),
    [
        (Odd, Tournament(group_size=20, keep=3)),  # groups of 20 and 1
        (Odd, Tournament(group_size=2, keep=1)),  # odd counts in every round
        (Huge, Tournament(group_size=111, keep=2)),  # 9 groups of 111 and 1
    ],
)
async def test_a_leftover_option_advances_without_a_request(
    flock, question, tournament
):
    """Choices need at least two options; a group of one is a bye."""
    options = list(question.__options__)
    decider = FakeDecider({question.__name__: peaked(options[-1], options)})
    flock.agent("mapper").consumes(Statement).decides(
        question, model=decider, tournament=tournament
    )

    await flock.publish(Statement(text="..."))
    await flock.run_until_idle()

    asked = [q for _state, questions in decider.requests for q in questions]
    assert all(len(q.options) >= 2 for q in asked)
    (decision,) = await decisions_of(flock, question)
    assert decision["choice"] == options[-1]
    first = decision["rounds"][0]
    assert first["group_results"][-1] == {
        "size": 1,
        "refused": False,
        "top": [[options[-1], 1.0]],
    }
