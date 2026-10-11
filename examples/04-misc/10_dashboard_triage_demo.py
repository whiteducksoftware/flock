"""
Dashboard demo: a ticket triage that shows every state, without API keys
=======================================================================

The flock of the dashboard's design mockups. Everything runs locally:
decisions come from a FakeDecider that takes a moment to think, and the
teams' replies from a scripted engine that streams canned text token by
token, like an LLM. No API keys, no network. Use it to look at the
dashboard, take screenshots and compare two dashboard versions on the same
data.

- `external` publishes a SupportTicket every few seconds.
- `triage` decides Route (billing, shipping, tech). Some tickets stay UNSURE
  and wait for a person: review them on the decision card in the dashboard.
- `urgency` decides Urgent.
- `billing_team`, `shipping_team`, `tech_support` and `supervisor` (on
  Route.UNSURE) stream a TeamReply.
- Every run reports tokens and a cost at demo prices (MODEL_PRICES).
- `pager` pages for urgent tech tickets (Route.tech AND Urgent.yes).
- `follow_up_desk` joins a reply with the customer's follow-up by ticket ID;
  every second ticket gets one, so joins wait or expire.
- `weekly_report` collects replies in batches of 5.
- `crm_sync` files every reply and fails every third time.
- `digest` runs every 30 seconds.

Run:
    uv run python examples/04-misc/10_dashboard_triage_demo.py
    uv run python examples/04-misc/10_dashboard_triage_demo.py --port 8345

Open http://localhost:8344 (or the port you chose).
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import re
from dataclasses import replace
from datetime import timedelta
from typing import Any, ClassVar
from uuid import uuid4

from pydantic import BaseModel

from flock import Choice, Flock, YesNo
from flock.components.agent import EngineComponent
from flock.components.server.models.events import StreamingOutputEvent
from flock.core import Agent
from flock.core.artifacts import Artifact
from flock.core.context_provider import DefaultContextProvider, EmptyContextProvider
from flock.core.subscription import BatchSpec, JoinSpec
from flock.decisions import FakeDecider
from flock.engines.streaming.sinks import WebSocketSink
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalInputs, EvalResult


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
TICKET_SECONDS = 4.0  # between two tickets
FOLLOW_UP_SECONDS = 20.0  # until a customer follows up
TOKEN_SECONDS = 0.05  # between two streamed tokens
DECIDE_SECONDS = 0.8  # a decision model's think time
SCRIPTED_MODEL = "demo/scripted-llm"  # what the scripted replies bill as
# Demo prices in USD per million tokens, so runs show a cost
MODEL_PRICES = {SCRIPTED_MODEL: (2.0, 8.0), "demo-decider": (0.5, 0.0)}
# ============================================================================


@flock_type
class SupportTicket(BaseModel):
    """A customer's support request."""

    ticket_id: str
    title: str
    body: str


@flock_type
class TeamReply(BaseModel):
    """A team's answer to a ticket."""

    ticket_id: str
    team: str
    reply: str


@flock_type
class Page(BaseModel):
    """An on-call page for an urgent tech ticket."""

    ticket_id: str
    message: str


@flock_type
class CustomerFollowUp(BaseModel):
    """The customer writes again about a ticket."""

    ticket_id: str
    note: str


@flock_type
class Resolution(BaseModel):
    """A reply and the customer's follow-up, settled together."""

    ticket_id: str
    summary: str


@flock_type
class TeamReport(BaseModel):
    """What the teams answered in one batch."""

    replies: int
    teams: list[str]


@flock_type
class CrmRecord(BaseModel):
    """A reply filed in the CRM."""

    ticket_id: str
    status: str


@flock_type
class Digest(BaseModel):
    """What happened on the blackboard so far."""

    summary: str


class Route(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds"
    shipping = "Parcels, addresses, deliveries"
    tech = "Bugs, crashes, login problems"


class Urgent(YesNo):
    """Does the customer need an answer today?"""


# Title, body, route probabilities, probability of urgent. At threshold 0.8,
# "Something odd with my account" and "Change plan and address" stay UNSURE.
TICKETS: list[tuple[str, str, dict[str, float], float]] = [
    (
        "Refund not received",
        "I returned the jacket two weeks ago and still have no refund.",
        {"billing": 0.91, "shipping": 0.07, "tech": 0.02},
        0.30,
    ),
    (
        "Where is my parcel?",
        "Tracking says delivered, but nothing arrived.",
        {"billing": 0.04, "shipping": 0.88, "tech": 0.08},
        0.62,
    ),
    (
        "App crashes on login",
        "The app closes right after I enter my password.",
        {"billing": 0.02, "shipping": 0.03, "tech": 0.95},
        0.91,
    ),
    (
        "Invoice copy",
        "Please send my invoice again.",
        {"billing": 0.95, "shipping": 0.03, "tech": 0.02},
        0.08,
    ),
    (
        "Something odd with my account",
        "My address and my plan both look different today.",
        {"billing": 0.44, "shipping": 0.46, "tech": 0.10},
        0.40,
    ),
    (
        "Charged twice",
        "My card shows two charges for one order.",
        {"billing": 0.90, "shipping": 0.02, "tech": 0.08},
        0.85,
    ),
    (
        "Damaged package",
        "The box arrived crushed and the mug inside is broken.",
        {"billing": 0.10, "shipping": 0.86, "tech": 0.04},
        0.20,
    ),
    (
        "Password reset loop",
        "Every reset link sends me back to the login page.",
        {"billing": 0.03, "shipping": 0.02, "tech": 0.89},
        0.83,
    ),
    (
        "Change plan and address",
        "I want a cheaper plan, and I moved last week.",
        {"billing": 0.38, "shipping": 0.52, "tech": 0.10},
        0.15,
    ),
]

REPLIES = {
    "billing_team": (
        "Sorry about that! I checked your account and refunded the amount; it "
        "shows on your statement within three working days. A fresh copy of "
        "your invoice is attached."
    ),
    "shipping_team": (
        "Thanks for letting us know. I opened a claim with the carrier and "
        "booked a replacement that ships today; you get the tracking link by "
        "email within the hour."
    ),
    "tech_support": (
        "Sorry about the trouble! Please update to the latest version of the "
        "app; it fixes this crash. If it happens again, send us the time it "
        "happened and we look at the logs."
    ),
    "supervisor": (
        "Thanks for your patience. Your request touches more than one team, "
        "so I took it over myself: I fixed your address, adjusted your plan "
        "and will confirm both by email today."
    ),
}


def _ticket(state: str) -> tuple[str, str, dict[str, float], float]:
    """The catalog entry of the ticket a decision is about."""
    return next((t for t in TICKETS if t[0] in state), TICKETS[0])


def route(state: str) -> dict[str, float]:
    return _ticket(state)[2]


def urgent(state: str) -> dict[str, float]:
    p = _ticket(state)[3]
    return {"yes": p, "no": 1 - p}


class ThinkingDecider(FakeDecider):
    """A FakeDecider that takes a moment, like a decision model over the network."""

    def __init__(self, *args: Any, seconds: float = DECIDE_SECONDS, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.seconds = seconds

    async def decide_many(self, state, questions, images=()):
        await asyncio.sleep(self.seconds)
        # A demo runs for hours: keep only the last request
        self.requests.clear()
        self.calls.clear()
        self.received_images.clear()
        answers = await super().decide_many(state, questions, images)
        # Like a decision model's API: the request's input tokens, on every answer
        tokens = len(state) // 4
        return {name: replace(a, input_tokens=tokens) for name, a in answers.items()}


class ScriptedReplyEngine(EngineComponent):
    """Streams a canned reply token by token, like an LLM, then publishes it."""

    # Stands in for an LLM, so the dashboard tags it as one
    kind: ClassVar[str | None] = "LLM"
    token_seconds: float = TOKEN_SECONDS

    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group):
        ticket = inputs.first_as(SupportTicket)
        reply = TeamReply(
            ticket_id=ticket.ticket_id, team=agent.name, reply=REPLIES[agent.name]
        )
        artifact_id = uuid4()  # the streaming preview and the reply share it
        reply_type = type_registry.name_for(TeamReply)

        def event(kind: str, content: str, sequence: int, final: bool):
            return StreamingOutputEvent(
                correlation_id=str(ctx.correlation_id or ""),
                agent_name=agent.name,
                run_id=str(ctx.task_id),
                output_type=kind,
                content=content,
                sequence=sequence,
                is_final=final,
                artifact_id=str(artifact_id),
                artifact_type=reply_type,
            )

        sink = WebSocketSink(
            ws_broadcast=Agent._websocket_broadcast_global, event_factory=event
        )
        tokens = re.findall(r"\S+\s*", reply.reply)
        for token in tokens:
            await sink.on_token(token, "reply")
            await asyncio.sleep(self.token_seconds)
        await sink.on_final(reply, len(tokens))
        await sink.flush()
        # What an LLM would have reported: the prompt and the streamed tokens
        usage = {
            SCRIPTED_MODEL: {
                "prompt_tokens": 180 + len(ticket.body) // 4,
                "completion_tokens": len(tokens),
            }
        }
        return EvalResult(
            artifacts=[
                Artifact(
                    id=artifact_id,
                    type=reply_type,
                    payload=reply.model_dump(),
                    produced_by=agent.name,
                )
            ],
            metrics={"usage": usage},
        )


class ScriptEngine(EngineComponent):
    """Runs a small async function instead of a model."""

    fn: Any = None

    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group):
        produced = await self.fn(agent, ctx, inputs)
        if not produced:
            return EvalResult(artifacts=[])
        return EvalResult.from_objects(*produced, agent=agent)


async def page(agent, ctx, inputs):
    ticket = inputs.first_as(SupportTicket)
    return [Page(ticket_id=ticket.ticket_id, message=f"Urgent: {ticket.title}")]


async def resolve(agent, ctx, inputs):
    reply_type = type_registry.name_for(TeamReply)
    reply = next(
        TeamReply(**a.payload) for a in inputs.artifacts if a.type == reply_type
    )
    return [
        Resolution(
            ticket_id=reply.ticket_id,
            summary=f"{reply.team} answered, and the customer confirmed.",
        )
    ]


async def report(agent, ctx, inputs):
    replies = inputs.all_as(TeamReply)
    return [TeamReport(replies=len(replies), teams=sorted({r.team for r in replies}))]


class FlakyCrm:
    """Files replies in a CRM that is unreachable every third time."""

    def __init__(self) -> None:
        self.calls = itertools.count(1)

    async def __call__(self, agent, ctx, inputs):
        reply = inputs.first_as(TeamReply)
        if next(self.calls) % 3 == 0:
            raise RuntimeError("CRM unreachable (HTTP 503)")
        return [CrmRecord(ticket_id=reply.ticket_id, status="filed")]


async def digest(agent, ctx, inputs):
    counts: dict[str, int] = {}
    for artifact in ctx.artifacts:
        name = artifact.type.rsplit(".", 1)[-1]
        counts[name] = counts.get(name, 0) + 1
    tickets = counts.get("SupportTicket", 0)
    replies = counts.get("TeamReply", 0)
    return [Digest(summary=f"{tickets} tickets, {replies} replies so far")]


def build_flock(
    *,
    token_seconds: float = TOKEN_SECONDS,
    decide_seconds: float = DECIDE_SECONDS,
    digest_every: timedelta | None = timedelta(seconds=30),
) -> Flock:
    """The triage flock. Shorter waits, and no digest (a timer keeps a flock
    from ever being idle), make it fast enough for tests."""
    flock = Flock(
        no_output=True,
        # A served flock is never idle, and the circuit breaker only resets
        # when it is: without a high limit, agents stop after 1,000 runs
        max_agent_iterations=10**9,
        # Agents read their inputs only; history would make every run slower
        context_provider=EmptyContextProvider(),
        model_prices=MODEL_PRICES,
    )
    decider = ThinkingDecider(
        {"Route": route, "Urgent": urgent}, label="demo-decider", seconds=decide_seconds
    )

    flock.agent("triage").description("Routes support tickets to a team").consumes(
        SupportTicket
    ).decides(Route, model=decider, threshold=0.8)
    flock.agent("urgency").description(
        "Decides whether a ticket needs an answer today"
    ).consumes(SupportTicket).decides(Urgent, model=decider, threshold=0.8)

    teams = {
        "billing_team": (
            Route.billing,
            "Answers billing questions as the billing team",
        ),
        "shipping_team": (Route.shipping, "Answers delivery questions"),
        "tech_support": (Route.tech, "Helps with bugs and login problems"),
        "supervisor": (Route.UNSURE, "Takes the tickets triage is not sure about"),
    }
    for name, (handle, description) in teams.items():
        flock.agent(name).description(description).consumes(handle).publishes(
            TeamReply
        ).with_engines(ScriptedReplyEngine(token_seconds=token_seconds))

    flock.agent("pager").description("Pages on-call for urgent tech tickets").consumes(
        Route.tech, Urgent.yes
    ).publishes(Page).with_engines(ScriptEngine(fn=page))
    flock.agent("follow_up_desk").description(
        "Settles a reply together with the customer's follow-up"
    ).consumes(
        TeamReply,
        CustomerFollowUp,
        join=JoinSpec(by=lambda m: m.ticket_id, within=timedelta(minutes=2)),
    ).publishes(Resolution).with_engines(ScriptEngine(fn=resolve))
    flock.agent("weekly_report").description(
        "Summarizes the replies in batches of five"
    ).consumes(
        TeamReply, batch=BatchSpec(size=5, timeout=timedelta(seconds=90))
    ).publishes(TeamReport).with_engines(ScriptEngine(fn=report))
    flock.agent("crm_sync").description("Files every reply in the CRM").consumes(
        TeamReply
    ).publishes(CrmRecord).with_engines(ScriptEngine(fn=FlakyCrm()))
    if digest_every is not None:
        flock.agent("digest").description(
            "Counts what happened, every 30 seconds"
        ).schedule(every=digest_every).with_context(DefaultContextProvider()).publishes(
            Digest
        ).with_engines(ScriptEngine(fn=digest))
    return flock


def ticket(number: int) -> SupportTicket:
    title, body, _, _ = TICKETS[(number - 1) % len(TICKETS)]
    return SupportTicket(ticket_id=f"T-{number:04d}", title=title, body=body)


async def feed(flock: Flock, seconds: float, follow_up_seconds: float) -> None:
    """Publish a ticket every few seconds; every second one gets a follow-up."""
    follow_ups: set[asyncio.Task[None]] = set()

    async def follow_up(ticket_id: str) -> None:
        await asyncio.sleep(follow_up_seconds)
        await flock.publish(
            CustomerFollowUp(ticket_id=ticket_id, note="Any news on this?")
        )

    await asyncio.sleep(3)  # let the dashboard start
    for number in itertools.count(1):
        await flock.publish(ticket(number))
        if number % 2 == 0:
            task = asyncio.create_task(follow_up(f"T-{number:04d}"))
            follow_ups.add(task)
            task.add_done_callback(follow_ups.discard)
        await asyncio.sleep(seconds)


async def main(port: int, seconds: float) -> None:
    flock = build_flock()
    feeder = asyncio.create_task(feed(flock, seconds, FOLLOW_UP_SECONDS))
    try:
        await flock.serve(dashboard=True, port=port)
    finally:
        feeder.cancel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8344)
    parser.add_argument(
        "--seconds", type=float, default=TICKET_SECONDS, help="between two tickets"
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.port, arguments.seconds))
