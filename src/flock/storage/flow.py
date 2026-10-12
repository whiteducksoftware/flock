"""What flowed where on the blackboard, counted over a filter range.

The dashboard's Agent View shows how many artifacts each agent published and
consumed, the edges between agents, the deciders' decision bars, the sinks'
receipts, the unsure decisions that wait for a person and the coverage groups.
Its graph reads only the newest artifacts of the range, but these counts cover
all of it (#640). The in-memory and Dapr stores count in one pass over the
range, the SQLite store in SQL; both fill a :class:`FlowCounts`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from flock.decisions.graph import (
    DecisionTally,
    decision_label,
    is_coverage_type,
    is_decision_type,
    needs_review,
)


if TYPE_CHECKING:
    from flock.core.artifacts import Artifact
    from flock.core.store import ArtifactEnvelope


@dataclass
class FlowCounts:
    """Counts of a filter range, keyed by who published what."""

    # (producer, type) -> artifacts
    produced: dict[tuple[str, str], int] = field(default_factory=dict)
    # (producer, consumer, type, decision label or None) -> [artifacts, newest]
    consumed: dict[tuple[str, str, str, str | None], list[Any]] = field(
        default_factory=dict
    )
    # (producer, decision type) -> what its decisions added up to
    decisions: dict[tuple[str, str], DecisionTally] = field(default_factory=dict)
    # producer -> ids of its unsure decisions, which wait for a person
    unsure: dict[str, set[str]] = field(default_factory=dict)
    # ids of the decisions a person reviewed
    reviewed: set[str] = field(default_factory=set)
    # (producer, coverage type, group) -> (revision, published, choice) of its
    # newest revision
    coverages: dict[tuple[str, str, str], tuple[Any, datetime, Any]] = field(
        default_factory=dict
    )
    # Type -> when its first unsure decision or coverage in the range was
    # published: their reviews and newer revisions count also from outside
    # the range, from then on
    follow_ups: dict[str, datetime] = field(default_factory=dict)
    # type -> "decision", "coverage" or None, looked up once per type
    _kinds: dict[str, str | None] = field(default_factory=dict, repr=False)

    def kind(self, type_name: str) -> str | None:
        """Whether ``type_name`` is a decision, a coverage or neither."""
        if type_name not in self._kinds:
            self._kinds[type_name] = (
                "decision"
                if is_decision_type(type_name)
                else "coverage"
                if is_coverage_type(type_name)
                else None
            )
        return self._kinds[type_name]

    def produce(self, producer: str, type_name: str, count: int = 1) -> None:
        key = (producer, type_name)
        self.produced[key] = self.produced.get(key, 0) + count

    def consume(
        self,
        producer: str,
        consumer: str,
        type_name: str,
        label: str | None,
        at: datetime,
        count: int = 1,
    ) -> None:
        """``count`` artifacts of ``type_name`` went from ``producer`` to
        ``consumer``, the newest at ``at``; ``label`` is a decision's option."""
        key = (producer, consumer, type_name, label)
        entry = self.consumed.get(key)
        if entry is None:
            self.consumed[key] = [count, at]
        else:
            entry[0] += count
            entry[1] = max(entry[1], at)

    def tally(self, producer: str, type_name: str) -> DecisionTally:
        """The tally of ``producer``'s decisions of ``type_name``."""
        key = (producer, type_name)
        tally = self.decisions.get(key)
        if tally is None:
            tally = self.decisions[key] = DecisionTally()
        return tally

    def wait(
        self, artifact_id: object, producer: str, type_name: str, at: datetime
    ) -> None:
        """An unsure decision, published at ``at``, waits for a person."""
        self.unsure.setdefault(producer, set()).add(str(artifact_id))
        self._follow_up(type_name, at)

    def decide(
        self,
        artifact_id: object,
        producer: str,
        type_name: str,
        payload: Mapping[str, Any],
        at: datetime,
    ) -> None:
        """Count a decision published at ``at``: its tally, whether it waits
        for a person, and which decision it reviews."""
        self.tally(producer, type_name).add(payload)
        if needs_review(payload):
            self.wait(artifact_id, producer, type_name, at)
        if payload.get("review_of"):
            self.reviewed.add(str(payload["review_of"]))

    def cover(
        self, producer: str, type_name: str, payload: Mapping[str, Any], at: datetime
    ) -> None:
        """Keep a coverage published at ``at`` if it is its group's newest
        revision so far: the highest, the later of two alike. Coverages may
        come in any order."""
        self._follow_up(type_name, at)
        key = (producer, type_name, str(payload.get("group")))
        revision = payload.get("revision", 0)
        current = self.coverages.get(key)
        if current is None or (revision, at) >= current[:2]:
            self.coverages[key] = (revision, at, payload.get("choice"))

    def _follow_up(self, type_name: str, at: datetime) -> None:
        if type_name not in self.follow_ups or at < self.follow_ups[type_name]:
            self.follow_ups[type_name] = at

    def add(self, artifact: Artifact, consumers: Iterable[str]) -> None:
        """Count one artifact and the agents that consumed it."""
        producer = artifact.produced_by or "external"
        type_name = artifact.type
        key = (producer, type_name)
        self.produced[key] = self.produced.get(key, 0) + 1
        kind = self.kind(type_name)
        if consumers:
            label = decision_label(artifact.payload) if kind == "decision" else None
            for consumer in consumers:
                self.consume(producer, consumer, type_name, label, artifact.created_at)
        if kind == "decision":
            self.decide(
                artifact.id,
                producer,
                type_name,
                artifact.payload,
                artifact.created_at,
            )
        elif kind == "coverage":
            self.cover(producer, type_name, artifact.payload, artifact.created_at)


def count_flow(envelopes: Iterable[ArtifactEnvelope]) -> FlowCounts:
    """The counts of ``envelopes``, in any order, with their consumptions."""
    flow = FlowCounts()
    for envelope in envelopes:
        flow.add(envelope.artifact, {r.consumer for r in envelope.consumptions})
    return flow


__all__ = ["FlowCounts", "count_flow"]
