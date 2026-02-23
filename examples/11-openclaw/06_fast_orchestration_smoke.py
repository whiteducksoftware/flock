"""
OpenClaw Integration: Fast Orchestration Smoke (Headless, Stream ON/OFF)

A compact alternative to 05_competitive_intelligence.py that still exercises
important orchestration behaviors fixed recently:

- OpenClaw fan-out materialization with unique artifact identities
- datetime-safe OpenClaw prompt shaping (input + context paths)
- headless streaming toggle (`--stream on|off`)
- mixed OpenClaw + native pipeline orchestration

🔧 SETUP:
    1) Enable gateway.http.endpoints.responses.enabled=true in OpenClaw config
    2) export OPENCLAW_CODEX_URL=http://localhost:19789
    3) export OPENCLAW_CODEX_TOKEN=your-token

Run (stream OFF):
    uv run python examples/11-openclaw/06_fast_orchestration_smoke.py --stream off

Run (stream ON):
    uv run python examples/11-openclaw/06_fast_orchestration_smoke.py --stream on

If your alias is not `codex`, pass `--alias <your-alias>`.
"""

import argparse
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock, OpenClawConfig
from flock.core.conditions import When
from flock.core.subscription import BatchSpec
from flock.models.system_artifacts import WorkflowError
from flock.registry import flock_type, type_registry


@flock_type
class FastBrief(BaseModel):
    """Small input brief with datetime to exercise JSON-safe input shaping."""

    product_name: str = Field(default="Flock", description="Product under analysis")
    positioning: str = Field(
        default="Typed blackboard orchestration for production multi-agent systems",
        description="Short positioning statement",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp used to exercise datetime-safe payload shaping",
    )


@flock_type
class MiniCompetitor(BaseModel):
    """Fan-out output from OpenClaw scout."""

    competitor_name: str = Field(description="Competitor name")
    one_liner: str = Field(description="One-line competitor summary")


@flock_type
class CompetitorSignal(BaseModel):
    """Native enrichment that injects datetime for downstream OpenClaw context/input."""

    competitor_name: str = Field(description="Competitor name")
    risk_level: str = Field(description="low|medium|high")
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Datetime field to exercise OpenClaw serialization safety",
    )


@flock_type
class QuickLandscape(BaseModel):
    """Batched OpenClaw synthesis output."""

    summary: str = Field(description="Two-sentence summary")
    competitor_names: list[str] = Field(description="Competitors included in synthesis")


@flock_type
class QuickReport(BaseModel):
    """Final compact report."""

    headline: str = Field(description="Short report headline")
    key_points: list[str] = Field(description="Top actionable points")


def build_flock(*, alias: str, stream_enabled: bool) -> tuple[Flock, tuple]:
    flock = Flock(openclaw=OpenClawConfig.from_env())

    scout = (
        flock.openclaw_agent(alias, name="fast_scout")
        .description(
            "Return exactly 2 direct competitors as compact JSON objects. "
            "Do not browse; use known market context from prompt and keep concise."
        )
        .consumes(FastBrief)
        .publishes(MiniCompetitor, fan_out=2)
    )

    signaler = (
        flock.agent("fast_signaler")
        .description(
            "For each competitor, assign risk_level (low/medium/high). "
            "Keep output terse and consistent."
        )
        .consumes(MiniCompetitor)
        .publishes(CompetitorSignal)
    )

    synthesizer = (
        flock.openclaw_agent(alias, name="fast_synthesizer")
        .description(
            "Given a batch of competitor signals, produce one compact landscape summary."
        )
        .consumes(
            CompetitorSignal,
            batch=BatchSpec(size=2, timeout=timedelta(seconds=20)),
        )
        .publishes(QuickLandscape)
    )

    reporter = (
        flock.openclaw_agent(alias, name="fast_reporter")
        .description("Produce a concise report with headline + 3-5 key points.")
        .consumes(
            QuickLandscape,
            activation=When.correlation(QuickLandscape).exists(),
        )
        .publishes(QuickReport)
    )

    # Explicit stream toggle for all OpenClaw agents in this example.
    for builder in (scout, synthesizer, reporter):
        builder.agent.engines[0].stream = stream_enabled

    return flock, (scout, signaler, synthesizer, reporter)


async def run(*, alias: str, stream_enabled: bool) -> None:
    flock, _builders = build_flock(alias=alias, stream_enabled=stream_enabled)
    correlation_id = str(uuid.uuid4())

    brief = FastBrief()

    print("=" * 72)
    print("⚡ OpenClaw Fast Orchestration Smoke")
    print("=" * 72)
    print(f"Alias: {alias}")
    print(f"Streaming: {'ON' if stream_enabled else 'OFF'}")
    print(f"Correlation ID: {correlation_id[:8]}...")
    print()

    await flock.publish(brief, correlation_id=correlation_id)
    await flock.run_until_idle()

    # Typed outputs
    reports = await flock.store.get_by_type(QuickReport, correlation_id=correlation_id)
    landscapes = await flock.store.get_by_type(
        QuickLandscape, correlation_id=correlation_id
    )

    # Raw artifacts for identity checks
    all_artifacts = await flock.store.list()
    mini_competitor_type = type_registry.name_for(MiniCompetitor)
    fan_out_artifacts = [
        artifact
        for artifact in all_artifacts
        if artifact.type == mini_competitor_type
        and str(artifact.correlation_id) == correlation_id
    ]

    unique_ids = {str(artifact.id) for artifact in fan_out_artifacts}

    workflow_error_type = type_registry.name_for(WorkflowError)
    workflow_errors = [
        artifact
        for artifact in all_artifacts
        if artifact.type == workflow_error_type
        and str(artifact.correlation_id) == correlation_id
    ]

    print("Summary")
    print(f"  Fan-out artifacts: {len(fan_out_artifacts)}")
    print(f"  Unique fan-out IDs: {len(unique_ids)}")
    print(f"  Landscapes: {len(landscapes)}")
    print(f"  Reports: {len(reports)}")
    print(f"  WorkflowError artifacts: {len(workflow_errors)}")

    if reports:
        report = reports[-1]
        print()
        print(f"Report: {report.headline}")
        for point in report.key_points[:3]:
            print(f"  - {point}")

    # Assertions make this script useful as a fast behavior smoke test.
    assert len(fan_out_artifacts) == 2, "Expected exactly 2 fan-out artifacts"
    assert len(unique_ids) == 2, "Fan-out artifacts must have unique IDs"
    assert landscapes, "Expected at least one QuickLandscape artifact"
    assert reports, "Expected at least one QuickReport artifact"
    assert not workflow_errors, "Expected no WorkflowError artifacts"

    await flock.shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fast OpenClaw orchestration smoke (headless, stream on/off)"
    )
    parser.add_argument(
        "--stream",
        choices=["on", "off"],
        default="off",
        help="Enable or disable OpenClaw streaming in headless mode.",
    )
    parser.add_argument(
        "--alias",
        default="codex",
        help="OpenClaw gateway alias discovered from OPENCLAW_<ALIAS>_* env vars.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(alias=args.alias, stream_enabled=(args.stream == "on")))
