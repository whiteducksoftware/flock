"""Transport-independent workflow execution for Flock applications.

Build a :class:`FlockApplication` from a factory that returns a configured
``Flock(no_output=True)``, then run typed workflows from any host - a queue
worker, an ASGI endpoint or an agent runtime such as Microsoft Foundry
(``flock.integrations.foundry``)::

    app = FlockApplication(
        factory=build_flock,
        input_type=IncidentRequest,
        output_types=(IncidentSummary,),
        required_output_types=(IncidentSummary,),
    )

    async with app.stream(
        request, context=WorkflowContext(workflow_id="job-42")
    ) as wf:
        async for event in wf:
            print(event.value)
        result = await wf.result()
        result.raise_for_status()

Streaming here is per *artifact*: an output is emitted once it is published,
not token by token.
"""

from flock.application.application import (
    AdmissionController,
    CountingAdmission,
    FlockApplication,
    WorkflowFactory,
    WorkflowStream,
)
from flock.application.errors import (
    ApplicationNotRunning,
    CapacityExceeded,
    ContractError,
    InvalidWorkflowInput,
    SessionRequired,
    WorkflowIdConflict,
    WorkflowRejected,
)
from flock.application.types import (
    AccessPolicy,
    CompletionPolicy,
    FailureCode,
    HistoryMode,
    OutputContract,
    WorkflowContext,
    WorkflowEvent,
    WorkflowFailedError,
    WorkflowFailure,
    WorkflowResult,
    WorkflowStatus,
)


__all__ = [
    "AccessPolicy",
    "AdmissionController",
    "ApplicationNotRunning",
    "CapacityExceeded",
    "CompletionPolicy",
    "ContractError",
    "CountingAdmission",
    "FailureCode",
    "FlockApplication",
    "HistoryMode",
    "InvalidWorkflowInput",
    "OutputContract",
    "SessionRequired",
    "WorkflowContext",
    "WorkflowEvent",
    "WorkflowFactory",
    "WorkflowFailedError",
    "WorkflowFailure",
    "WorkflowIdConflict",
    "WorkflowRejected",
    "WorkflowResult",
    "WorkflowStatus",
    "WorkflowStream",
]
