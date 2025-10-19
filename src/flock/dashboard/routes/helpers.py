"""Helper functions for dashboard routes."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.agent import Agent
    from flock.agent.specification import Subscription
    from flock.core import Flock
    from flock.orchestrator.batch_accumulator import BatchEngine, BatchSpec
    from flock.orchestrator.correlation_engine import CorrelationEngine


def _get_correlation_groups(
    engine: "CorrelationEngine",
    agent_name: str,
    subscription_index: int,
) -> list[dict[str, Any]]:
    """Extract correlation group state from CorrelationEngine.

    Returns waiting state for all correlation groups for the given agent subscription.
    Used by enhanced /api/agents endpoint to expose JoinSpec waiting state.

    Args:
        engine: CorrelationEngine instance from orchestrator
        agent_name: Name of the agent
        subscription_index: Index of the subscription (for agents with multiple subscriptions)

    Returns:
        List of correlation group states with progress metrics:
        [
            {
                "correlation_key": "patient_123",
                "created_at": "2025-10-13T14:30:00Z",
                "elapsed_seconds": 45.2,
                "expires_in_seconds": 254.8,  # For time windows
                "expires_in_artifacts": 7,     # For count windows
                "collected_types": {"XRayImage": 1, "LabResults": 0},
                "required_types": {"XRayImage": 1, "LabResults": 1},
                "waiting_for": ["LabResults"],
                "is_complete": False,
                "is_expired": False
            },
            ...
        ]
    """

    pool_key = (agent_name, subscription_index)
    groups = engine.correlation_groups.get(pool_key, {})

    if not groups:
        return []

    now = datetime.now(UTC)
    result = []

    for corr_key, group in groups.items():
        # Calculate elapsed time
        if group.created_at_time:
            created_at_time = group.created_at_time
            if created_at_time.tzinfo is None:
                created_at_time = created_at_time.replace(tzinfo=UTC)
            elapsed = (now - created_at_time).total_seconds()
        else:
            elapsed = 0

        # Calculate time remaining (for time windows)
        expires_in_seconds = None
        if isinstance(group.window_spec, timedelta):
            window_seconds = group.window_spec.total_seconds()
            expires_in_seconds = max(0, window_seconds - elapsed)

        # Calculate artifact count remaining (for count windows)
        expires_in_artifacts = None
        if isinstance(group.window_spec, int):
            artifacts_passed = engine.global_sequence - group.created_at_sequence
            expires_in_artifacts = max(0, group.window_spec - artifacts_passed)

        # Determine what we're waiting for
        collected_types = {
            type_name: len(group.waiting_artifacts.get(type_name, []))
            for type_name in group.required_types
        }

        waiting_for = [
            type_name
            for type_name, required_count in group.type_counts.items()
            if collected_types.get(type_name, 0) < required_count
        ]

        result.append({
            "correlation_key": str(corr_key),
            "created_at": group.created_at_time.isoformat()
            if group.created_at_time
            else None,
            "elapsed_seconds": round(elapsed, 1),
            "expires_in_seconds": round(expires_in_seconds, 1)
            if expires_in_seconds is not None
            else None,
            "expires_in_artifacts": expires_in_artifacts,
            "collected_types": collected_types,
            "required_types": dict(group.type_counts),
            "waiting_for": waiting_for,
            "is_complete": group.is_complete(),
            "is_expired": group.is_expired(engine.global_sequence),
        })

    return result


def _get_batch_state(
    engine: "BatchEngine",
    agent_name: str,
    subscription_index: int,
    batch_spec: "BatchSpec",
) -> dict[str, Any] | None:
    """Extract batch state from BatchEngine.

    Returns current batch accumulator state for the given agent subscription.
    Used by enhanced /api/agents endpoint to expose BatchSpec waiting state.

    Args:
        engine: BatchEngine instance from orchestrator
        agent_name: Name of the agent
        subscription_index: Index of the subscription
        batch_spec: BatchSpec configuration (needed for metrics)

    Returns:
        Batch state dict or None if no batch or batch is empty:
        {
            "created_at": "2025-10-13T14:30:00Z",
            "elapsed_seconds": 12.5,
            "items_collected": 18,
            "items_target": 25,
            "items_remaining": 7,
            "timeout_seconds": 30,
            "timeout_remaining_seconds": 17.5,
            "will_flush": "on_size" | "on_timeout" | "unknown"
        }
    """

    batch_key = (agent_name, subscription_index)
    accumulator = engine.batches.get(batch_key)

    # Return None if no batch or batch is empty
    if not accumulator or not accumulator.artifacts:
        return None

    now = datetime.now(UTC)
    # Ensure accumulator.created_at is timezone-aware
    created_at = accumulator.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    elapsed = (now - created_at).total_seconds()

    # Calculate items collected (needed for all batch types)
    items_collected = len(accumulator.artifacts)
    # For group batching, use _group_count if available
    if hasattr(accumulator, "_group_count"):
        items_collected = accumulator._group_count

    result = {
        "created_at": accumulator.created_at.isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "items_collected": items_collected,  # Always include for all batch types
    }

    # Size-based metrics (only if size threshold configured)
    if batch_spec.size:
        result["items_target"] = batch_spec.size
        result["items_remaining"] = max(0, batch_spec.size - items_collected)
    else:
        # Timeout-only batches: no target
        result["items_target"] = None
        result["items_remaining"] = None

    # Timeout-based metrics
    if batch_spec.timeout:
        timeout_seconds = batch_spec.timeout.total_seconds()
        timeout_remaining = max(0, timeout_seconds - elapsed)

        result["timeout_seconds"] = int(timeout_seconds)
        result["timeout_remaining_seconds"] = round(timeout_remaining, 1)

    # Determine what will trigger flush
    if batch_spec.size and batch_spec.timeout:
        # Hybrid: predict which will fire first based on progress percentages
        items_collected = result["items_collected"]
        items_target = result.get("items_target", 1)
        timeout_remaining = result.get("timeout_remaining_seconds", 0)

        # Calculate progress toward each threshold
        size_progress = items_collected / items_target if items_target > 0 else 0
        timeout_elapsed = elapsed
        timeout_total = batch_spec.timeout.total_seconds()
        time_progress = timeout_elapsed / timeout_total if timeout_total > 0 else 0

        # Predict based on which threshold we're progressing toward faster
        # If we're closer to size threshold (percentage-wise), predict size
        # Otherwise predict timeout
        if size_progress > time_progress:
            result["will_flush"] = "on_size"
        else:
            result["will_flush"] = "on_timeout"
    elif batch_spec.size:
        result["will_flush"] = "on_size"
    elif batch_spec.timeout:
        result["will_flush"] = "on_timeout"

    return result


def _compute_agent_status(agent: "Agent", orchestrator: "Flock") -> str:
    """Determine agent status based on waiting state.

    Checks if agent is waiting for correlation or batch completion.
    Used by enhanced /api/agents endpoint to show agent status.

    Args:
        agent: Agent instance
        orchestrator: Flock orchestrator instance

    Returns:
        "ready" - Agent not waiting for anything
        "waiting" - Agent has correlation groups or batches accumulating
        "active" - Agent currently executing (future enhancement)
    """
    # Check if any subscription is waiting for correlation or batching
    for idx, subscription in enumerate(agent.subscriptions):
        if subscription.join:
            pool_key = (agent.name, idx)
            if pool_key in orchestrator._correlation_engine.correlation_groups:
                groups = orchestrator._correlation_engine.correlation_groups[pool_key]
                if groups:  # Has waiting correlation groups
                    return "waiting"

        if subscription.batch:
            batch_key = (agent.name, idx)
            if batch_key in orchestrator._batch_engine.batches:
                accumulator = orchestrator._batch_engine.batches[batch_key]
                if accumulator and accumulator.artifacts:
                    return "waiting"

    return "ready"


def _build_logic_config(
    agent: "Agent",
    subscription: "Subscription",
    idx: int,
    orchestrator: "Flock",
) -> dict[str, Any] | None:
    """Build logic operations configuration for a subscription.

    Phase 1.2: Extracts JoinSpec and BatchSpec configuration plus current
    waiting state for agents using logic operations.

    Args:
        agent: Agent instance
        subscription: Subscription to analyze
        idx: Subscription index (for agents with multiple subscriptions)
        orchestrator: Flock orchestrator instance

    Returns:
        Logic operations config dict or None if no join/batch:
        {
            "subscription_index": 0,
            "subscription_types": ["XRayImage", "LabResults"],
            "join": {...},  # JoinSpec config (if present)
            "batch": {...},  # BatchSpec config (if present)
            "waiting_state": {...}  # Current state (if waiting)
        }
    """
    if not subscription.join and not subscription.batch:
        return None

    config = {
        "subscription_index": idx,
        "subscription_types": list(subscription.type_names),
    }

    # JoinSpec configuration
    if subscription.join:
        join_spec = subscription.join
        window_type = "time" if isinstance(join_spec.within, timedelta) else "count"
        window_value = (
            int(join_spec.within.total_seconds())
            if isinstance(join_spec.within, timedelta)
            else join_spec.within
        )

        config["join"] = {
            "correlation_strategy": "by_key",
            "window_type": window_type,
            "window_value": window_value,
            "window_unit": "seconds" if window_type == "time" else "artifacts",
            "required_types": list(subscription.type_names),
            "type_counts": dict(subscription.type_counts),
        }

        # Get waiting state from CorrelationEngine
        correlation_groups = _get_correlation_groups(
            orchestrator._correlation_engine, agent.name, idx
        )
        if correlation_groups:
            config["waiting_state"] = {
                "is_waiting": True,
                "correlation_groups": correlation_groups,
            }

    # BatchSpec configuration
    if subscription.batch:
        batch_spec = subscription.batch
        strategy = (
            "hybrid"
            if batch_spec.size and batch_spec.timeout
            else "size"
            if batch_spec.size
            else "timeout"
        )

        config["batch"] = {
            "strategy": strategy,
        }
        if batch_spec.size:
            config["batch"]["size"] = batch_spec.size
        if batch_spec.timeout:
            config["batch"]["timeout_seconds"] = int(batch_spec.timeout.total_seconds())

        # Get waiting state from BatchEngine
        batch_state = _get_batch_state(
            orchestrator._batch_engine, agent.name, idx, batch_spec
        )
        if batch_state:
            if "waiting_state" not in config:
                config["waiting_state"] = {"is_waiting": True}
            config["waiting_state"]["batch_state"] = batch_state

    return config
