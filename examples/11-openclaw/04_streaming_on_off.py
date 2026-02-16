"""
OpenClaw Integration: Streaming ON/OFF (Dashboard vs Headless)

This example demonstrates the two runtime modes for OpenClaw responses in Flock:

- Headless mode (streaming OFF): normal `publish()` + `run_until_idle()` run.
- Dashboard mode (streaming ON): same pipeline, but with dashboard/WebSocket sink active.

No per-agent streaming flag is needed. Streaming is auto-detected from active sinks.

🔧 SETUP:
    1) Enable gateway.http.endpoints.responses.enabled=true in OpenClaw config
    2) export OPENCLAW_CODEX_URL=http://localhost:19789
    3) export OPENCLAW_CODEX_TOKEN=your-token

Run (streaming OFF):
    uv run python examples/11-openclaw/04_streaming_on_off.py --mode headless

Run (streaming ON):
    uv run python examples/11-openclaw/04_streaming_on_off.py --mode dashboard
"""

import argparse
import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from flock import Flock, OpenClawConfig
from flock.registry import flock_type


@flock_type
class Prompt(BaseModel):
    request: str = Field(description="User request for the OpenClaw agent")


@flock_type
class Result(BaseModel):
    answer: str = Field(description="Structured answer from the OpenClaw agent")


def build_flock() -> Flock:
    """Build Flock using environment-discovered OpenClaw gateway config."""
    return Flock(openclaw=OpenClawConfig.from_env())


async def run(mode: Literal["headless", "dashboard"]) -> None:
    flock = build_flock()

    (
        flock.openclaw_agent("codex")
        .description("Helpful assistant that returns concise JSON answers")
        .consumes(Prompt)
        .publishes(Result)
    )

    if mode == "dashboard":
        await flock.serve(dashboard=True, blocking=False)
        print("📊 Dashboard mode enabled — OpenClaw streaming turns ON automatically.")
        print("   Open: http://127.0.0.1:8344")
    else:
        print("🧪 Headless mode — OpenClaw runs in non-streaming request mode.")

    await flock.publish(
        Prompt(
            request="Explain in 2 short bullets why typed artifacts help pipeline reliability.",
        )
    )
    await flock.run_until_idle()

    outputs = await flock.store.get_by_type(Result)
    if outputs:
        print("\n✅ Result:")
        print(outputs[-1].answer)

    # Keep dashboard open briefly so token streaming can be observed.
    if mode == "dashboard":
        await asyncio.sleep(2)

    await flock.shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw streaming ON/OFF example")
    parser.add_argument(
        "--mode",
        choices=["headless", "dashboard"],
        default="headless",
        help="headless = non-streaming, dashboard = streaming via WebSocket sink",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(args.mode))
