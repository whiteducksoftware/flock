"""ActivationComponent - Evaluates subscription activation conditions.

Spec: 003-until-conditions-dsl
Phase 5: T5.6 - Implement ActivationComponent

This component evaluates activation conditions on subscriptions before
an agent is scheduled. If an activation condition is set and evaluates
to False, the artifact is deferred (filtered out) until the condition
becomes True.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flock.components.orchestrator.base import OrchestratorComponent
from flock.logging.logging import get_logger


if TYPE_CHECKING:
    from flock.core import Agent, Flock
    from flock.core.artifacts import Artifact
    from flock.core.subscription import Subscription


logger = get_logger("flock.components.orchestrator.activation")


class ActivationComponent(OrchestratorComponent):
    """Evaluates subscription activation conditions before scheduling.

    This component hooks into the on_before_agent_schedule lifecycle event
    to filter artifacts based on activation conditions. If an artifact's
    matching subscription has an activation condition that evaluates to False,
    the artifact is filtered out (deferred).

    Attributes:
        name: Component name for logging/debugging
        priority: Execution priority (15 - after circuit breaker, before dedup)

    Examples:
        >>> # Agent only activates after 5 user stories generated
        >>> qa_agent.consumes(
        ...     UserStory,
        ...     activation=When.correlation(UserStory).count_at_least(5),
        ... )
        >>> # ActivationComponent will filter artifacts until condition is met
    """

    name: str = "activation"
    priority: int = 15  # After circuit breaker (10), before dedup (20)

    async def on_before_agent_schedule(
        self,
        orchestrator: Flock,
        agent: Agent,
        artifacts: list[Artifact],
    ) -> list[Artifact] | None:
        """Filter artifacts based on activation conditions.

        For each artifact, finds the matching subscription and evaluates
        its activation condition. If the condition is False, the artifact
        is filtered out (deferred for later).

        Args:
            orchestrator: Flock orchestrator instance
            agent: Agent to schedule
            artifacts: Collected artifacts

        Returns:
            Filtered list of artifacts that pass activation conditions,
            or None to block scheduling entirely
        """
        if not artifacts:
            return artifacts

        result: list[Artifact] = []

        for artifact in artifacts:
            # Find the subscription that matched this artifact
            subscription = self._find_matching_subscription(agent, artifact)

            if subscription is None:
                # No matching subscription found, include artifact by default
                logger.debug(
                    f"No matching subscription found for artifact {artifact.id}, "
                    "including by default"
                )
                result.append(artifact)
                continue

            if subscription.activation is None:
                # No activation condition, include artifact
                result.append(artifact)
                continue

            # Evaluate activation condition
            try:
                # Bind correlation context to condition if needed
                condition = self._bind_correlation_context(
                    subscription.activation,
                    artifact.correlation_id,
                )

                is_activated = await condition.evaluate(orchestrator)

                if is_activated:
                    result.append(artifact)
                    logger.debug(
                        f"Activation condition met for artifact {artifact.id}, "
                        f"agent {agent.name}"
                    )
                else:
                    logger.debug(
                        f"Activation condition NOT met for artifact {artifact.id}, "
                        f"agent {agent.name} - deferring"
                    )
                    # Artifact is filtered out (deferred)

            except Exception as e:
                logger.warning(
                    f"Error evaluating activation condition for artifact "
                    f"{artifact.id}: {e}. Including artifact by default."
                )
                result.append(artifact)

        return result

    def _find_matching_subscription(
        self,
        agent: Agent,
        artifact: Artifact,
    ) -> Subscription | None:
        """Find the subscription that matches this artifact.

        Args:
            agent: Agent to search subscriptions for
            artifact: Artifact to match

        Returns:
            Matching subscription or None if not found
        """
        from flock.core.subscription import Subscription

        for subscription in agent.subscriptions:
            if isinstance(subscription, Subscription):
                if artifact.type in subscription.type_names:
                    return subscription

        return None

    def _bind_correlation_context(
        self,
        condition,
        correlation_id: str | None,
    ):
        """Bind correlation context to a condition.

        Creates a copy of the condition with the artifact's correlation_id
        bound, so that queries are scoped to the current workflow rather
        than searching the entire store.

        For composite conditions (And, Or, Not), recursively binds to
        all child conditions.

        Args:
            condition: RunCondition to potentially wrap
            correlation_id: Correlation ID from artifact

        Returns:
            Condition with correlation_id bound (if applicable)
        """
        from dataclasses import replace

        from flock.core.conditions import (
            AndCondition,
            ArtifactCountCondition,
            ExistsCondition,
            FieldPredicateCondition,
            NotCondition,
            OrCondition,
        )

        if correlation_id is None:
            return condition

        # Handle composite conditions recursively
        if isinstance(condition, AndCondition):
            return AndCondition(
                left=self._bind_correlation_context(condition.left, correlation_id),
                right=self._bind_correlation_context(condition.right, correlation_id),
            )
        if isinstance(condition, OrCondition):
            return OrCondition(
                left=self._bind_correlation_context(condition.left, correlation_id),
                right=self._bind_correlation_context(condition.right, correlation_id),
            )
        if isinstance(condition, NotCondition):
            return NotCondition(
                condition=self._bind_correlation_context(
                    condition.condition, correlation_id
                ),
            )

        # Bind correlation_id to conditions that support it
        # Only bind if the condition doesn't already have a correlation_id set
        if isinstance(
            condition,
            (ArtifactCountCondition, ExistsCondition, FieldPredicateCondition),
        ):
            if condition.correlation_id is None:
                return replace(condition, correlation_id=correlation_id)

        return condition


__all__ = ["ActivationComponent"]
