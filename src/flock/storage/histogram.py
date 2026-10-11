"""Artifacts per time bucket, for the dashboard's activity histogram.

The range from ``start`` to ``end`` is split into ``buckets`` equal buckets;
an artifact created exactly at ``end`` counts in the last one. Workflow errors
are counted a second time, on their own, so the timeline can mark them.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from flock.core.artifacts import Artifact
from flock.utils.time_utils import as_utc


def workflow_error_type() -> str:
    """The registered type name of ``WorkflowError``."""
    from flock.models.system_artifacts import WorkflowError
    from flock.registry import type_registry

    return type_registry.name_for(WorkflowError)


def bucket_of(
    created_at: datetime, start: datetime, end: datetime, buckets: int
) -> int | None:
    """The bucket an instant falls into, or None outside the range."""
    created_at, start, end = as_utc(created_at), as_utc(start), as_utc(end)
    if created_at < start or created_at > end:
        return None
    width = (end - start).total_seconds() / buckets
    return min(int((created_at - start).total_seconds() // width), buckets - 1)


def bucket_artifacts(
    artifacts: Iterable[Artifact], start: datetime, end: datetime, buckets: int
) -> tuple[list[int], list[int]]:
    """Artifacts and workflow errors per bucket."""
    counts = [0] * buckets
    errors = [0] * buckets
    error_type = workflow_error_type()
    for artifact in artifacts:
        index = bucket_of(artifact.created_at, start, end, buckets)
        if index is None:
            continue
        counts[index] += 1
        if artifact.type == error_type:
            errors[index] += 1
    return counts, errors


__all__ = ["bucket_artifacts", "bucket_of", "workflow_error_type"]
