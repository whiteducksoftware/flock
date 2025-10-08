from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from flock.orchestrator import Flock
from flock.components import EngineComponent
from flock.runtime import EvalInputs, EvalResult
from flock.logging.telemetry import TelemetryConfig


class NoOpEngine(EngineComponent):
    """An Engine that forwards inputs to outputs without calling an LLM.

    This keeps boilerplate experiments runnable without API keys.
    If you want LLM-backed behavior, replace with DSPyEngine or your own Engine.
    """

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:  # type: ignore[override]
        return EvalResult(artifacts=inputs.artifacts, state=inputs.state)


def setup_tracing(db_dir: str = ".flock", db_name: str = "traces.duckdb") -> None:
    os.makedirs(db_dir, exist_ok=True)
    TelemetryConfig(
        service_name="flock-research",
        local_logging_dir=db_dir,
        duckdb_name=db_name,
        enable_duckdb=True,
        enable_otlp=False,
        enable_file=False,
        enable_sql=False,
        enable_jaeger=False,
    ).setup_tracing()


@dataclass
class ExperimentConfig:
    name: str
    runs: int = 10
    batch: int = 10

    @staticmethod
    def from_json(path: str) -> "ExperimentConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ExperimentConfig(
            name=data.get("name", "experiment"),
            runs=int(data.get("runs", 10)),
            batch=int(data.get("batch", 10)),
        )


import asyncio


async def _run_noop_batch_async(cfg: ExperimentConfig) -> None:
    """Minimal, deterministic batch run that exercises publish→run_until_idle pipeline.

    Defines two typed artifacts and a single NoOp engine agent that echoes input to output.
    """

    class ItemIn(BaseModel):
        text: str

    class ItemOut(BaseModel):
        text: str

    setup_tracing()
    flock = Flock(model=os.getenv("DEFAULT_MODEL"))

    agent = (
        flock.agent("noop")
        .consumes(ItemIn)
        .publishes(ItemOut)
        .with_engines(NoOpEngine())
    )

    # Publish in batches to demonstrate decoupled publish vs run.
    total = cfg.runs
    batch = max(1, cfg.batch)

    i = 0
    while i < total:
        # queue up batch
        for _ in range(min(batch, total - i)):
            i += 1
            flock_input = ItemIn(text=f"msg-{i}")
            await flock.publish(flock_input)

        # execute scheduled work for this batch
        await flock.run_until_idle()

    print(f"Completed noop experiment: {cfg.name} | runs={cfg.runs} batch={cfg.batch}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Flock research harness runner")
    parser.add_argument("--config", required=True, help="Path to experiment.json")
    args = parser.parse_args()
    cfg = ExperimentConfig.from_json(args.config)
    asyncio.run(_run_noop_batch_async(cfg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
