"""Condition DSL for workflow termination and subscription activation.

This module provides a protocol-based DSL for defining conditions that
can be evaluated against the orchestrator state. Conditions are composable
using boolean operators (&, |, ~).

Spec: 003-until-conditions-dsl

Examples:
    >>> # Simple condition
    >>> condition = Until.idle()
    >>> result = await condition.evaluate(orchestrator)

    >>> # Composite conditions
    >>> stop_condition = Until.artifact_count(
    ...     UserStory, correlation_id=cid
    ... ).at_least(5) | Until.workflow_error(cid)
    >>> await flock.run_until(stop_condition, timeout=60)
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel


if TYPE_CHECKING:
    from flock.core import Flock


# ============================================================================
# RunCondition Protocol
# ============================================================================


@runtime_checkable
class RunCondition(Protocol):
    """Protocol for workflow termination/activation conditions.

    All conditions must implement the `evaluate` method which checks
    the condition against the current orchestrator state.

    Conditions support boolean composition via operators:
    - `&` (and): Both conditions must be True
    - `|` (or): Either condition must be True
    - `~` (not): Inverts the condition result

    Examples:
        >>> class MyCondition:
        ...     async def evaluate(self, orchestrator: Flock) -> bool:
        ...         return True  # Custom logic here

        >>> # Composition
        >>> combined = cond1 & cond2 | ~cond3
    """

    @abstractmethod
    async def evaluate(self, orchestrator: Flock) -> bool:
        """Evaluate condition against current orchestrator state.

        Args:
            orchestrator: Flock orchestrator instance to evaluate against

        Returns:
            True if condition is satisfied, False otherwise
        """
        ...

    def __and__(self, other: RunCondition) -> RunCondition:
        """Create AND composite: self & other.

        Args:
            other: Another condition to AND with

        Returns:
            AndCondition combining both conditions
        """
        return AndCondition(self, other)

    def __or__(self, other: RunCondition) -> RunCondition:
        """Create OR composite: self | other.

        Args:
            other: Another condition to OR with

        Returns:
            OrCondition combining both conditions
        """
        return OrCondition(self, other)

    def __invert__(self) -> RunCondition:
        """Create NOT composite: ~self.

        Returns:
            NotCondition that inverts this condition
        """
        return NotCondition(self)


# ============================================================================
# Composite Conditions
# ============================================================================


@dataclass
class AndCondition:
    """Composite condition: left AND right.

    Evaluates to True only if both left and right conditions are True.
    Uses short-circuit evaluation (right not evaluated if left is False).

    Examples:
        >>> and_cond = AndCondition(cond1, cond2)
        >>> # Or using operator:
        >>> and_cond = cond1 & cond2
    """

    left: RunCondition
    right: RunCondition

    async def evaluate(self, orchestrator: Flock) -> bool:
        """Evaluate AND condition with short-circuit logic.

        Args:
            orchestrator: Flock orchestrator instance

        Returns:
            True if both conditions are True
        """
        # Short-circuit: if left is False, don't evaluate right
        if not await self.left.evaluate(orchestrator):
            return False
        return await self.right.evaluate(orchestrator)

    def __and__(self, other: RunCondition) -> RunCondition:
        """Chain AND conditions."""
        return AndCondition(self, other)

    def __or__(self, other: RunCondition) -> RunCondition:
        """Chain with OR."""
        return OrCondition(self, other)

    def __invert__(self) -> RunCondition:
        """Negate this condition."""
        return NotCondition(self)


@dataclass
class OrCondition:
    """Composite condition: left OR right.

    Evaluates to True if either left or right condition is True.
    Uses short-circuit evaluation (right not evaluated if left is True).

    Examples:
        >>> or_cond = OrCondition(cond1, cond2)
        >>> # Or using operator:
        >>> or_cond = cond1 | cond2
    """

    left: RunCondition
    right: RunCondition

    async def evaluate(self, orchestrator: Flock) -> bool:
        """Evaluate OR condition with short-circuit logic.

        Args:
            orchestrator: Flock orchestrator instance

        Returns:
            True if either condition is True
        """
        # Short-circuit: if left is True, don't evaluate right
        if await self.left.evaluate(orchestrator):
            return True
        return await self.right.evaluate(orchestrator)

    def __and__(self, other: RunCondition) -> RunCondition:
        """Chain with AND."""
        return AndCondition(self, other)

    def __or__(self, other: RunCondition) -> RunCondition:
        """Chain OR conditions."""
        return OrCondition(self, other)

    def __invert__(self) -> RunCondition:
        """Negate this condition."""
        return NotCondition(self)


@dataclass
class NotCondition:
    """Composite condition: NOT inner.

    Inverts the result of the inner condition.

    Examples:
        >>> not_cond = NotCondition(cond)
        >>> # Or using operator:
        >>> not_cond = ~cond
    """

    condition: RunCondition

    async def evaluate(self, orchestrator: Flock) -> bool:
        """Evaluate NOT condition.

        Args:
            orchestrator: Flock orchestrator instance

        Returns:
            Inverted result of inner condition
        """
        return not await self.condition.evaluate(orchestrator)

    def __and__(self, other: RunCondition) -> RunCondition:
        """Chain with AND."""
        return AndCondition(self, other)

    def __or__(self, other: RunCondition) -> RunCondition:
        """Chain with OR."""
        return OrCondition(self, other)

    def __invert__(self) -> RunCondition:
        """Double negation: ~~cond = cond."""
        return NotCondition(self)


# ============================================================================
# Concrete Conditions
# ============================================================================


@dataclass
class IdleCondition:
    """Condition that checks if orchestrator has no pending work.

    Returns True when the scheduler has no pending tasks.
    Useful for waiting until all current work completes.

    Examples:
        >>> condition = IdleCondition()
        >>> await flock.run_until(condition)
    """

    async def evaluate(self, orchestrator: Flock) -> bool:
        """Check if orchestrator is idle (no pending tasks).

        Args:
            orchestrator: Flock orchestrator instance

        Returns:
            True if no pending scheduler tasks
        """
        return not orchestrator._scheduler.pending_tasks

    def __and__(self, other: RunCondition) -> RunCondition:
        """Chain with AND."""
        return AndCondition(self, other)

    def __or__(self, other: RunCondition) -> RunCondition:
        """Chain with OR."""
        return OrCondition(self, other)

    def __invert__(self) -> RunCondition:
        """Negate this condition."""
        return NotCondition(self)


@dataclass
class ArtifactCountCondition:
    """Condition based on artifact count in the store.

    Queries the store for artifacts matching the given filters and
    compares the count against min_count, max_count, or exact_count.

    Examples:
        >>> # At least 5 user stories
        >>> condition = ArtifactCountCondition(model=UserStory, min_count=5)

        >>> # Using builder methods
        >>> condition = ArtifactCountCondition(model=UserStory).at_least(5)
    """

    model: type[BaseModel]
    correlation_id: str | None = None
    tags: set[str] | None = None
    produced_by: str | None = None
    min_count: int | None = None
    max_count: int | None = None
    exact_count: int | None = None

    async def evaluate(self, orchestrator: Flock) -> bool:
        """Query artifacts and check count against thresholds.

        Args:
            orchestrator: Flock orchestrator instance

        Returns:
            True if count satisfies all specified constraints
        """
        from flock.core.store import FilterConfig
        from flock.registry import type_registry

        filters = FilterConfig(
            type_names={type_registry.name_for(self.model)},
            correlation_id=self.correlation_id,
            tags=self.tags,
            produced_by={self.produced_by} if self.produced_by else None,
        )
        _, total = await orchestrator.store.query_artifacts(filters, limit=0)

        if self.min_count is not None and total < self.min_count:
            return False
        if self.max_count is not None and total > self.max_count:
            return False
        if self.exact_count is not None and total != self.exact_count:
            return False
        return True

    def at_least(self, n: int) -> ArtifactCountCondition:
        """Set minimum count threshold.

        Args:
            n: Minimum number of artifacts required

        Returns:
            New condition with min_count set
        """
        return replace(self, min_count=n)

    def at_most(self, n: int) -> ArtifactCountCondition:
        """Set maximum count threshold.

        Args:
            n: Maximum number of artifacts allowed

        Returns:
            New condition with max_count set
        """
        return replace(self, max_count=n)

    def exactly(self, n: int) -> ArtifactCountCondition:
        """Set exact count requirement.

        Args:
            n: Exact number of artifacts required

        Returns:
            New condition with exact_count set
        """
        return replace(self, exact_count=n)

    def __and__(self, other: RunCondition) -> RunCondition:
        """Chain with AND."""
        return AndCondition(self, other)

    def __or__(self, other: RunCondition) -> RunCondition:
        """Chain with OR."""
        return OrCondition(self, other)

    def __invert__(self) -> RunCondition:
        """Negate this condition."""
        return NotCondition(self)


@dataclass
class ExistsCondition:
    """Condition that checks if any matching artifact exists.

    Queries the store with limit=1 for efficiency and returns True
    if at least one matching artifact is found.

    Examples:
        >>> # Check if any approval exists
        >>> condition = ExistsCondition(model=Approval, correlation_id=cid)
    """

    model: type[BaseModel]
    correlation_id: str | None = None
    tags: set[str] | None = None

    async def evaluate(self, orchestrator: Flock) -> bool:
        """Check if any matching artifact exists.

        Args:
            orchestrator: Flock orchestrator instance

        Returns:
            True if at least one matching artifact exists
        """
        from flock.core.store import FilterConfig
        from flock.registry import type_registry

        filters = FilterConfig(
            type_names={type_registry.name_for(self.model)},
            correlation_id=self.correlation_id,
            tags=self.tags,
        )
        _, total = await orchestrator.store.query_artifacts(filters, limit=1)
        return bool(total > 0)

    def __and__(self, other: RunCondition) -> RunCondition:
        """Chain with AND."""
        return AndCondition(self, other)

    def __or__(self, other: RunCondition) -> RunCondition:
        """Chain with OR."""
        return OrCondition(self, other)

    def __invert__(self) -> RunCondition:
        """Negate this condition."""
        return NotCondition(self)


@dataclass
class FieldPredicateCondition:
    """Condition based on a field value predicate.

    Queries artifacts and checks if any artifact's payload field
    satisfies the given predicate function.

    Note:
        For performance, this condition checks up to 100 artifacts.
        If your workflow produces more than 100 artifacts of the same type,
        consider using more specific filters or a different condition strategy.

    Examples:
        >>> # Check for high-confidence hypothesis
        >>> condition = FieldPredicateCondition(
        ...     model=Hypothesis,
        ...     field="confidence",
        ...     predicate=lambda v: v is not None and v >= 0.9,
        ... )
    """

    model: type[BaseModel]
    field: str
    predicate: Callable[[Any], bool]
    correlation_id: str | None = None

    async def evaluate(self, orchestrator: Flock) -> bool:
        """Check if any artifact field satisfies the predicate.

        Args:
            orchestrator: Flock orchestrator instance

        Returns:
            True if any artifact's field value satisfies the predicate
        """
        from flock.core.store import FilterConfig
        from flock.registry import type_registry

        filters = FilterConfig(
            type_names={type_registry.name_for(self.model)},
            correlation_id=self.correlation_id,
        )
        artifacts, _ = await orchestrator.store.query_artifacts(filters, limit=100)

        for artifact in artifacts:
            value = artifact.payload.get(self.field)
            if self.predicate(value):
                return True
        return False

    def __and__(self, other: RunCondition) -> RunCondition:
        """Chain with AND."""
        return AndCondition(self, other)

    def __or__(self, other: RunCondition) -> RunCondition:
        """Chain with OR."""
        return OrCondition(self, other)

    def __invert__(self) -> RunCondition:
        """Negate this condition."""
        return NotCondition(self)


@dataclass
class WorkflowErrorCondition:
    """Condition that checks for WorkflowError artifacts.

    Uses orchestrator.get_correlation_status() to check if any
    error artifacts exist for the given correlation_id.

    Examples:
        >>> # Stop on first error
        >>> condition = WorkflowErrorCondition(correlation_id=cid)
    """

    correlation_id: str

    async def evaluate(self, orchestrator: Flock) -> bool:
        """Check if workflow has error artifacts.

        Args:
            orchestrator: Flock orchestrator instance

        Returns:
            True if error_count > 0
        """
        status = await orchestrator.get_correlation_status(self.correlation_id)
        error_count: int = status.get("error_count", 0)
        return error_count > 0

    def __and__(self, other: RunCondition) -> RunCondition:
        """Chain with AND."""
        return AndCondition(self, other)

    def __or__(self, other: RunCondition) -> RunCondition:
        """Chain with OR."""
        return OrCondition(self, other)

    def __invert__(self) -> RunCondition:
        """Negate this condition."""
        return NotCondition(self)


# ============================================================================
# Until Helper (Builder Pattern)
# ============================================================================


class Until:
    """Builder for workflow termination conditions.

    Provides a fluent API for creating common condition types.
    All methods are static and return condition instances that can
    be composed using boolean operators.

    Examples:
        >>> # Wait until idle
        >>> await flock.run_until(Until.idle())

        >>> # Wait for 5 user stories or error
        >>> condition = Until.artifact_count(
        ...     UserStory, correlation_id=cid
        ... ).at_least(5) | Until.workflow_error(cid)
        >>> await flock.run_until(condition, timeout=60)

        >>> # Wait for high-confidence hypothesis
        >>> condition = Until.any_field(
        ...     Hypothesis,
        ...     field="confidence",
        ...     predicate=lambda v: v is not None and v >= 0.9,
        ... )
    """

    @staticmethod
    def idle() -> IdleCondition:
        """Create condition that checks if orchestrator is idle.

        Returns:
            IdleCondition instance
        """
        return IdleCondition()

    @staticmethod
    def no_pending_work() -> IdleCondition:
        """Alias for idle() - checks if no pending work.

        Returns:
            IdleCondition instance
        """
        return IdleCondition()

    @staticmethod
    def artifact_count(
        model: type[BaseModel],
        *,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
        produced_by: str | None = None,
    ) -> ArtifactCountCondition:
        """Create condition based on artifact count.

        Args:
            model: Pydantic model class for artifact type
            correlation_id: Optional correlation_id filter
            tags: Optional tags filter
            produced_by: Optional producer agent filter

        Returns:
            ArtifactCountCondition that can be chained with
            at_least(), at_most(), or exactly()

        Examples:
            >>> Until.artifact_count(UserStory).at_least(5)
            >>> Until.artifact_count(UserStory, correlation_id=cid).exactly(10)
        """
        return ArtifactCountCondition(
            model=model,
            correlation_id=correlation_id,
            tags=tags,
            produced_by=produced_by,
        )

    @staticmethod
    def exists(
        model: type[BaseModel],
        *,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
    ) -> ExistsCondition:
        """Create condition that checks if any matching artifact exists.

        Args:
            model: Pydantic model class for artifact type
            correlation_id: Optional correlation_id filter
            tags: Optional tags filter

        Returns:
            ExistsCondition instance

        Examples:
            >>> Until.exists(Approval, correlation_id=cid)
        """
        return ExistsCondition(
            model=model,
            correlation_id=correlation_id,
            tags=tags,
        )

    @staticmethod
    def none(
        model: type[BaseModel],
        *,
        correlation_id: str | None = None,
    ) -> NotCondition:
        """Create condition that checks if NO matching artifacts exist.

        Equivalent to ~Until.exists(model).

        Args:
            model: Pydantic model class for artifact type
            correlation_id: Optional correlation_id filter

        Returns:
            NotCondition wrapping ExistsCondition

        Examples:
            >>> Until.none(Error, correlation_id=cid)  # No errors exist
        """
        return NotCondition(ExistsCondition(model=model, correlation_id=correlation_id))

    @staticmethod
    def any_field(
        model: type[BaseModel],
        *,
        field: str,
        predicate: Callable[[Any], bool],
        correlation_id: str | None = None,
    ) -> FieldPredicateCondition:
        """Create condition based on field value predicate.

        Checks if any artifact has a field value satisfying the predicate.

        Args:
            model: Pydantic model class for artifact type
            field: Field name to check in artifact payload
            predicate: Function (value) -> bool to evaluate field
            correlation_id: Optional correlation_id filter

        Returns:
            FieldPredicateCondition instance

        Examples:
            >>> Until.any_field(
            ...     Hypothesis,
            ...     field="confidence",
            ...     predicate=lambda v: v >= 0.9,
            ... )
        """
        return FieldPredicateCondition(
            model=model,
            field=field,
            predicate=predicate,
            correlation_id=correlation_id,
        )

    @staticmethod
    def workflow_error(correlation_id: str) -> WorkflowErrorCondition:
        """Create condition that checks for workflow errors.

        Uses orchestrator.get_correlation_status() to check
        if any WorkflowError artifacts exist.

        Args:
            correlation_id: Correlation ID to check for errors

        Returns:
            WorkflowErrorCondition instance

        Examples:
            >>> Until.workflow_error(cid)  # Stop on first error
        """
        return WorkflowErrorCondition(correlation_id=correlation_id)


# ============================================================================
# When Helper - Subscription Activation Conditions
# ============================================================================


@dataclass
class CorrelationConditionBuilder:
    """Builder for subscription activation conditions.

    Creates conditions that evaluate against artifacts within a correlation.
    Used with When.correlation() to build activation conditions for subscriptions.

    The conditions created by this builder are typically bound to a specific
    correlation_id at evaluation time by the ActivationComponent.

    Attributes:
        model: Pydantic model class for artifact type to check

    Examples:
        >>> # Count-based activation
        >>> When.correlation(UserStory).count_at_least(5)

        >>> # Field-based activation
        >>> When.correlation(Hypothesis).any_field(
        ...     field="confidence",
        ...     predicate=lambda v: v >= 0.9,
        ... )

        >>> # Existence check
        >>> When.correlation(Approval).exists()
    """

    model: type[BaseModel]

    def count_at_least(self, n: int) -> ArtifactCountCondition:
        """Create condition requiring at least N artifacts.

        Args:
            n: Minimum artifact count threshold

        Returns:
            ArtifactCountCondition with min_count set

        Examples:
            >>> When.correlation(UserStory).count_at_least(5)
        """
        return ArtifactCountCondition(model=self.model, min_count=n)

    def count_at_most(self, n: int) -> ArtifactCountCondition:
        """Create condition requiring at most N artifacts.

        Args:
            n: Maximum artifact count threshold

        Returns:
            ArtifactCountCondition with max_count set

        Examples:
            >>> When.correlation(Error).count_at_most(3)
        """
        return ArtifactCountCondition(model=self.model, max_count=n)

    def count_exactly(self, n: int) -> ArtifactCountCondition:
        """Create condition requiring exactly N artifacts.

        Args:
            n: Exact artifact count required

        Returns:
            ArtifactCountCondition with exact_count set

        Examples:
            >>> When.correlation(Approval).count_exactly(2)
        """
        return ArtifactCountCondition(model=self.model, exact_count=n)

    def any_field(
        self,
        *,
        field: str,
        predicate: Callable[[Any], bool],
    ) -> FieldPredicateCondition:
        """Create condition based on field value predicate.

        Checks if any artifact has a field value satisfying the predicate.

        Args:
            field: Field name to check in artifact payload
            predicate: Function (value) -> bool to evaluate field

        Returns:
            FieldPredicateCondition instance

        Examples:
            >>> When.correlation(Hypothesis).any_field(
            ...     field="confidence",
            ...     predicate=lambda v: v >= 0.9,
            ... )
        """
        return FieldPredicateCondition(
            model=self.model,
            field=field,
            predicate=predicate,
        )

    def exists(self) -> ExistsCondition:
        """Create condition checking if any artifact exists.

        Returns:
            ExistsCondition instance

        Examples:
            >>> When.correlation(Approval).exists()
        """
        return ExistsCondition(model=self.model)


class When:
    """Builder for subscription activation conditions.

    Creates conditions that determine when a subscription should activate.
    Used with agent.consumes(..., activation=...) to defer agent execution
    until specific conditions are met within the correlation.

    The When helper provides a fluent interface for building activation
    conditions, similar to the Until helper for run_until() conditions.

    Examples:
        >>> # Activate QA agent after 5 user stories generated
        >>> qa_agent.consumes(
        ...     UserStory,
        ...     activation=When.correlation(UserStory).count_at_least(5),
        ... )

        >>> # Activate synthesis after high-confidence hypothesis found
        >>> synthesis.consumes(
        ...     Hypothesis,
        ...     activation=When.correlation(Hypothesis).any_field(
        ...         field="confidence",
        ...         predicate=lambda v: v >= 0.9,
        ...     ),
        ... )

        >>> # Composite activation condition
        >>> agent.consumes(
        ...     Data,
        ...     activation=(
        ...         When.correlation(Input).count_at_least(10)
        ...         | When.correlation(Signal).exists()
        ...     ),
        ... )
    """

    @staticmethod
    def correlation(model: type[BaseModel]) -> CorrelationConditionBuilder:
        """Start building a correlation-scoped activation condition.

        Creates a builder for conditions that evaluate artifacts of the
        specified type within the current correlation context.

        Args:
            model: Pydantic model class for artifact type to check

        Returns:
            CorrelationConditionBuilder for chaining

        Examples:
            >>> When.correlation(UserStory).count_at_least(5)
            >>> When.correlation(Hypothesis).any_field(...)
            >>> When.correlation(Approval).exists()
        """
        return CorrelationConditionBuilder(model=model)


__all__ = [
    "AndCondition",
    "ArtifactCountCondition",
    "CorrelationConditionBuilder",
    "ExistsCondition",
    "FieldPredicateCondition",
    "IdleCondition",
    "NotCondition",
    "OrCondition",
    "RunCondition",
    "Until",
    "When",
    "WorkflowErrorCondition",
]
