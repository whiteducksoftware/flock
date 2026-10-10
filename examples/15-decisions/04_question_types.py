"""
Decision Models: Yes/No, Scale and Choice Questions in One Call

One decision agent asks three questions about every support ticket, all in a
single request to the decision model:

- `Team` (Choice): which team handles the ticket
- `Urgent` (YesNo): does the customer need an answer today
- `Anger` (Scale): how angry is the customer, from calm to furious

Downstream agents subscribe to the answers they care about:

- `billing` and `tech` take the tickets routed to their team
- `pager` runs for urgent tickets (`Urgent.yes`)
- `deescalation` runs when the probability-weighted anger is at least
  "angry" (`Anger.angry.or_higher`), even if no single level is certain
- `supervisor` gets tickets whose team the model was not sure about

The handlers here only log, so the decision model is the only model called.

🎯 Key Concepts:
- `YesNo`: a yes/no question, asked natively (systemone `noul`, OpenAI
  `predicate`); optional `yes = "..."` / `no = "..."` describe the answers
- `Scale`: ordered levels, lowest first; the decision carries the most
  probable level and the weighted `score`
- `.decides(Team, Urgent, Anger)`: one request, one decision per question
- `.consumes(Anger.angry.or_higher)` / `.or_lower`: subscribe to a score range

🎛️  CONFIGURATION:
- USE_DASHBOARD = True serves the dashboard and publishes one ticket every
  two seconds.
- DECISION_MODEL below, or DEFAULT_DECISION_MODEL in your environment:
  "azure/decision-1" (default), "openai/gpt-6-luna", "jev/jev-latest" or
  "local/<name>" (see 01_ticket_triage.py).
"""

import asyncio
import os

from pydantic import BaseModel

from flock import (
    Choice,
    Decision,
    EngineComponent,
    EvalResult,
    Flock,
    Scale,
    YesNo,
)
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
DECISION_MODEL = os.getenv("DEFAULT_DECISION_MODEL", "azure/decision-1")
THRESHOLD = 0.8
# ============================================================================


@flock_type
class SupportTicket(BaseModel):
    """A customer support ticket."""

    subject: str
    message: str


@flock_type
class Handled(BaseModel):
    """What a handler did with a ticket."""

    handler: str
    subject: str


class Team(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds, payment problems"
    tech = "Bugs, crashes, login problems"


class Urgent(YesNo):
    """Does the customer need an answer today?"""

    yes = "A deadline today, money at stake right now, or a service outage"


class Anger(Scale):
    """How angry is the customer?"""

    calm = "Calm and polite"
    annoyed = "Annoyed but civil"
    angry = "Angry, complaining strongly"
    furious = "Furious, threatening to leave or escalate"


class LogHandler(EngineComponent):
    """Logs the ticket it received; stands in for a real handler."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        ticket = SupportTicket(**inputs.artifacts[0].payload)
        decision = ctx.decision
        print(
            f"  {agent.name:<13} ← {ticket.subject}  ({decision.question}: {decision.choice})"
        )
        return EvalResult.from_object(
            Handled(handler=agent.name, subject=ticket.subject), agent=agent
        )


# decision_model= is the default for every .decides() in this flock
flock = Flock(
    decision_model=DECISION_MODEL, no_output=True
)  # handlers print one line each

triage = (
    flock.agent("triage")
    .description("Answers three questions about every ticket in one request")
    .consumes(SupportTicket)
    .decides(Team, Urgent, Anger, threshold=THRESHOLD)
)

for name, handle in (
    ("billing", Team.billing),
    ("tech", Team.tech),
    ("supervisor", Team.UNSURE),
    ("pager", Urgent.yes),
    ("deescalation", Anger.angry.or_higher),
):
    flock.agent(name).consumes(handle).with_engines(LogHandler()).publishes(Handled)


TICKETS = [
    SupportTicket(
        subject="Charged twice AGAIN",
        message="Third time this month my card was charged twice. Refund it today "
        "or I cancel and tell everyone.",
    ),
    SupportTicket(
        subject="Dark mode request",
        message="Hi! Would be lovely to have a dark mode some day. Thanks!",
    ),
    SupportTicket(
        subject="Can't log in before my demo",
        message="Login fails with error 500 and I present to a client in two hours.",
    ),
    SupportTicket(
        subject="Invoice address",
        message="Could you change the address on last month's invoice? No rush.",
    ),
    SupportTicket(
        subject="App deleted my notes",
        message="The update wiped all my notes. This is unacceptable, I paid for "
        "this. Fix it now.",
    ),
    SupportTicket(
        subject="Weird charge after the app crashed",
        message="The app crashed during checkout and now there's a charge I "
        "don't recognise.",
    ),
]


async def main_cli():
    print(f"\n⚖️  Three questions per ticket with {DECISION_MODEL}\n")
    for ticket in TICKETS:
        await flock.publish(ticket)
    await flock.run_until_idle()

    store = await flock.store.list()
    subjects = {
        str(a.id): a.payload["subject"]
        for a in store
        if a.type == type_registry.name_for(SupportTicket)
    }
    answers: dict[str, dict[str, str]] = {}
    for question in (Team, Urgent, Anger):
        model = Decision.of(question)
        for artifact in store:
            if artifact.type != type_registry.name_for(model):
                continue
            decision = model(**artifact.payload)
            answer = decision.choice
            if decision.score is not None:
                answer += f" ({decision.score:.1f})"
            if decision.refused:
                answer = "refused"
            subject = subjects[decision.subject_ids[0]]
            answers.setdefault(subject, {})[question.__name__] = answer

    print("\n" + "=" * 78)
    print(f"{'ticket':<36} {'Team':<9} {'Urgent':<8} Anger")
    for subject, row in answers.items():
        print(f"{subject:<36} {row['Team']:<9} {row['Urgent']:<8} {row['Anger']}")


async def main_dashboard():
    async def feed():
        await asyncio.sleep(5)
        for ticket in TICKETS:
            await flock.publish(ticket)
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
