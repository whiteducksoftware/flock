"""Errors raised before a workflow is admitted.

Once a workflow is admitted, every outcome - including failures, timeouts and
cancellation - is returned as a :class:`~flock.application.WorkflowResult`
instead of being raised.
"""

from __future__ import annotations


class ContractError(ValueError):
    """The application's factory or contract is invalid (raised by ``start()``)."""


class WorkflowRejected(Exception):  # noqa: N818 - reads as an outcome
    """The workflow was not admitted; nothing was executed."""


class InvalidWorkflowInput(WorkflowRejected, ValueError):  # noqa: N818
    """The input does not match the contract's input type, or options are invalid."""


class WorkflowIdConflict(WorkflowRejected):
    """The workflow id is active or was used recently (retry protection)."""


class CapacityExceeded(WorkflowRejected):
    """The admission controller refused the workflow; retry later."""


class SessionRequired(WorkflowRejected):
    """Conversation history mode needs a ``session_id``."""


class ApplicationNotRunning(WorkflowRejected):
    """The application is not started or is draining for shutdown."""


__all__ = [
    "ApplicationNotRunning",
    "CapacityExceeded",
    "ContractError",
    "InvalidWorkflowInput",
    "SessionRequired",
    "WorkflowIdConflict",
    "WorkflowRejected",
]
