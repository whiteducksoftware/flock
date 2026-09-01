"""Instance A — the writer.

Three agents turn a ``BandConcept`` into a ``BandLineup``, an ``Album`` and
``MarketingCopy``. Every artifact lands in the Dapr state store, so this
process can be killed and restarted without losing the blackboard.

    export DAPR_GRPC_ENDPOINT=localhost:50001
    uv run python examples/12-dapr/demos/writer.py            # dashboard on :8344
    uv run python examples/12-dapr/demos/writer.py --port 8346
"""

from __future__ import annotations

import argparse
import asyncio

from _common import (
    Album,
    BandConcept,
    BandLineup,
    MarketingCopy,
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
        store=make_store(secrets["state_store_name"]),  # the only Dapr-specific line
    )

    flock.agent("talent_scout").description(
        "A legendary talent scout who assembles perfect band lineups"
    ).consumes(BandConcept).publishes(BandLineup, visibility=PublicVisibility())

    flock.agent("music_producer").description(
        "A visionary music producer who creates debut album concepts"
    ).consumes(BandLineup).publishes(Album, visibility=PublicVisibility())

    flock.agent("marketing_guru").description(
        "A marketing genius who writes compelling promotional material"
    ).consumes(Album).publishes(MarketingCopy, visibility=PublicVisibility())

    await flock.serve(dashboard=True, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flock writer instance on a Dapr-backed blackboard"
    )
    parser.add_argument("--port", type=int, default=8344)
    asyncio.run(main(parser.parse_args().port))
