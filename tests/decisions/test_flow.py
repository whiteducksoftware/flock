"""Decision agents on the blackboard: deciding, routing, delivery, visibility."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, PrivateAttr

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.core.visibility import PrivateVisibility, PublicVisibility
from flock.decisions import UNSURE, Choice, Decision
from flock.decisions.providers import FakeDecider
from flock.models.system_artifacts import WorkflowError
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@flock_type
class Ticket(BaseModel):
    subject: str
    body: str


@flock_type
class CustomerNote(BaseModel):
    text: str


@flock_type
class Reply(BaseModel):
    team: str


class Route(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


class ReplyEngine(EngineComponent):
    """Records what it was given and replies as its agent."""

    _seen: list = PrivateAttr(default_factory=list)

    @property
    def seen(self) -> list:
        return self._seen

    async def evaluate(self, agent, ctx, inputs, output_group):
        self._seen.append((list(inputs.artifacts), ctx.decision))
        return EvalResult.from_object(Reply(team=agent.name), agent=agent)


@pytest.fixture
def flock() -> Flock:
    orchestrator = Flock()
    orchestrator.is_dashboard = True
    return orchestrator


def team(flock: Flock, name: str, handle) -> ReplyEngine:
    engine = ReplyEngine()
    flock.agent(name).consumes(handle).with_engines(engine).publishes(Reply)
    return engine


async def artifacts_of(flock: Flock, model: type[BaseModel]):
    name = type_registry.name_for(model)
    return [a for a in await flock.store.list() if a.type == name]


TICKET = Ticket(subject="Charged twice", body="My card was charged twice.")


async def test_decider_publishes_one_decision_about_its_input(flock):
    decider = FakeDecider({"billing": 0.9, "tech": 0.1})
    flock.agent("triage").consumes(Ticket).decides(Route, model=decider)

    ticket = await flock.publish(TICKET)
    await flock.run_until_idle()

    [artifact] = await artifacts_of(flock, Decision.of(Route))
    decision = Decision.of(Route)(**artifact.payload)
    assert artifact.produced_by == "triage"
    assert decision.question == "Route"
    assert decision.choice == "billing"
    assert decision.best_guess == "billing"
    assert decision.probabilities == {"billing": 0.9, "tech": 0.1}
    assert decision.subject_ids == [str(ticket.id)]
    assert decision.model == "fake"
    assert decision.latency_ms is not None


async def test_decider_sends_the_question_and_the_rendered_input(flock):
    decider = FakeDecider({"billing": 0.9, "tech": 0.1})
    flock.agent("triage").consumes(Ticket).decides(Route, model=decider)

    await flock.publish(TICKET)
    await flock.run_until_idle()

    [(state, question)] = decider.calls
    assert state == (
        'Ticket: {"subject": "Charged twice", "body": "My card was charged twice."}'
    )
    assert question.name == "Route"
    assert question.instructions == "Which team should handle this support ticket?"
    assert dict(question.options) == Route.__options__


async def test_instructions_override_the_docstring(flock):
    decider = FakeDecider({"billing": 0.9, "tech": 0.1})
    flock.agent("triage").consumes(Ticket).decides(
        Route, model=decider, instructions="Route by tone of voice."
    )

    await flock.publish(TICKET)
    await flock.run_until_idle()

    assert decider.calls[0][1].instructions == "Route by tone of voice."


async def test_only_the_chosen_option_runs_and_receives_the_subject(flock):
    flock.agent("triage").consumes(Ticket).decides(
        Route, model=FakeDecider({"billing": 0.9, "tech": 0.1})
    )
    billing = team(flock, "billing", Route.billing)
    tech = team(flock, "tech", Route.tech)

    ticket = await flock.publish(TICKET)
    await flock.run_until_idle()

    assert tech.seen == []
    [(inputs, decision)] = billing.seen
    assert [a.id for a in inputs] == [ticket.id]
    assert decision.choice == "billing"
    assert isinstance(decision, Decision.of(Route))


async def test_below_threshold_the_decision_goes_to_unsure(flock):
    flock.agent("triage").consumes(Ticket).decides(
        Route, model=FakeDecider({"billing": 0.6, "tech": 0.4}), threshold=0.8
    )
    billing = team(flock, "billing", Route.billing)
    supervisor = team(flock, "supervisor", Route.UNSURE)

    await flock.publish(TICKET)
    await flock.run_until_idle()

    assert billing.seen == []
    [(_, decision)] = supervisor.seen
    assert decision.choice == UNSURE
    assert decision.best_guess == "billing"
    assert decision.threshold == 0.8


async def test_any_handle_receives_every_decision(flock):
    flock.agent("triage").consumes(Ticket).decides(
        Route,
        model=FakeDecider(
            lambda s: {"billing": 1.0, "tech": 0.0}
            if "card" in s
            else {"billing": 0.0, "tech": 1.0}
        ),
    )
    audit = team(flock, "audit", Route.ANY)

    await flock.publish(TICKET)
    await flock.publish(Ticket(subject="Crash", body="The app crashes on start."))
    await flock.run_until_idle()

    assert sorted(decision.choice for _, decision in audit.seen) == ["billing", "tech"]


async def test_consuming_the_decision_type_delivers_the_decision(flock):
    flock.agent("triage").consumes(Ticket).decides(
        Route, model=FakeDecider({"billing": 0.9, "tech": 0.1})
    )
    auditor = team(flock, "auditor", Decision.of(Route))

    await flock.publish(TICKET)
    await flock.run_until_idle()

    [(inputs, decision)] = auditor.seen
    assert [a.type for a in inputs] == [type_registry.name_for(Decision.of(Route))]
    assert decision.choice == "billing"


async def test_consumption_is_recorded_on_the_decision(flock):
    flock.agent("triage").consumes(Ticket).decides(
        Route, model=FakeDecider({"billing": 0.9, "tech": 0.1})
    )
    team(flock, "billing", Route.billing)

    await flock.publish(TICKET)
    await flock.run_until_idle()

    envelopes, _ = await flock.store.query_artifacts(embed_meta=True, limit=100)
    consumers = {
        envelope.artifact.type: {c.consumer for c in envelope.consumptions}
        for envelope in envelopes
    }
    assert consumers[type_registry.name_for(Decision.of(Route))] == {"billing"}


async def test_decision_inherits_the_subject_visibility(flock):
    flock.agent("triage").consumes(Ticket).decides(
        Route, model=FakeDecider({"billing": 0.9, "tech": 0.1})
    )
    allowed = team(flock, "billing", Route.billing)
    outsider = team(flock, "billing_outsider", Route.billing)
    private = PrivateVisibility(agents={"triage", "billing"})

    await flock.publish(TICKET, visibility=private)
    await flock.run_until_idle()

    [decision] = await artifacts_of(flock, Decision.of(Route))
    assert decision.visibility == private
    assert len(allowed.seen) == 1
    assert outsider.seen == []


async def test_explicit_visibility_overrides_inheritance(flock):
    flock.agent("triage").consumes(Ticket).decides(
        Route,
        model=FakeDecider({"billing": 0.9, "tech": 0.1}),
        visibility=PublicVisibility(),
    )

    await flock.publish(TICKET, visibility=PrivateVisibility(agents={"triage"}))
    await flock.run_until_idle()

    [decision] = await artifacts_of(flock, Decision.of(Route))
    assert decision.visibility == PublicVisibility()


async def test_inputs_with_different_visibilities_fail_closed(flock):
    flock.agent("triage").consumes(Ticket, CustomerNote).decides(
        Route, model=FakeDecider({"billing": 0.9, "tech": 0.1})
    )

    await flock.publish(TICKET, visibility=PrivateVisibility(agents={"triage"}))
    await flock.publish(CustomerNote(text="VIP"))
    await flock.run_until_idle()

    assert await artifacts_of(flock, Decision.of(Route)) == []
    [error] = await artifacts_of(flock, WorkflowError)
    assert "visibilit" in error.payload["error_message"]


async def test_provider_failure_becomes_a_workflow_error(flock):
    flock.agent("triage").consumes(Ticket).decides(
        Route, model=FakeDecider({"marketing": 1.0})
    )

    await flock.publish(TICKET)
    await flock.run_until_idle()

    assert await artifacts_of(flock, Decision.of(Route)) == []
    [error] = await artifacts_of(flock, WorkflowError)
    assert error.payload["failed_agent"] == "triage"


def test_choice_handles_combine_only_across_questions(flock):
    with pytest.raises(ValueError, match="mixed with types"):
        flock.agent("x").consumes(Route.billing, Ticket)
    with pytest.raises(ValueError, match="same question"):
        flock.agent("y").consumes(Route.billing, Route.tech)


def test_decides_reads_the_default_model_from_the_environment(flock, monkeypatch):
    monkeypatch.setenv("DEFAULT_DECISION_MODEL", "local/clef-flash")

    agent = flock.agent("triage").consumes(Ticket).decides(Route).agent

    [engine] = agent.engines
    assert engine.provider.label == "local/clef-flash"


def test_decides_without_any_model_fails_early(flock, monkeypatch):
    monkeypatch.delenv("DEFAULT_DECISION_MODEL", raising=False)

    with pytest.raises(ValueError, match="DEFAULT_DECISION_MODEL"):
        flock.agent("triage").consumes(Ticket).decides(Route)


@pytest.mark.parametrize("threshold", [0.0, -0.1, 1.5])
def test_threshold_must_be_a_probability(flock, threshold):
    with pytest.raises(ValueError, match="threshold"):
        flock.agent("triage").consumes(Ticket).decides(
            Route, model=FakeDecider({"billing": 1.0, "tech": 0.0}), threshold=threshold
        )


def test_decides_owns_the_engine(flock):
    with pytest.raises(ValueError, match="engine"):
        (
            flock.agent("triage")
            .consumes(Ticket)
            .with_engines(ReplyEngine())
            .decides(Route, model=FakeDecider({"billing": 1.0, "tech": 0.0}))
        )


def test_decides_expects_a_choice(flock):
    with pytest.raises(TypeError, match="Choice"):
        flock.agent("triage").consumes(Ticket).decides(
            Ticket, model=FakeDecider({"billing": 1.0, "tech": 0.0})
        )
