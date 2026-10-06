"""Example 13.02: expose a Flock application from your own ASGI service.

A minimal Starlette app with one endpoint that streams public outputs as
Server-Sent Events and ends with the terminal status. Flock's own server
(``flock.serve()``) is not involved and no second server is started.

Run:
    uv run python examples/13-applications/02_starlette_sse.py
    curl -N localhost:8000/incidents -H 'content-type: application/json' \
         -H 'x-tenant: customer-a' -d '{"report": "Checkout requests are timing out."}'

The tenant header stands in for your real authentication: resolve the
principal from a verified identity, never from an unauthenticated header.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager

from incident_app import application
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from flock import WorkflowContext
from flock.application import CapacityExceeded, InvalidWorkflowInput, WorkflowRejected


async def incidents(request: Request):
    context = WorkflowContext(
        workflow_id=f"req-{uuid.uuid4()}",
        principal_id=request.headers.get("x-tenant", "anonymous"),
    )
    try:
        payload = await request.json()
        stream = application.stream(payload, context=context, timeout=60)
        workflow = await stream.__aenter__()  # admission errors surface here
    except InvalidWorkflowInput as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except CapacityExceeded:
        return JSONResponse({"error": "busy"}, status_code=429)
    except WorkflowRejected as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    async def events():
        try:
            async for event in workflow:
                data = json.dumps({
                    "type": event.artifact.type,
                    "value": event.value.model_dump(),
                })
                yield f"event: output\ndata: {data}\n\n"
            result = await workflow.result()
            code = result.failure.code.value if result.failure else None
            yield f"event: done\ndata: {json.dumps({'status': result.status.value, 'failure': code})}\n\n"
        finally:
            # A disconnected client closes this generator: the workflow is cancelled
            # and torn down instead of running on unobserved.
            await stream.__aexit__(None, None, None)

    async def close() -> None:
        # Also runs when the body was never iterated; __aexit__ is idempotent.
        await stream.__aexit__(None, None, None)

    return StreamingResponse(
        events(), media_type="text/event-stream", background=BackgroundTask(close)
    )


@asynccontextmanager
async def lifespan(_app):
    async with application:
        yield


app = Starlette(
    routes=[Route("/incidents", incidents, methods=["POST"])], lifespan=lifespan
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
