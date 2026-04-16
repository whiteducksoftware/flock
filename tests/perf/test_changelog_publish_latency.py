"""Changelog publish latency benchmark (Unit 10).

Measures store-level ``publish(artifact, event)`` latency under load.
Marked ``@pytest.mark.perf`` so it does not run in the default test
suite. Invoke explicitly:

    uv run pytest tests/perf -m perf -s

A wide tolerance is asserted to catch order-of-magnitude regressions
without flaking on machine variance. The numbers themselves are the
deliverable — see docs/guides/changelog-stream.md for recorded results.

The smaller in-suite SC4 latency tests in
tests/integration/test_meta_orchestrator_e2e.py cover the SC4 success
criterion (< 5ms p99 in-memory, < 15ms p99 SQLite on WSL2 at N=200);
this benchmark scales to N=1000 with full p50/p95/p99/max reporting
for tracking trends across releases.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from pathlib import Path

import pytest

from flock.core.artifacts import Artifact
from flock.core.store import InMemoryBlackboardStore, SQLiteBlackboardStore
from flock.core.visibility import PublicVisibility
from flock.models.changelog import ChangelogEvent, ChangelogEventType


pytestmark = pytest.mark.perf


N_PUBLISHES = 1000
# SQLite on slow filesystems (WSL2, network FS) is dramatically slower than
# in-memory; smaller sample keeps the benchmark practical there.
N_PUBLISHES_SQLITE = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _summarise(samples_ms: list[float]) -> dict[str, float]:
    samples_sorted = sorted(samples_ms)
    return {
        "count": len(samples_ms),
        "mean_ms": round(statistics.fmean(samples_sorted), 3),
        "p50_ms": round(samples_sorted[len(samples_sorted) // 2], 3),
        "p95_ms": round(samples_sorted[int(len(samples_sorted) * 0.95)], 3),
        "p99_ms": round(samples_sorted[int(len(samples_sorted) * 0.99)], 3),
        "max_ms": round(samples_sorted[-1], 3),
    }


def _make_artifact(i: int) -> Artifact:
    return Artifact(
        type="BenchArtifact",
        payload={"i": i},
        produced_by="bench",
        visibility=PublicVisibility(),
    )


def _make_event(artifact: Artifact) -> ChangelogEvent:
    return ChangelogEvent(
        event_type=ChangelogEventType.artifact_published,
        artifact_id=artifact.id,
        artifact_type=artifact.type,
        produced_by=artifact.produced_by,
        correlation_id=artifact.correlation_id,
        visibility=artifact.visibility.model_dump(mode="json"),
        timestamp=artifact.created_at,
        payload_summary={"i": artifact.payload.get("i")},
    )


async def _measure(store, n: int) -> list[float]:
    samples_ms: list[float] = []
    for i in range(n):
        artifact = _make_artifact(i)
        event = _make_event(artifact)
        start = time.perf_counter()
        await store.publish(artifact, event)
        samples_ms.append((time.perf_counter() - start) * 1000.0)
    return samples_ms


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inmemory_publish_latency() -> None:
    store = InMemoryBlackboardStore()
    samples = await _measure(store, N_PUBLISHES)
    summary = _summarise(samples)

    print(f"\n[InMemory] {N_PUBLISHES} publishes: {summary}")

    # Wide tolerance — catches 10x regressions without flaking
    assert summary["p99_ms"] < 50.0, summary
    assert summary["mean_ms"] < 10.0, summary


@pytest.mark.asyncio
@pytest.mark.timeout(300)  # SQLite on slow disks is much slower than in-memory
async def test_sqlite_publish_latency(tmp_path: Path) -> None:
    store = SQLiteBlackboardStore(str(tmp_path / "perf.db"))
    await store.ensure_schema()
    try:
        samples = await _measure(store, N_PUBLISHES_SQLITE)
    finally:
        await store.close()

    summary = _summarise(samples)
    print(f"\n[SQLite]   {N_PUBLISHES_SQLITE} publishes: {summary}")

    # Tolerate up to 200ms p99 even on slow disks (WSL2 ext4-on-NTFS)
    assert summary["p99_ms"] < 200.0, summary


@pytest.mark.asyncio
async def test_concurrent_publish_seq_monotonicity() -> None:
    """Concurrent publishes via asyncio.gather must produce monotonic seq numbers.

    Verifies that the changelog event seq is strictly increasing even
    under contention — exercises the store's write-lock + auto-increment.
    """
    store = InMemoryBlackboardStore()

    n = 200

    async def one(i: int) -> None:
        artifact = _make_artifact(i)
        event = _make_event(artifact)
        await store.publish(artifact, event)

    await asyncio.gather(*[one(i) for i in range(n)])

    events_result = await store.query_changelog(after_seq=0, limit=n + 50)
    seqs = [e.seq for e in events_result.events]
    assert seqs == sorted(seqs), "Changelog seq numbers are not monotonic"
    assert len(seqs) == n, f"Expected {n} events, got {len(seqs)}"
