"""Public package API for flock.

This module exposes the most commonly used classes and utilities at the top level
for convenient imports:

    from flock import Flock, flock_type, DSPyEngine, BAMLAdapter
    from flock import AgentComponent, EngineComponent, Context, EvalInputs, EvalResult
    from flock import Artifact, PublicVisibility, PrivateVisibility
    from flock import Until, BatchSpec, JoinSpec
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
from flock.core import Flock, start_orchestrator
from flock.registry import flock_tool, flock_type

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
# Components - Base classes for extending agents and orchestrators
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

# =============================================================================
# Runtime - Context and evaluation types for custom engines/components
# =============================================================================
from flock.utils.runtime import Context, EvalInputs, EvalResult

# =============================================================================
# Artifacts - Core data types
# =============================================================================
from flock.core.artifacts import Artifact

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
# Conditions - Workflow control DSL
# =============================================================================
from flock.core.conditions import Until

# =============================================================================
# Subscriptions - Advanced subscription patterns
# =============================================================================
from flock.core.subscription import BatchSpec, JoinSpec, ScheduleSpec

# =============================================================================
# Store - Filtering and storage
# =============================================================================
from flock.core.store import FilterConfig


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
    # Core
    "Flock",
    "flock_tool",
    "flock_type",
    "main",
    "start_orchestrator",
    # Engines
    "BAMLAdapter",
    "ChatAdapter",
    "DSPyEngine",
    "JSONAdapter",
    "TwoStepAdapter",
    "XMLAdapter",
    # Components
    "AgentComponent",
    "AgentComponentConfig",
    "EngineComponent",
    "OrchestratorComponent",
    "OrchestratorComponentConfig",
    # Runtime
    "Context",
    "EvalInputs",
    "EvalResult",
    # Artifacts
    "Artifact",
    # Visibility
    "AfterVisibility",
    "AgentIdentity",
    "LabelledVisibility",
    "PrivateVisibility",
    "PublicVisibility",
    "TenantVisibility",
    "Visibility",
    # Conditions
    "Until",
    # Subscriptions
    "BatchSpec",
    "JoinSpec",
    "ScheduleSpec",
    # Store
    "FilterConfig",
]
