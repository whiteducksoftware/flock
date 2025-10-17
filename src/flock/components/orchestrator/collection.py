"""Built-in collection component for AND gates, correlation, and batching."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flock.components.orchestrator.base import (
    CollectionResult,
    OrchestratorComponent,
)


if TYPE_CHECKING:
    from flock.agent import Agent
    from flock.artifacts import Artifact
    from flock.orchestrator import Flock
    from flock.subscription import Subscription


class BuiltinCollectionComponent(OrchestratorComponent):
    """Built-in component that handles AND gates, correlation, and batching.

    This component wraps the existing ArtifactCollector, CorrelationEngine,
    and BatchEngine to provide collection logic via the component system.

    Priority: 100 (runs after user components for circuit breaking/dedup)
    """

    priority: int = 100  # Run late (after circuit breaker/dedup components)
    name: str = "builtin_collection"

    async def on_collect_artifacts(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> CollectionResult | None:
        """Handle AND gates, correlation (JoinSpec), and batching (BatchSpec).

        This maintains backward compatibility with existing collection engines
        while allowing user components to override collection logic.
        """
        from datetime import timedelta

        # Check if subscription has required attributes (defensive for mocks/tests)
        if (
            not hasattr(subscription, "join")
            or not hasattr(subscription, "type_models")
            or not hasattr(subscription, "batch")
        ):
            # Fallback: immediate with single artifact
            return CollectionResult.immediate([artifact])

        # JoinSpec CORRELATION: Check if subscription has correlated AND gate
        if subscription.join is not None:
            subscription_index = agent.subscriptions.index(subscription)
            completed_group = orchestrator._correlation_engine.add_artifact(
                artifact=artifact,
                subscription=subscription,
                subscription_index=subscription_index,
            )

            # Start correlation cleanup task if time-based window
            if (
                isinstance(subscription.join.within, timedelta)
                and orchestrator._correlation_cleanup_task is None
            ):
                import asyncio

                orchestrator._correlation_cleanup_task = asyncio.create_task(
                    orchestrator._correlation_cleanup_loop()
                )

            if completed_group is None:
                # Still waiting for correlation to complete
                await orchestrator._emit_correlation_updated_event(
                    agent_name=agent.name,
                    subscription_index=subscription_index,
                    artifact=artifact,
                )
                return CollectionResult.waiting()

            # Correlation complete!
            artifacts = completed_group.get_artifacts()
        else:
            # AND GATE: Use artifact collector for simple AND gates (no correlation)
            is_complete, artifacts = orchestrator._artifact_collector.add_artifact(
                agent, subscription, artifact
            )

            if not is_complete:
                return CollectionResult.waiting()

        # BatchSpec BATCHING: Check if subscription has batch accumulator
        if subscription.batch is not None:
            subscription_index = agent.subscriptions.index(subscription)

            # Treat artifact groups as single batch items
            if subscription.join is not None or len(subscription.type_models) > 1:
                should_flush = orchestrator._batch_engine.add_artifact_group(
                    artifacts=artifacts,
                    subscription=subscription,
                    subscription_index=subscription_index,
                )

                if (
                    subscription.batch.timeout
                    and orchestrator._batch_timeout_task is None
                ):
                    import asyncio

                    orchestrator._batch_timeout_task = asyncio.create_task(
                        orchestrator._batch_timeout_checker_loop()
                    )
            else:
                # Single type: Add each artifact individually
                should_flush = False
                for single_artifact in artifacts:
                    should_flush = orchestrator._batch_engine.add_artifact(
                        artifact=single_artifact,
                        subscription=subscription,
                        subscription_index=subscription_index,
                    )

                    if (
                        subscription.batch.timeout
                        and orchestrator._batch_timeout_task is None
                    ):
                        import asyncio

                        orchestrator._batch_timeout_task = asyncio.create_task(
                            orchestrator._batch_timeout_checker_loop()
                        )

                    if should_flush:
                        break

            if not should_flush:
                # Batch not full yet
                await orchestrator._emit_batch_item_added_event(
                    agent_name=agent.name,
                    subscription_index=subscription_index,
                    subscription=subscription,
                    artifact=artifact,
                )
                return CollectionResult.waiting()

            # Flush batch
            batched_artifacts = orchestrator._batch_engine.flush_batch(
                agent.name, subscription_index
            )

            if batched_artifacts is None:
                return CollectionResult.waiting()

            artifacts = batched_artifacts

        # Collection complete!
        return CollectionResult.immediate(artifacts)


__all__ = ["BuiltinCollectionComponent"]
