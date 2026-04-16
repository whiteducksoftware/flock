"""External agent runtime integration — protocol, models, and engine.

External agents plug into Flock through ``ExternalEngineComponent``,
which is auto-attached to any agent declared with
``.kind("external").adapter("...")``.  See
docs/guides/meta-orchestrator.md for usage.
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

__all__ = [
    "AgentOutcome",
    "ExternalAgentConfig",
    "ExternalAgentRuntime",
    "ExternalEngineComponent",
    "ExternalEngineExecutionError",
    "ExternalSessionStore",
    "LazySQLiteExternalSessionStore",
    "SQLiteExternalSessionStore",
    "SessionStoreProtocol",
    "SpawnConfig",
    "SpawnResult",
]
