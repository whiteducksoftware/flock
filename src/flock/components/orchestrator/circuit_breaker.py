"""Circuit breaker component to prevent runaway agent loops."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flock.components.orchestrator.base import OrchestratorComponent, ScheduleDecision


if TYPE_CHECKING:
    from flock.core import Agent, Flock
    from flock.core.artifacts import Artifact
    from flock.core.subscription import Subscription


class CircuitBreakerComponent(OrchestratorComponent):
    """Circuit breaker to prevent runaway agent loops.

    Tracks iteration count per agent and blocks scheduling when limit is reached.
    Automatically resets counters when orchestrator becomes idle.

    Priority: 10 (runs early, before deduplication)

    Configuration:
        max_iterations: Maximum iterations per agent before circuit breaker trips

    Examples:
        >>> # Use default (1000 iterations)
        >>> flock = Flock("openai/gpt-4.1")

        >>> # Custom limit
        >>> flock = Flock("openai/gpt-4.1")
        >>> for component in flock._components:
        ...     if component.name == "circuit_breaker":
        ...         component.max_iterations = 500
    """

    priority: int = 10  # Run early (before dedup at 20)
    name: str = "circuit_breaker"
    max_iterations: int = 1000  # Default from orchestrator

    def __init__(self, max_iterations: int = 1000, **kwargs):
        """Initialize circuit breaker with iteration limit.

        Args:
            max_iterations: Maximum iterations per agent (default 1000)
        """
        super().__init__(**kwargs)
        self.max_iterations = max_iterations
        self._iteration_counts: dict[str, int] = {}

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        """Check if agent has exceeded iteration limit.

        Returns SKIP if agent has reached max_iterations, preventing
        potential infinite loops.

        Uses orchestrator.max_agent_iterations if available, otherwise
        falls back to self.max_iterations.
        """
        current_count = self._iteration_counts.get(agent.name, 0)

        # Check orchestrator property first (allows runtime modification)
        # Fall back to component's max_iterations if orchestrator property doesn't exist
        max_limit = self.max_iterations
        if hasattr(orchestrator, "max_agent_iterations"):
            orch_limit = orchestrator.max_agent_iterations
            # Only use orchestrator limit if it's a valid int
            if isinstance(orch_limit, int):
                max_limit = orch_limit

        if current_count >= max_limit:
            # Circuit breaker tripped
            return ScheduleDecision.SKIP

        # Increment counter
        self._iteration_counts[agent.name] = current_count + 1
        return ScheduleDecision.CONTINUE

    async def on_orchestrator_idle(self, orchestrator: Flock) -> None:
        """Reset iteration counters when orchestrator becomes idle.

        This prevents the circuit breaker from permanently blocking agents
        across different workflow runs.
        """
        self._iteration_counts.clear()


__all__ = ["CircuitBreakerComponent"]
