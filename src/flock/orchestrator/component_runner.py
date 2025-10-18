"""Component lifecycle hook execution for orchestrator.

This module manages the execution of OrchestratorComponent hooks in priority order.
Components can modify artifacts, control scheduling decisions, and handle collection logic.
"""

from __future__ import annotations

import logging
from asyncio import Task
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.components.orchestrator import OrchestratorComponent
    from flock.core import Agent
    from flock.core.artifacts import Artifact
    from flock.core.subscription import Subscription


class ComponentRunner:
    """Executes orchestrator component hooks in priority order.

    This class manages the component lifecycle including initialization,
    artifact processing, scheduling decisions, and shutdown. All hooks
    execute in priority order (lower priority number = earlier execution).

    Attributes:
        _components: List of orchestrator components (sorted by priority)
        _logger: Logger instance for component execution tracking
        _initialized: Flag to prevent multiple initializations
    """

    def __init__(
        self,
        components: list[OrchestratorComponent],
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the component runner.

        Args:
            components: List of orchestrator components (should be pre-sorted by priority)
            logger: Logger instance (defaults to module logger if not provided)
        """
        self._components = components
        self._logger = logger or logging.getLogger(__name__)
        self._initialized = False

    @property
    def components(self) -> list[OrchestratorComponent]:
        """Get the list of registered components."""
        return self._components

    @property
    def is_initialized(self) -> bool:
        """Check if components have been initialized."""
        return self._initialized

    async def run_initialize(self, orchestrator: Any) -> None:
        """Initialize all components in priority order (called once).

        Executes on_initialize hook for each component. Sets _initialized
        flag to prevent multiple initializations.

        Args:
            orchestrator: The Flock orchestrator instance
        """
        if self._initialized:
            return

        self._logger.info(
            f"Initializing {len(self._components)} orchestrator components"
        )

        for component in self._components:
            comp_name = component.name or component.__class__.__name__
            self._logger.debug(
                f"Initializing component: name={comp_name}, priority={component.priority}"
            )

            try:
                await component.on_initialize(orchestrator)
            except Exception as e:
                self._logger.exception(
                    f"Component initialization failed: name={comp_name}, error={e!s}"
                )
                raise

        self._initialized = True
        self._logger.info(f"All components initialized: count={len(self._components)}")

    async def run_artifact_published(
        self, orchestrator: Any, artifact: Artifact
    ) -> Artifact | None:
        """Run on_artifact_published hooks (returns modified artifact or None to block).

        Components execute in priority order, each receiving the artifact from the
        previous component (chaining). If any component returns None, the artifact
        is blocked and scheduling stops.

        Args:
            orchestrator: The Flock orchestrator instance
            artifact: The artifact being published

        Returns:
            Modified artifact or None if blocked by a component
        """
        current_artifact = artifact

        for component in self._components:
            comp_name = component.name or component.__class__.__name__
            self._logger.debug(
                f"Running on_artifact_published: component={comp_name}, "
                f"artifact_type={current_artifact.type}, artifact_id={current_artifact.id}"
            )

            try:
                result = await component.on_artifact_published(
                    orchestrator, current_artifact
                )

                if result is None:
                    self._logger.info(
                        f"Artifact blocked by component: component={comp_name}, "
                        f"artifact_type={current_artifact.type}, artifact_id={current_artifact.id}"
                    )
                    return None

                current_artifact = result
            except Exception as e:
                self._logger.exception(
                    f"Component hook failed: component={comp_name}, "
                    f"hook=on_artifact_published, error={e!s}"
                )
                raise

        return current_artifact

    async def run_before_schedule(
        self,
        orchestrator: Any,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> Any:
        """Run on_before_schedule hooks (returns CONTINUE, SKIP, or DEFER).

        Components execute in priority order. First component to return SKIP or
        DEFER stops execution and returns that decision.

        Args:
            orchestrator: The Flock orchestrator instance
            artifact: The artifact being scheduled
            agent: The target agent
            subscription: The subscription being evaluated

        Returns:
            ScheduleDecision (CONTINUE, SKIP, or DEFER)
        """
        from flock.components.orchestrator import ScheduleDecision

        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            self._logger.debug(
                f"Running on_before_schedule: component={comp_name}, "
                f"agent={agent.name}, artifact_type={artifact.type}"
            )

            try:
                decision = await component.on_before_schedule(
                    orchestrator, artifact, agent, subscription
                )

                if decision == ScheduleDecision.SKIP:
                    self._logger.info(
                        f"Scheduling skipped by component: component={comp_name}, "
                        f"agent={agent.name}, artifact_type={artifact.type}, decision=SKIP"
                    )
                    return ScheduleDecision.SKIP

                if decision == ScheduleDecision.DEFER:
                    self._logger.debug(
                        f"Scheduling deferred by component: component={comp_name}, "
                        f"agent={agent.name}, decision=DEFER"
                    )
                    return ScheduleDecision.DEFER

            except Exception as e:
                self._logger.exception(
                    f"Component hook failed: component={comp_name}, "
                    f"hook=on_before_schedule, error={e!s}"
                )
                raise

        return ScheduleDecision.CONTINUE

    async def run_collect_artifacts(
        self,
        orchestrator: Any,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> Any:
        """Run on_collect_artifacts hooks (returns first non-None result).

        Components execute in priority order. First component to return non-None
        wins (short-circuit). If all return None, default is immediate scheduling.

        Args:
            orchestrator: The Flock orchestrator instance
            artifact: The artifact being collected
            agent: The target agent
            subscription: The subscription being evaluated

        Returns:
            CollectionResult (complete=True/False, artifacts=[...])
        """
        from flock.components.orchestrator import CollectionResult

        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            self._logger.debug(
                f"Running on_collect_artifacts: component={comp_name}, "
                f"agent={agent.name}, artifact_type={artifact.type}"
            )

            try:
                result = await component.on_collect_artifacts(
                    orchestrator, artifact, agent, subscription
                )

                if result is not None:
                    self._logger.debug(
                        f"Collection handled by component: component={comp_name}, "
                        f"complete={result.complete}, artifact_count={len(result.artifacts)}"
                    )
                    return result
            except Exception as e:
                self._logger.exception(
                    f"Component hook failed: component={comp_name}, "
                    f"hook=on_collect_artifacts, error={e!s}"
                )
                raise

        # Default: immediate scheduling with single artifact
        self._logger.debug(
            f"No component handled collection, using default: "
            f"agent={agent.name}, artifact_type={artifact.type}"
        )
        return CollectionResult.immediate([artifact])

    async def run_before_agent_schedule(
        self, orchestrator: Any, agent: Agent, artifacts: list[Artifact]
    ) -> list[Artifact] | None:
        """Run on_before_agent_schedule hooks (returns modified artifacts or None to block).

        Components execute in priority order, each receiving artifacts from the
        previous component (chaining). If any component returns None, scheduling
        is blocked.

        Args:
            orchestrator: The Flock orchestrator instance
            agent: The target agent
            artifacts: List of artifacts to schedule

        Returns:
            Modified artifacts list or None if scheduling blocked
        """
        current_artifacts = artifacts

        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            self._logger.debug(
                f"Running on_before_agent_schedule: component={comp_name}, "
                f"agent={agent.name}, artifact_count={len(current_artifacts)}"
            )

            try:
                result = await component.on_before_agent_schedule(
                    orchestrator, agent, current_artifacts
                )

                if result is None:
                    self._logger.info(
                        f"Agent scheduling blocked by component: component={comp_name}, "
                        f"agent={agent.name}"
                    )
                    return None

                current_artifacts = result
            except Exception as e:
                self._logger.exception(
                    f"Component hook failed: component={comp_name}, "
                    f"hook=on_before_agent_schedule, error={e!s}"
                )
                raise

        return current_artifacts

    async def run_agent_scheduled(
        self,
        orchestrator: Any,
        agent: Agent,
        artifacts: list[Artifact],
        task: Task[Any],
    ) -> None:
        """Run on_agent_scheduled hooks (notification only, non-blocking).

        Components execute in priority order. Exceptions are logged but don't
        prevent other components from executing or block scheduling.

        Args:
            orchestrator: The Flock orchestrator instance
            agent: The scheduled agent
            artifacts: List of artifacts for the agent
            task: The asyncio task for agent execution
        """
        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            self._logger.debug(
                f"Running on_agent_scheduled: component={comp_name}, "
                f"agent={agent.name}, artifact_count={len(artifacts)}"
            )

            try:
                await component.on_agent_scheduled(orchestrator, agent, artifacts, task)
            except Exception as e:
                self._logger.warning(
                    f"Component notification hook failed (non-critical): "
                    f"component={comp_name}, hook=on_agent_scheduled, error={e!s}"
                )
                # Don't propagate - this is a notification hook

    async def run_idle(self, orchestrator: Any) -> None:
        """Run on_orchestrator_idle hooks when orchestrator becomes idle.

        Components execute in priority order. Exceptions are logged but don't
        prevent other components from executing.

        Args:
            orchestrator: The Flock orchestrator instance
        """
        self._logger.debug(
            f"Running on_orchestrator_idle hooks: component_count={len(self._components)}"
        )

        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            try:
                await component.on_orchestrator_idle(orchestrator)
            except Exception as e:
                self._logger.warning(
                    f"Component idle hook failed (non-critical): "
                    f"component={comp_name}, hook=on_orchestrator_idle, error={e!s}"
                )

    async def run_shutdown(self, orchestrator: Any) -> None:
        """Run on_shutdown hooks when orchestrator shuts down.

        Components execute in priority order. Exceptions are logged but don't
        prevent shutdown of other components (best-effort cleanup).

        Args:
            orchestrator: The Flock orchestrator instance
        """
        self._logger.info(
            f"Shutting down {len(self._components)} orchestrator components"
        )

        for component in self._components:
            comp_name = component.name or component.__class__.__name__
            self._logger.debug(f"Shutting down component: name={comp_name}")

            try:
                await component.on_shutdown(orchestrator)
            except Exception as e:
                self._logger.exception(
                    f"Component shutdown failed: component={comp_name}, "
                    f"hook=on_shutdown, error={e!s}"
                )
                # Continue shutting down other components


__all__ = ["ComponentRunner"]
