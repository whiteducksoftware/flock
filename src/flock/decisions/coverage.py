"""Coverage: checklist results combined across the artifacts of a group.

A single document rarely shows every control of a catalog; the question is
whether a control is shown by *any* of an organisation's documents. An agent
subscribed to a checklist handle calls ``.aggregates(by=..., combine=...)`` and
publishes one :class:`Coverage` per group, updated as decisions arrive.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, create_model

from flock.components.agent import EngineComponent
from flock.core.artifacts import Artifact
from flock.core.visibility import Visibility
from flock.decisions.choice import FAILED, PASSED, UNSURE, Question
from flock.decisions.engine import inherited_visibility
from flock.decisions.models import Decision
from flock.registry import type_registry
from flock.utils.runtime import Context, EvalInputs, EvalResult


COMBINES = ("any", "all")


class Coverage(BaseModel):
    """Checklist results combined over the decided artifacts of one group.

    Each Checklist gets its own registered subclass (``Coverage.of(Controls)``)
    whose ``results`` only accept that checklist's items.
    """

    question: str = Field(default="", description="Name of the checklist")
    group: str = Field(description="The group the results were combined for")
    combine: str = Field(
        description="any: an item is yes if one artifact shows it; all: if every "
        "artifact does"
    )
    choice: str = Field(description=f"{PASSED}, {FAILED} or {UNSURE} over all items")
    results: dict[str, str] = Field(
        default_factory=dict, description="Combined answer per item"
    )
    evidence: dict[str, list[str]] = Field(
        default_factory=dict, description="Ids of the artifacts that showed each item"
    )
    subject_ids: list[str] = Field(
        default_factory=list, description="Ids of the artifacts in the group"
    )
    decision_ids: list[str] = Field(
        default_factory=list, description="Ids of the combined decisions"
    )
    revision: int = Field(
        default=0,
        description="How many decisions were combined; per group, the highest "
        "revision is the current coverage, whatever order coverages were stored in",
    )

    @classmethod
    def of(cls, checklist: type[Question]) -> type[Coverage]:
        """Return the registered Coverage model for a checklist (cached)."""
        if not (
            isinstance(checklist, type)
            and issubclass(checklist, Question)
            and checklist.__kind__ == "checklist"
        ):
            raise TypeError(
                f"Coverage.of() expects a Checklist subclass, got {checklist!r}"
            )
        cached = checklist.__dict__.get("__coverage_model__")
        if cached is not None:
            return cached
        items = tuple(checklist.__options__)
        model = create_model(
            f"{checklist.__name__}Coverage",
            __base__=Coverage,
            __module__=checklist.__module__,
            question=(str, Field(default=checklist.__name__)),
            choice=(Literal[PASSED, FAILED, UNSURE], Field(description="Outcome")),
            results=(
                dict[Literal[items], Literal["yes", "no", UNSURE]],
                Field(default_factory=dict, description="Combined answer per item"),
            ),
        )
        model.__flock_checklist__ = checklist
        type_registry.register(
            model, name=f"Coverage[{checklist.__module__}.{checklist.__qualname__}]"
        )
        checklist.__coverage_model__ = model
        return model


def combine_results(
    items: list[str], answers: list[dict[str, str]], combine: str
) -> dict[str, str]:
    """One answer per item from several artifacts' answers."""
    combined: dict[str, str] = {}
    for item in items:
        values = [answer.get(item, UNSURE) for answer in answers]
        if combine == "any":
            if "yes" in values:
                combined[item] = "yes"
            elif values and all(value == "no" for value in values):
                combined[item] = "no"
            else:
                combined[item] = UNSURE
        elif "no" in values:
            combined[item] = "no"
        elif values and all(value == "yes" for value in values):
            combined[item] = "yes"
        else:
            combined[item] = UNSURE
    return combined


def outcome(results: dict[str, str]) -> str:
    """The checklist outcome: failed on any no, unsure on any unsure."""
    if not results:
        return UNSURE
    if "no" in results.values():
        return FAILED
    if UNSURE in results.values():
        return UNSURE
    return PASSED


class _Entry(BaseModel):
    """One decision in a group."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subject_ids: list[str]
    results: dict[str, str]
    visibility: Visibility


class AggregateEngine(EngineComponent):
    """Combines a checklist's decisions per group into :class:`Coverage`.

    Every execution adds its decision to the group, merges the decisions in
    its context that its subscriptions would receive (with the default context
    provider all visible ones, so a restart with a persistent store loses
    nothing) and publishes the group's coverage. Groups are updated one at a
    time.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    question: Any = Field(description="The Checklist whose decisions are combined")
    by: str | Callable[[BaseModel], Any] = Field(
        description="Field of the decided artifact, or a function of it, that "
        "names its group"
    )
    combine: Literal["any", "all"] = "any"
    visibility: Visibility | None = Field(
        default=None,
        description="Readership of the coverage; by default the group's common "
        "visibility",
    )
    _groups: dict[str, dict[str, _Entry]] = PrivateAttr(default_factory=dict)
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def evaluate(
        self, agent: Any, ctx: Context, inputs: EvalInputs, output_group: Any
    ) -> EvalResult:
        decision_type = type_registry.name_for(Decision.of(self.question))
        triggering = [
            item
            for item in (ctx.state or {}).get("__decisions__") or []
            if item["type"] == decision_type
        ]
        if not triggering:
            return EvalResult(artifacts=[], state=dict(inputs.state))
        known = {str(a.id): a for a in [*ctx.artifacts, *inputs.artifacts]}

        async with self._lock:
            # History, e.g. after a restart: only decisions that reach this agent
            for artifact in ctx.artifacts:
                if artifact.type == decision_type and self._reaches(agent, artifact):
                    self._add(str(artifact.id), artifact.payload, known)
            groups = [
                self._add(item["id"], item["payload"], known) for item in triggering
            ]
            coverages = [self._coverage(group) for group in dict.fromkeys(groups)]

        model = Coverage.of(self.question)
        return EvalResult(
            artifacts=[
                Artifact(
                    type=type_registry.name_for(model),
                    payload=coverage.model_dump(mode="json"),
                    produced_by=agent.name,
                    visibility=visibility,
                )
                for coverage, visibility in coverages
            ],
            state=dict(inputs.state),
        )

    def _add(
        self, decision_id: str, payload: dict[str, Any], known: dict[str, Artifact]
    ) -> str:
        """Record a decision in its group; returns the group."""
        subjects = [
            known[sid] for sid in payload.get("subject_ids", []) if sid in known
        ]
        if not subjects:
            raise ValueError(
                f"Decision {decision_id} has no visible subject to group it by."
            )
        keys = {self._key(subject) for subject in subjects}
        if len(keys) != 1:
            raise ValueError(
                f"The subjects of decision {decision_id} belong to different "
                f"groups: {sorted(keys)}."
            )
        (group,) = keys
        self._groups.setdefault(group, {})[decision_id] = _Entry(
            subject_ids=[str(subject.id) for subject in subjects],
            results=dict(payload.get("results") or {}),
            visibility=inherited_visibility(subjects),
        )
        return group

    @staticmethod
    def _reaches(agent: Any, artifact: Artifact) -> bool:
        """Whether one of the agent's subscriptions matches the decision."""
        return any(
            subscription.accepts_events() and subscription.matches(artifact)
            for subscription in agent.subscriptions
        )

    def _key(self, subject: Artifact) -> str:
        if callable(self.by):
            model = type_registry.resolve(subject.type)
            # Stored payloads use field names, also for alias-only models
            return str(self.by(model.model_validate(subject.payload, by_name=True)))
        if self.by not in subject.payload:
            raise ValueError(
                f"Artifact {subject.type} has no field '{self.by}' to group by."
            )
        return str(subject.payload[self.by])

    def _coverage(self, group: str) -> tuple[Coverage, Visibility]:
        entries = self._groups[group]
        items = list(self.question.__options__)
        results = combine_results(
            items, [entry.results for entry in entries.values()], self.combine
        )
        evidence: dict[str, list[str]] = {}
        for entry in entries.values():
            for item, result in entry.results.items():
                if result == "yes":
                    evidence.setdefault(item, []).extend(entry.subject_ids)
        coverage = Coverage.of(self.question)(
            group=group,
            combine=self.combine,
            choice=outcome(results),
            results=results,
            evidence={item: evidence[item] for item in items if item in evidence},
            subject_ids=[
                sid for entry in entries.values() for sid in entry.subject_ids
            ],
            decision_ids=list(entries),
            revision=len(entries),
        )
        return coverage, self._readership(group, entries)

    def _readership(self, group: str, entries: dict[str, _Entry]) -> Visibility:
        if self.visibility is not None:
            return self.visibility.model_copy(deep=True)
        first, *rest = [entry.visibility for entry in entries.values()]
        reference = first.model_dump(mode="json")
        if any(v.model_dump(mode="json") != reference for v in rest):
            raise ValueError(
                f"The artifacts of group '{group}' carry different visibilities; "
                "pass visibility= to .aggregates() to choose the coverage's "
                "readership explicitly."
            )
        return first.model_copy(deep=True)


__all__ = ["COMBINES", "AggregateEngine", "Coverage", "combine_results", "outcome"]
