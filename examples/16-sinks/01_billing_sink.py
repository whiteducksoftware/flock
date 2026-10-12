"""
Sinks: Deliver Agent Results to External Systems

A sink is an external system as a consumer on the blackboard. It subscribes
like an agent and delivers what it consumes over HTTP, then publishes a
receipt: `Delivered` or `DeliveryFailed`. The workflow, the dashboard and the
trace all see what went out, where it went, and what came back.

This example runs without API keys. A small local server stands in for "myapp"
(a billing system with an audit log), and the support agent writes its replies
from a template instead of with an LLM:

- `support` answers every `Ticket` with a `Reply`; `publishes(..., post=...)`
  also sends every reply to myapp's audit log (the audit log is down for its
  first request: the sink retries).
- `billing-api` consumes the billing replies, posts them to myapp's billing
  API and publishes the API's answer as a `CrmRecord`.
- myapp rejects one reply (HTTP 400): its receipt is a `DeliveryFailed`.

🎯 Key Concepts:
- `Flock(endpoints={"myapp": Endpoint(url, auth=Bearer(env=...))})`: named
  systems with their secrets (named by environment variable, never stored)
- `flock.sink(name).consumes(...).post("myapp:/billing", response=...)`
- `.publishes(Reply, post="myapp:/audit")`: a sink for an agent's output
- `Delivered` / `DeliveryFailed` receipts; retries with an idempotency key

🎛️  CONFIGURATION:
- USE_DASHBOARD: True opens the dashboard; sinks show as nodes of their own
"""

import asyncio
import os

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from flock import Bearer, Delivered, DeliveryFailed, Endpoint, Flock, flock_type
from flock.components.agent import EngineComponent
from flock.utils.runtime import EvalResult


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
PORT = 8790
# ============================================================================

os.environ.setdefault("MYAPP_TOKEN", "demo-token")  # normally in your .env


@flock_type
class Ticket(BaseModel):
    customer: str
    team: str  # "billing" or "tech"
    text: str


@flock_type
class Reply(BaseModel):
    customer: str
    team: str
    text: str


@flock_type
class CrmRecord(BaseModel):
    """myapp's answer to a billing reply."""

    record_id: str
    customer: str


# ============================================================================
# myapp: a stand-in for the external system
# ============================================================================
myapp = FastAPI()
audit_requests = 0


@myapp.post("/audit")
async def audit(entry: dict, authorization: str = Header()):
    global audit_requests
    audit_requests += 1
    if audit_requests == 1:
        # Down for a moment: the sink retries after the advised wait
        return Response(status_code=503, headers={"Retry-After": "1"})
    return {"ok": True}


@myapp.post("/billing")
async def billing(entry: dict, authorization: str = Header()):
    if authorization != f"Bearer {os.environ['MYAPP_TOKEN']}":
        raise HTTPException(401)
    reply = entry["payload"]
    if reply["customer"] == "unknown":
        raise HTTPException(400, detail="no such customer")
    return {"record_id": f"CRM-{entry['id'][:8]}", "customer": reply["customer"]}


# ============================================================================
# The flock
# ============================================================================
class TemplateReply(EngineComponent):
    """Answers from a template (an LLM engine would write the text)."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        ticket = Ticket(**inputs.artifacts[0].payload)
        reply = Reply(
            customer=ticket.customer,
            team=ticket.team,
            text=f"Thanks {ticket.customer}, the {ticket.team} team is on it.",
        )
        return EvalResult.from_object(reply, agent=agent)


flock = Flock(
    endpoints={
        "myapp": Endpoint(
            f"http://127.0.0.1:{PORT}",
            auth=Bearer(env="MYAPP_TOKEN"),
            retries=3,
            rate_limit="100/min",
        )
    }
)

flock.agent("support").consumes(Ticket).with_engines(TemplateReply()).publishes(
    Reply, post="myapp:/audit"
)

flock.sink("billing-api").consumes(Reply, where=lambda r: r.team == "billing").post(
    "myapp:/billing", response=CrmRecord
)

TICKETS = [
    Ticket(customer="ada", team="billing", text="I was charged twice."),
    Ticket(customer="grace", team="tech", text="The app crashes on login."),
    Ticket(customer="unknown", team="billing", text="Refund please."),
]


async def start_myapp() -> tuple[uvicorn.Server, asyncio.Task]:
    server = uvicorn.Server(
        uvicorn.Config(myapp, host="127.0.0.1", port=PORT, log_level="warning")
    )
    serving = asyncio.get_running_loop().create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 - uvicorn offers only the flag
        await asyncio.sleep(0.05)
    return server, serving


async def main_cli():
    server, serving = await start_myapp()
    print(f"\n📮 Sinks delivering to myapp on port {PORT}\n")
    for ticket in TICKETS:
        await flock.publish(ticket)
    await flock.run_until_idle()

    artifacts = await flock.store.list()
    print("=" * 72)
    for artifact in artifacts:
        if artifact.type.endswith(".Delivered"):
            receipt = Delivered(**artifact.payload)
            print(
                f"✅ {receipt.sink:<24} {receipt.method} {receipt.target:<16} "
                f"HTTP {receipt.status}  {receipt.attempts} attempt(s)  "
                f"{receipt.latency_ms:.0f} ms"
            )
        elif artifact.type.endswith(".DeliveryFailed"):
            failed = DeliveryFailed(**artifact.payload)
            print(
                f"❌ {failed.sink:<24} {failed.method} {failed.target:<16} {failed.error}"
            )
        elif artifact.type.endswith(".CrmRecord"):
            print(f"📇 myapp answered: {CrmRecord(**artifact.payload)}")
    server.should_exit = True
    await serving


async def main_dashboard():
    await start_myapp()
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
