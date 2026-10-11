"""
Decision Models: Explain on Demand

Decision models give probabilities, no reasons. When a person has to look at
a ticket the router was not sure about, a reason helps. An LLM agent
subscribed to the UNSURE branch writes an explanation of every decision that
reaches it, so the LLM runs only for the hard cases.

- `triage` routes support tickets with a decision model
- `explainer` consumes `Route.UNSURE` and `.explains()` each of those
  decisions: why the ticket is hard to route, citing the ticket, and what
  would settle it
- the team agents get the tickets routed to them; they only log here

🎯 Key Concepts:
- `.consumes(Route.UNSURE).explains(model=...)`: an explaining agent
- `Explanation`: `explanation`, `missing`, linked to the decision
  (`decision_ids`) and the ticket (`subject_ids`), with the ticket's visibility
- The LLM sees the ticket and the decision (question, options, probabilities,
  threshold); it does not answer the question itself

🎛️  CONFIGURATION:
- DECISION_MODEL: Microsoft-Decision-1 on Azure AI Foundry (AZURE_API_BASE,
  AZURE_API_KEY) or any other decision model
- EXPLAIN_MODEL: the LLM that writes the explanations (DEFAULT_MODEL)
- USE_DASHBOARD = True serves the dashboard and publishes one ticket every
  three seconds; unsure decisions show their explanation.
"""

import asyncio
import os

from pydantic import BaseModel, Field

from flock import Choice, Decision, EngineComponent, EvalResult, Flock
from flock.decisions.explain import Explanation
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
DECISION_MODEL = os.getenv("DEFAULT_DECISION_MODEL", "azure/decision-1")
EXPLAIN_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-4.1")
THRESHOLD = 0.95
# ============================================================================


@flock_type
class SupportTicket(BaseModel):
    """A customer support ticket that needs routing."""

    subject: str
    message: str = Field(description="The customer's issue or question")


@flock_type
class Handled(BaseModel):
    """A ticket a team took."""

    team: str
    subject: str


class Route(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds, payment problems"
    shipping = "Delivery, tracking, returns"
    tech = "Bugs, crashes, login problems"


class Take(EngineComponent):
    """A team takes the ticket; stands in for a real handler."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        ticket = SupportTicket(**inputs.artifacts[0].payload)
        return EvalResult.from_object(
            Handled(team=agent.name, subject=ticket.subject), agent=agent
        )


flock = Flock(EXPLAIN_MODEL, decision_model=DECISION_MODEL, no_output=True)
flock.agent("triage").consumes(SupportTicket).decides(Route, threshold=THRESHOLD)
for team in ("billing", "shipping", "tech"):
    flock.agent(team).consumes(getattr(Route, team)).with_engines(Take()).publishes(
        Handled
    )
flock.agent("explainer").consumes(Route.UNSURE).explains(model=EXPLAIN_MODEL)


TICKETS = [
    SupportTicket(subject="Charged twice", message="My card was charged twice."),
    SupportTicket(
        subject="Parcel missing", message="Tracking says delivered, nothing here."
    ),
    SupportTicket(subject="App crash", message="The app crashes when I open it."),
    SupportTicket(
        subject="Refund for broken item",
        message="The blender arrived broken. I want my money back.",
    ),
    SupportTicket(
        subject="Weird charge after the app crashed",
        message="The app crashed during checkout and now there's a charge I "
        "don't recognise.",
    ),
    SupportTicket(
        subject="Return label not working",
        message="The return label from the website gives an error when I print it.",
    ),
    SupportTicket(
        subject="Paid for a parcel that never came",
        message="I paid for express delivery three weeks ago. Nothing arrived and "
        "the tracking link is dead.",
    ),
    SupportTicket(
        subject="Can't download my invoice",
        message="Every time I click 'Download invoice' I get logged out.",
    ),
]


async def main_cli() -> None:
    print(f"\n⚖️  {len(TICKETS)} tickets, {DECISION_MODEL}, threshold {THRESHOLD}")
    print(f"💬 {EXPLAIN_MODEL} explains the unsure ones\n")
    for ticket in TICKETS:
        await flock.publish(ticket)
    await flock.run_until_idle()

    store = await flock.store.list()
    subjects = {
        str(a.id): a.payload["subject"]
        for a in store
        if a.type == type_registry.name_for(SupportTicket)
    }
    explanations = {
        sid: a.payload
        for a in store
        if a.type == type_registry.name_for(Explanation)
        for sid in a.payload["subject_ids"]
    }
    model = Decision.of(Route)
    for artifact in store:
        if artifact.type != type_registry.name_for(model):
            continue
        decision = model(**artifact.payload)
        subject = subjects[decision.subject_ids[0]]
        top = sorted(decision.probabilities.items(), key=lambda kv: -kv[1])[:2]
        odds = "  ".join(f"{option} {p:.2f}" for option, p in top)
        print(f"{subject:<36} → {decision.choice:<9} [{odds}]")
        explanation = explanations.get(decision.subject_ids[0])
        if explanation:
            print(f"   💬 {explanation['explanation']}")
            if explanation.get("missing"):
                print(f"   ❓ {explanation['missing']}")
    runs = len(explanations)
    print(
        f"\nThe LLM ran {runs} time{'' if runs == 1 else 's'} for {len(subjects)} "
        "tickets: only for the unsure ones."
    )


async def main_dashboard() -> None:
    async def feed():
        await asyncio.sleep(5)
        for ticket in TICKETS:
            await flock.publish(ticket)
            await asyncio.sleep(3)

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
