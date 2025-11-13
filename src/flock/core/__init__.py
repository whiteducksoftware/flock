"""Core abstractions and interfaces."""

from flock.core.agent import (
    Agent,
    AgentBuilder,
    AgentOutput,
    MCPServerConfig,
    OutputGroup,
    Pipeline,
    PublishBuilder,
    RunHandle,
)
from flock.core.fan_out import FanOutRange, FanOutSpec, normalize_fan_out
from flock.core.orchestrator import BoardHandle, Flock, start_orchestrator
from flock.core.visibility import AgentIdentity


__all__ = [
    "Agent",
    "AgentBuilder",
    "AgentIdentity",
    "AgentOutput",
    "BoardHandle",
    "FanOutRange",
    "FanOutSpec",
    "Flock",
    "MCPServerConfig",
    "OutputGroup",
    "Pipeline",
    "PublishBuilder",
    "RunHandle",
    "normalize_fan_out",
    "start_orchestrator",
]
