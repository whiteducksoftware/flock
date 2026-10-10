"""
Decision Models: Ticket Triage with Typed Choices

A decision model reads a state plus a question and returns a calibrated
probability for every option of a closed set. It generates no text, so it is
much cheaper and faster than an LLM call for routing.

This example routes support tickets:

- `triage` decides a `Route` for every `SupportTicket` with a decision model.
- `billing_team` and `tech_support` subscribe to one option each and receive the
  ticket itself (their LLM signature is `SupportTicket -> ...`).
- `supervisor` subscribes to `Route.UNSURE` and gets every ticket the decision
  model was not sure about (top probability below the threshold).

🎯 Key Concepts:
- `Choice` types: options as attributes, the docstring is the question
- `.decides(Route, model=..., threshold=...)` on the deciding agent
- `.consumes(Route.billing)` / `.consumes(Route.UNSURE)` on downstream agents
- `ctx.decision` carries the decision for custom engines

🎛️  CONFIGURATION:
- DECISION_MODEL below, or DEFAULT_DECISION_MODEL in your environment:
  - "azure/decision-1" (default): Microsoft-Decision-1 on Azure AI Foundry
    (AZURE_API_BASE, AZURE_API_KEY)
  - "openai/gpt-6-luna": OpenAI Decisions (OPENAI_API_KEY)
  - "jev/jev-latest": TypeSafe Jev (JEV_API_KEY)
  - "local/clef-flash": a local systemone server, e.g.
        llama serve -m Clef-Flash-Q8_0.gguf -b 4096 -ub 4096 -ngl 99
    (DECISION_API_BASE, default http://127.0.0.1:8080)
- DEFAULT_MODEL: the LLM the team agents use to write their replies
"""

import asyncio
import os

from pydantic import BaseModel, Field

from flock import Choice, Decision, Flock
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
    """A customer support ticket that needs routing."""

    subject: str
    message: str = Field(description="The customer's issue or question")


@flock_type
class TeamReply(BaseModel):
    """A team's answer to the customer."""

    team: str
    reply: str = Field(description="Short, friendly answer to the customer")


class Route(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds, payment problems"
    shipping = "Delivery, tracking, returns"
    tech = "Bugs, crashes, login problems"


flock = Flock()

triage = (
    flock.agent("triage")
    .description("Routes support tickets to a team")
    .consumes(SupportTicket)
    .decides(Route, model=DECISION_MODEL, threshold=THRESHOLD)
)

billing_team = (
    flock.agent("billing_team")
    .description("Answers billing questions as the billing team")
    .consumes(Route.billing)
    .publishes(TeamReply)
)

shipping_team = (
    flock.agent("shipping_team")
    .description("Answers delivery questions as the shipping team")
    .consumes(Route.shipping)
    .publishes(TeamReply)
)

tech_support = (
    flock.agent("tech_support")
    .description("Answers technical problems as tech support")
    .consumes(Route.tech)
    .publishes(TeamReply)
)

supervisor = (
    flock.agent("supervisor")
    .description(
        "Handles tickets the router was unsure about: answer as a supervisor "
        "and say which team will follow up"
    )
    .consumes(Route.UNSURE)
    .publishes(TeamReply)
)


TICKETS = [
    SupportTicket(subject="Charged twice", message="My card was charged twice."),
    SupportTicket(
        subject="Parcel missing", message="Tracking hasn't moved in 10 days."
    ),
    SupportTicket(subject="App crash", message="The app crashes when I open settings."),
    SupportTicket(
        subject="Refund for broken item",
        message="The blender arrived broken and the app won't let me file a return.",
    ),
]


async def main_cli():
    print(f"\n⚖️  Decision triage with {DECISION_MODEL} (threshold {THRESHOLD})\n")
    for ticket in TICKETS:
        await flock.publish(ticket)
    await flock.run_until_idle()

    decisions = [
        Decision.of(Route)(**a.payload)
        for a in await flock.store.list()
        if a.type == type_registry.name_for(Decision.of(Route))
    ]
    tickets = {
        str(a.id): a.payload["subject"]
        for a in await flock.store.list()
        if a.type == type_registry.name_for(SupportTicket)
    }
    print("\n" + "=" * 72)
    for decision in decisions:
        subject = tickets[decision.subject_ids[0]]
        bars = "  ".join(
            f"{option} {p:.2f}"
            for option, p in sorted(
                decision.probabilities.items(), key=lambda kv: -kv[1]
            )
        )
        print(
            f"{subject:<24} → {decision.choice:<8} [{bars}]  {decision.latency_ms:.0f} ms"
        )


async def main_dashboard():
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
