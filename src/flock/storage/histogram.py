"""Artifacts per time bucket, for the dashboard's activity histogram.

The range from ``start`` to ``end`` is split into ``buckets`` equal buckets;
an artifact on an edge counts in the later bucket, and one created exactly at
``end`` in the last. Buckets are computed in whole microseconds, as the SQLite
store does in SQL, so every store puts an artifact in the same bucket. Workflow
errors and failed sink deliveries are counted a second time, on their own, so
the timeline can mark them.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from flock.core.artifacts import Artifact
from flock.registry import type_registry
from flock.utils.time_utils import as_utc
from flock.utils.type_resolution import TypeResolutionHelper


EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MICROSECOND = timedelta(microseconds=1)
# SQLite computes an offset in microseconds times the buckets in 64 bits
_MAX_PRODUCT = 2**63 - 1


def too_wide(start: datetime, end: datetime, buckets: int) -> bool:
    """Whether the range is too wide for exact buckets (about 584 years over
    500 buckets)."""
    return (as_utc(end) - as_utc(start)) // MICROSECOND * buckets > _MAX_PRODUCT


def error_types() -> tuple[str, ...]:
    """The registered type names of ``WorkflowError`` and ``DeliveryFailed``."""
    from flock.models.system_artifacts import WorkflowError
    from flock.sinks.models import DeliveryFailed

    return (
        type_registry.name_for(WorkflowError),
        type_registry.name_for(DeliveryFailed),
    )


def bucket_of(
    created_at: datetime, start: datetime, end: datetime, buckets: int
) -> int | None:
    """The bucket an instant falls into, or None outside the range."""
    created_at, start, end = as_utc(created_at), as_utc(start), as_utc(end)
    if created_at < start or created_at > end:
        return None
    offset = (created_at - start) // MICROSECOND
    span = (end - start) // MICROSECOND
    return min(offset * buckets // span, buckets - 1)


def bucket_artifacts(
    artifacts: Iterable[Artifact], start: datetime, end: datetime, buckets: int
) -> tuple[list[int], list[int]]:
    """Artifacts and errors per bucket."""
    counts = [0] * buckets
    errors = [0] * buckets
    errors_of = error_types()
    for artifact in artifacts:
        index = bucket_of(artifact.created_at, start, end, buckets)
        if index is None:
            continue
        counts[index] += 1
        # Resolved like the SQLite store's canonical_type
        resolved = TypeResolutionHelper.safe_resolve(type_registry, artifact.type)
        if resolved in errors_of:
            errors[index] += 1
    return counts, errors


__all__ = [
    "EPOCH",
    "MICROSECOND",
    "bucket_artifacts",
    "bucket_of",
    "error_types",
    "too_wide",
]
