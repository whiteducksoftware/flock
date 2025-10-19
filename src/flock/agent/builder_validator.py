"""Validation and normalization logic for AgentBuilder fluent API.

Phase 5B: Extracted from agent.py to reduce file size and improve modularity.

This module contains validation methods that warn about common configuration issues
and normalization methods that convert dict-based specs to proper dataclass instances.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from flock.core.subscription import BatchSpec, JoinSpec


if TYPE_CHECKING:
    from flock.core import Agent


class BuilderValidator:
    """Validation and normalization logic for AgentBuilder configuration.

    This class provides static methods for:
    - Warning about feedback loop risks (self-trigger detection)
    - Warning about excessive best_of or max_concurrency values
    - Normalizing dict-based JoinSpec and BatchSpec to proper instances
    """

    @staticmethod
    def validate_self_trigger_risk(agent: Agent) -> None:
        """T074: Warn if agent consumes and publishes same type (feedback loop risk).

        Detects when an agent subscribes to and publishes the same artifact type,
        which could create infinite feedback loops if not configured carefully.

        Args:
            agent: Agent instance to validate
        """
        from flock.logging.logging import get_logger

        logger = get_logger(__name__)

        # Get types agent consumes
        consuming_types = set()
        for sub in agent.subscriptions:
            consuming_types.update(sub.type_names)

        # Get types agent publishes
        publishing_types = {
            output.spec.type_name
            for group in agent.output_groups
            for output in group.outputs
        }

        # Check for overlap
        overlap = consuming_types.intersection(publishing_types)
        if overlap and agent.prevent_self_trigger:
            logger.warning(
                f"Agent '{agent.name}' consumes and publishes {overlap}. "
                f"Feedback loop risk detected. Agent has prevent_self_trigger=True (safe), "
                f"but consider adding filtering: .consumes(Type, where=lambda x: ...) "
                f"or use .prevent_self_trigger(False) for intentional feedback."
            )

    @staticmethod
    def validate_best_of(agent_name: str, n: int) -> None:
        """T074: Warn if best_of value is excessively high.

        High best_of values (>100) dramatically increase cost and latency
        by running the same evaluation multiple times.

        Args:
            agent_name: Name of agent being validated
            n: best_of value to validate
        """
        from flock.logging.logging import get_logger

        logger = get_logger(__name__)

        if n > 100:
            logger.warning(
                f"Agent '{agent_name}' has best_of({n}) which is very high. "
                f"Typical values are 3-10. High values increase cost and latency. "
                f"Consider reducing unless you have specific requirements."
            )

    @staticmethod
    def validate_concurrency(agent_name: str, n: int) -> None:
        """T074: Warn if max_concurrency is excessively high.

        Excessive concurrency (>1000) may overwhelm resources and cause
        rate limiting, memory issues, or performance degradation.

        Args:
            agent_name: Name of agent being validated
            n: max_concurrency value to validate
        """
        from flock.logging.logging import get_logger

        logger = get_logger(__name__)

        if n > 1000:
            logger.warning(
                f"Agent '{agent_name}' has max_concurrency({n}) which is very high. "
                f"Typical values are 1-50. Excessive concurrency may cause resource issues. "
                f"Consider reducing unless you have specific infrastructure."
            )

    @staticmethod
    def normalize_join(value: dict | JoinSpec | None) -> JoinSpec | None:
        """Normalize dict-based JoinSpec to proper JoinSpec instance.

        Converts dict syntax to JoinSpec dataclass for backward compatibility:
        >>> normalize_join({"by": "user_id", "within": 60.0})
        JoinSpec(by="user_id", within=timedelta(seconds=60.0))

        Args:
            value: Either a JoinSpec instance, a dict with join config, or None

        Returns:
            JoinSpec instance or None
        """
        if value is None or isinstance(value, JoinSpec):
            return value

        # Phase 2: New JoinSpec API with 'by' and 'within' (time OR count)
        within_value = value.get("within")
        if isinstance(within_value, (int, float)):
            # Count window or seconds as float - keep as is
            within = (
                int(within_value)
                if isinstance(within_value, int)
                else timedelta(seconds=within_value)
            )
        else:
            # Default to 1 minute time window
            within = timedelta(minutes=1)

        return JoinSpec(
            by=value["by"],  # Required
            within=within,
        )

    @staticmethod
    def normalize_batch(value: dict | BatchSpec | None) -> BatchSpec | None:
        """Normalize dict-based BatchSpec to proper BatchSpec instance.

        Converts dict syntax to BatchSpec dataclass for backward compatibility:
        >>> normalize_batch({"size": 10, "within": 5.0})
        BatchSpec(size=10, within=5.0, by=None)

        Args:
            value: Either a BatchSpec instance, a dict with batch config, or None

        Returns:
            BatchSpec instance or None
        """
        if value is None or isinstance(value, BatchSpec):
            return value

        return BatchSpec(
            size=int(value.get("size", 1)),
            within=float(value.get("within", 0.0)),
            by=value.get("by"),
        )


__all__ = ["BuilderValidator"]
