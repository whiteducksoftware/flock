"""External agent runtime integration — protocol, models, engine, and scheduler.

The engine path (``ExternalEngineComponent``) is the supported way to run
external CLI agents. The legacy ``ExternalAgentScheduler`` is being phased
out in favour of the engine — see
docs/plans/2026-04-16-001-refactor-meta-orchestrator-engine-pattern-plan.md
"""

from flock.integrations.external.engine import (
    ExternalEngineComponent,
    ExternalEngineExecutionError,
)
from flock.integrations.external.models import (
    AgentOutcome,
    ExternalAgentConfig,
    ExternalSessionStore,
    LazySQLiteExternalSessionStore,
    SQLiteExternalSessionStore,
    SessionStoreProtocol,
    SpawnConfig,
    SpawnResult,
)
from flock.integrations.external.runtime import ExternalAgentRuntime
from flock.integrations.external.scheduler import ExternalAgentScheduler

__all__ = [
    "AgentOutcome",
    "ExternalAgentConfig",
    "ExternalAgentRuntime",
    "ExternalAgentScheduler",
    "ExternalEngineComponent",
    "ExternalEngineExecutionError",
    "ExternalSessionStore",
    "LazySQLiteExternalSessionStore",
    "SQLiteExternalSessionStore",
    "SessionStoreProtocol",
    "SpawnConfig",
    "SpawnResult",
]
