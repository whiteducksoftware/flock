"""Example 13.01: run a Flock application from a plain worker.

Shows the transport-independent execution API without any web framework or
Azure dependency:

- one isolated workflow per job (``WorkflowContext.workflow_id``)
- public outputs streamed as they are published (artifact-level, not tokens)
- an explicit terminal result that must be checked
- concurrent jobs of different principals running independently

Run:
    uv run python examples/13-applications/01_worker.py
"""

from __future__ import annotations

import asyncio

from incident_app import IncidentRequest, IncidentSummary, application

from flock import WorkflowContext


async def handle_job(job_id: str, principal: str, report: str) -> None:
    context = WorkflowContext(
        workflow_id=job_id,
        principal_id=principal,  # resolved by the trusted worker, never by the payload
    )
    async with application.stream(
        IncidentRequest(report=report), context=context, timeout=60
    ) as workflow:
        async for event in workflow:
            print(f"[{job_id}] output #{event.sequence}: {event.value}")
        result = await workflow.result()

    print(f"[{job_id}] {result.status} diagnostics={dict(result.diagnostics)}")
    result.raise_for_status()
    print(f"[{job_id}] summary: {result.values(IncidentSummary)[0].summary}")


async def main() -> None:
    async with application:  # validates the contract, drains on exit
        await asyncio.gather(
            handle_job("job-1", "customer-a", "Checkout requests are timing out."),
            handle_job("job-2", "customer-b", "The logo looks slightly off."),
        )


if __name__ == "__main__":
    asyncio.run(main())
