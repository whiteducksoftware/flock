"""Public contracts of the workflow execution API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from pydantic import BaseModel


if TYPE_CHECKING:
    from flock.core.artifacts import Artifact
    from flock.core.conditions import RunCondition


ModelT = TypeVar("ModelT", bound=BaseModel)

_MAX_ID_LENGTH = 256


def _validate_id(value: str | None, name: str, *, required: bool) -> None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > _MAX_ID_LENGTH or any(ch in value for ch in "\r\n\x00"):
        raise ValueError(
            f"{name} must be at most {_MAX_ID_LENGTH} printable characters"
        )


@dataclass(frozen=True, slots=True)
class WorkflowContext:
    """Trusted identity of one workflow execution, resolved by the host.

    Attributes:
        workflow_id: Unique id of this execution (one turn / job). It becomes
            the Flock correlation id of the workflow. Not an agent task id.
        principal_id: Trusted partition key of the caller (tenant, user, ...).
            Never taken from untrusted request data by the host.
        session_id: Optional continuity key across workflows (conversation).
            Never substitutes for ``workflow_id``.
        attributes: Opaque host metadata (for example platform call ids),
            passed to the factory unchanged.
    """

    workflow_id: str
    principal_id: str | None = None
    session_id: str | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_id(self.workflow_id, "workflow_id", required=True)
        _validate_id(self.principal_id, "principal_id", required=False)
        _validate_id(self.session_id, "session_id", required=False)
        frozen = MappingProxyType({str(k): str(v) for k, v in self.attributes.items()})
        object.__setattr__(self, "attributes", frozen)


class WorkflowStatus(StrEnum):
    """Terminal status of a workflow."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class FailureCode(StrEnum):
    """Why a workflow failed. Safe to expose to callers."""

    AGENT_FAILED = "agent_failed"
    INTERNAL_ERROR = "internal_error"
    REQUIRED_OUTPUT_MISSING = "required_output_missing"
    CONDITION_NOT_MET = "condition_not_met"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    ITERATION_LIMIT_EXCEEDED = "iteration_limit_exceeded"
    TIMER_FAILED = "timer_failed"
    FACTORY_ERROR = "factory_error"


_FAILURE_MESSAGES: dict[FailureCode, str] = {
    FailureCode.AGENT_FAILED: "An agent failed while processing the workflow.",
    FailureCode.INTERNAL_ERROR: "The workflow failed because of an internal error.",
    FailureCode.REQUIRED_OUTPUT_MISSING: "The workflow finished without a required output.",
    FailureCode.CONDITION_NOT_MET: "The workflow finished before its completion condition was met.",
    FailureCode.OUTPUT_LIMIT_EXCEEDED: "The workflow produced more outputs than allowed.",
    FailureCode.ITERATION_LIMIT_EXCEEDED: "An agent reached its iteration limit; the cascade was cut short.",
    FailureCode.TIMER_FAILED: "A scheduled agent's timer failed.",
    FailureCode.FACTORY_ERROR: "The workflow could not be set up.",
}


@dataclass(frozen=True, slots=True)
class WorkflowFailure:
    """Failure summary with fixed, safe text (never raw exception text)."""

    code: FailureCode
    agent: str | None = None
    message: str = ""

    @classmethod
    def of(cls, code: FailureCode, agent: str | None = None) -> WorkflowFailure:
        return cls(code=code, agent=agent, message=_FAILURE_MESSAGES[code])


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    """One public output of a workflow, in publication order."""

    sequence: int
    artifact: Artifact
    value: BaseModel
    kind: Literal["output"] = "output"


class WorkflowFailedError(RuntimeError):
    """Raised by :meth:`WorkflowResult.raise_for_status` for non-success outcomes."""

    def __init__(self, result: WorkflowResult) -> None:
        detail = f": {result.failure.code}" if result.failure else ""
        super().__init__(f"Workflow {result.workflow_id} {result.status}{detail}")
        self.result = result


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Unambiguous terminal outcome of one workflow."""

    workflow_id: str
    status: WorkflowStatus
    outputs: tuple[WorkflowEvent, ...] = ()
    failure: WorkflowFailure | None = None
    condition_met: bool | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status is WorkflowStatus.SUCCEEDED

    def values(self, model: type[ModelT]) -> list[ModelT]:
        """Output values of one type, in publication order."""
        return [event.value for event in self.outputs if isinstance(event.value, model)]  # type: ignore[misc]

    def raise_for_status(self) -> None:
        """Raise :class:`WorkflowFailedError` unless the workflow succeeded."""
        if not self.ok:
            raise WorkflowFailedError(self)


AccessPolicy = Callable[["Artifact", WorkflowContext], bool]


@dataclass(frozen=True)
class OutputContract:
    """What a workflow accepts and what it may expose.

    Public outputs are never inferred from the agent graph: only
    ``output_types`` produced by the application's own agents and allowed by
    ``access_policy`` are returned. The default policy exposes an artifact
    when its visibility admits the caller, represented as
    ``AgentIdentity(name="__caller__", tenant_id=principal_id)`` - public and
    matching-tenant artifacts, never agent-private ones.
    """

    input_type: type[BaseModel]
    output_types: tuple[type[BaseModel], ...]
    required_output_types: tuple[type[BaseModel], ...] = ()
    access_policy: AccessPolicy | None = None

    def __post_init__(self) -> None:
        if not self.output_types:
            raise ValueError("output_types must name at least one public output type")
        missing = set(self.required_output_types) - set(self.output_types)
        if missing:
            names = ", ".join(sorted(model.__name__ for model in missing))
            raise ValueError(f"required_output_types must be output_types: {names}")


@dataclass(frozen=True)
class CompletionPolicy:
    """When a workflow is done.

    Attributes:
        until: Optional result condition. It is bound to the workflow's
            correlation id automatically; ``Until.idle()`` is rejected.
        on_condition: ``"stop"`` cancels remaining work once ``until`` holds;
            ``"drain"`` lets the cascade finish first.
        on_error: ``"stop"`` ends the workflow at the first agent failure;
            ``"continue"`` lets other branches finish. Either way the result
            is ``failed``.
    """

    until: RunCondition | None = None
    on_condition: Literal["stop", "drain"] = "stop"
    on_error: Literal["stop", "continue"] = "stop"


HistoryMode = Literal["stateless", "conversation"]


__all__ = [
    "AccessPolicy",
    "CompletionPolicy",
    "FailureCode",
    "HistoryMode",
    "OutputContract",
    "WorkflowContext",
    "WorkflowEvent",
    "WorkflowFailedError",
    "WorkflowFailure",
    "WorkflowResult",
    "WorkflowStatus",
]
