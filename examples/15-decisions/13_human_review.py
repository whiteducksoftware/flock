"""
Decision Models: Human Review

When the decision model is not sure, a person decides. The person's answer is
published as a decision of the same question about the same ticket, made by
the reviewer, and routes like any other decision: the ticket reaches the team
the person chose. Reviewed decisions double as labels for calibration.

- `triage` routes support tickets with a decision model
- `review_queue` gets the tickets the model was not sure about
- the team agents get the tickets routed to them, by the model or a person

In the CLI, a support lead reviews the queue in code: `flock.review()` with the
lead's choice for each unsure ticket. With USE_DASHBOARD = True, unsure
decisions show review buttons in the Blackboard View; a click publishes the
review the same way (`POST /api/control/decisions/{id}/review`).

🎯 Key Concepts:
- `await flock.review(decision_id, choice="tech", reviewer="lead")`; without
  `choice`, the decision's best guess is confirmed
- The review is a decision: probability 1.0, `model` and producer the reviewer,
  `review_of` the reviewed decision, same subject, correlation and visibility
- Choice, yes/no and scale decisions can be reviewed

🎛️  CONFIGURATION:
- DECISION_MODEL: Microsoft-Decision-1 on Azure AI Foundry (AZURE_API_BASE,
  AZURE_API_KEY) or DEFAULT_DECISION_MODEL
- THRESHOLD: high on purpose, so that some tickets need a person
- USE_DASHBOARD = True serves the dashboard and publishes one ticket every
  two seconds; review the unsure decisions there.
"""

import asyncio
import os

from pydantic import BaseModel, Field

from flock import Choice, Decision, EngineComponent, EvalResult, Flock
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
DECISION_MODEL = os.getenv("DEFAULT_DECISION_MODEL", "azure/decision-1")
THRESHOLD = 0.95
# ============================================================================


@flock_type
class SupportTicket(BaseModel):
    """A customer support ticket that needs routing."""

    subject: str
    message: str = Field(description="The customer's issue or question")


@flock_type
class Handled(BaseModel):
    """A ticket a team or the review queue took."""

    handler: str
    subject: str


class Route(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds, payment problems"
    shipping = "Delivery, tracking, returns"
    tech = "Bugs, crashes, login problems"


class Take(EngineComponent):
    """Takes the ticket; stands in for a real handler."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        ticket = SupportTicket(**inputs.artifacts[0].payload)
        return EvalResult.from_object(
            Handled(handler=agent.name, subject=ticket.subject), agent=agent
        )


flock = Flock(decision_model=DECISION_MODEL, no_output=True)
flock.agent("triage").consumes(SupportTicket).decides(Route, threshold=THRESHOLD)
flock.agent("review_queue").consumes(Route.UNSURE).with_engines(Take()).publishes(
    Handled
)
for team in ("billing", "shipping", "tech"):
    flock.agent(team).consumes(getattr(Route, team)).with_engines(Take()).publishes(
        Handled
    )


# Each ticket, and where the support lead would send it
TICKETS = [
    (
        SupportTicket(subject="Charged twice", message="My card was charged twice."),
        "billing",
    ),
    (
        SupportTicket(
            subject="Return label not working",
            message="The return label from the website gives an error when I print it.",
        ),
        "tech",
    ),
    (
        SupportTicket(
            subject="Refund for broken item",
            message="The blender arrived broken. I want my money back.",
        ),
        "billing",
    ),
    (
        SupportTicket(
            subject="Can't download my invoice",
            message="Every time I click 'Download invoice' I get logged out.",
        ),
        "tech",
    ),
    (
        SupportTicket(
            subject="Paid for a parcel that never came",
            message="I paid for express delivery three weeks ago. Nothing arrived and "
            "the tracking link is dead.",
        ),
        "shipping",
    ),
]
LEAD = {ticket.subject: team for ticket, team in TICKETS}


async def main_cli() -> None:
    print(f"\n⚖️  {len(TICKETS)} tickets, {DECISION_MODEL}, threshold {THRESHOLD}\n")
    for ticket, _ in TICKETS:
        await flock.publish(ticket)
    await flock.run_until_idle()

    store = await flock.store.list()
    subjects = {
        str(a.id): a.payload["subject"]
        for a in store
        if a.type == type_registry.name_for(SupportTicket)
    }
    model = Decision.of(Route)
    unsure = [
        a
        for a in store
        if a.type == type_registry.name_for(model) and a.payload["choice"] == "UNSURE"
    ]
    print(
        f"The model routed {len(TICKETS) - len(unsure)} tickets; {len(unsure)} wait for a person.\n"
    )

    # The support lead works through the review queue
    for decision in unsure:
        subject = subjects[decision.payload["subject_ids"][0]]
        choice = LEAD[subject]
        verdict = (
            "confirms" if choice == decision.payload["best_guess"] else "overrides"
        )
        print(
            f"  lead {verdict} {decision.payload['best_guess']} → {choice}: {subject}"
        )
        await flock.review(decision.id, choice=choice, reviewer="lead")
    await flock.run_until_idle()

    print("\nWho handled what:")
    for artifact in await flock.store.list():
        if artifact.type == type_registry.name_for(Handled):
            print(
                f"  {artifact.payload['handler']:<13} ← {artifact.payload['subject']}"
            )
    reviews = [
        a.payload
        for a in await flock.store.list()
        if a.type == type_registry.name_for(model) and a.payload["review_of"]
    ]
    print(f"\n{len(reviews)} reviewed decisions are labels for calibration.")


async def main_dashboard() -> None:
    async def feed():
        await asyncio.sleep(5)
        for ticket, _ in TICKETS:
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
