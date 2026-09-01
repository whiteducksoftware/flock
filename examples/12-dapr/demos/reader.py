"""Instance B — the reader (and critic).

A second Flock process on the *same* Dapr state store. It registers the same
artifact types, so everything the writer produced is visible here: REST,
dashboard, history. It also runs one agent of its own, ``critic``, which
turns ``MarketingCopy`` into a ``Review``.

    export DAPR_GRPC_ENDPOINT=localhost:50001
    uv run python examples/12-dapr/demos/reader.py            # dashboard on :8345

Note the boundary this demo makes visible: the critic reacts to artifacts
published *to this instance*. It does not wake up when the writer publishes
``MarketingCopy`` in its own process — shared state, not shared events. A Dapr
Pub/Sub bridge for cross-instance triggering is on the roadmap.
"""

from __future__ import annotations

import argparse
import asyncio

from _common import (
    MarketingCopy,
    Review,
    configure_model_env,
    load_secrets,
    make_store,
)

from flock import Flock, PublicVisibility
from flock.logging.logging import configure_logging


async def main(port: int) -> None:
    configure_logging("WARNING", external_level="ERROR")
    secrets = load_secrets()
    configure_model_env(secrets)

    flock = Flock(
        model=secrets["default_model"],
        max_agent_iterations=100,
        store=make_store(secrets["state_store_name"]),  # same store_name as the writer
    )

    flock.agent("critic").description(
        "A merciless music critic who has heard it all before"
    ).consumes(MarketingCopy).publishes(Review, visibility=PublicVisibility())

    await flock.serve(dashboard=True, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flock reader/critic instance on a Dapr-backed blackboard"
    )
    parser.add_argument("--port", type=int, default=8345)
    asyncio.run(main(parser.parse_args().port))
