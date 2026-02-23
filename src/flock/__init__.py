"""Public package API for flock.

This module exposes the most commonly used classes and utilities at the top level
for convenient imports:

    from flock import Flock, flock_type, DSPyEngine, BAMLAdapter
    from flock import AgentComponent, EngineComponent, ServerComponent
    from flock import Context, EvalInputs, EvalResult
    from flock import Artifact, PublicVisibility, PrivateVisibility
    from flock import Until, When, BatchSpec, JoinSpec
"""

from __future__ import annotations


# Load environment variables from .env file early
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv not available, environment variables must be set manually
    pass

# =============================================================================
# Core - Orchestrator and registration
# =============================================================================
from flock.cli import main

# =============================================================================
# Components - Base classes for extending agents, orchestrators, and server
# =============================================================================
from flock.components.agent import (
    AgentComponent,
    AgentComponentConfig,
    EngineComponent,
)
from flock.components.orchestrator import (
    OrchestratorComponent,
    OrchestratorComponentConfig,
)
from flock.components.server import (
    ServerComponent,
    ServerComponentConfig,
)
from flock.core import Flock, start_orchestrator

# =============================================================================
# Artifacts - Core data types
# =============================================================================
from flock.core.artifacts import Artifact

# =============================================================================
# Conditions - Workflow control DSL
# =============================================================================
from flock.core.conditions import Until, When

# =============================================================================
# Store - Filtering and storage
# =============================================================================
from flock.core.store import FilterConfig

# =============================================================================
# Subscriptions - Advanced subscription patterns
# =============================================================================
from flock.core.subscription import BatchSpec, JoinSpec, ScheduleSpec

# =============================================================================
# Visibility - Access control for artifacts
# =============================================================================
from flock.core.visibility import (
    AfterVisibility,
    AgentIdentity,
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
    TenantVisibility,
    Visibility,
)

# =============================================================================
# Engines - DSPy engine and adapters
# =============================================================================
from flock.engines import (
    BAMLAdapter,
    ChatAdapter,
    DSPyEngine,
    JSONAdapter,
    TwoStepAdapter,
    XMLAdapter,
)

# =============================================================================
# Integrations - OpenClaw
# =============================================================================
from flock.integrations.openclaw import GatewayConfig, OpenClawConfig, OpenClawDefaults

# =============================================================================
# Logging - Logger and configuration
# =============================================================================
from flock.logging.logging import configure_logging, get_logger
from flock.registry import flock_tool, flock_type

# =============================================================================
# Runtime - Context and evaluation types for custom engines/components
# =============================================================================
from flock.utils.runtime import Context, EvalInputs, EvalResult


def _register_optional_providers() -> None:
    """Auto-register optional LiteLLM providers when dependencies are available."""
    try:
        from flock.engines.providers.transformers_provider import (
            register_transformers_provider,
        )

        register_transformers_provider()
    except ImportError:
        pass  # transformers not installed, skip registration


# Register optional providers at import time
_register_optional_providers()


__all__ = [
    # Visibility
    "AfterVisibility",
    # Components
    "AgentComponent",
    "AgentComponentConfig",
    "AgentIdentity",
    # Artifacts
    "Artifact",
    # Engines
    "BAMLAdapter",
    # Subscriptions
    "BatchSpec",
    "ChatAdapter",
    # Runtime
    "Context",
    "DSPyEngine",
    "EngineComponent",
    "EvalInputs",
    "EvalResult",
    # Store
    "FilterConfig",
    # Core
    "Flock",
    # Integrations - OpenClaw
    "GatewayConfig",
    "JSONAdapter",
    "JoinSpec",
    "LabelledVisibility",
    "OpenClawConfig",
    "OpenClawDefaults",
    "OrchestratorComponent",
    "OrchestratorComponentConfig",
    "PrivateVisibility",
    "PublicVisibility",
    "ScheduleSpec",
    "ServerComponent",
    "ServerComponentConfig",
    "TenantVisibility",
    "TwoStepAdapter",
    # Conditions
    "Until",
    "Visibility",
    "When",
    "XMLAdapter",
    # Logging
    "configure_logging",
    "flock_tool",
    "flock_type",
    "get_logger",
    "main",
    "start_orchestrator",
]
