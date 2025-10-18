"""Agent component lifecycle management - hook execution and coordination.

Phase 4: Extracted from agent.py to organize component hook execution logic.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from flock.logging.logging import get_logger


if TYPE_CHECKING:
    from flock.components import AgentComponent, EngineComponent
    from flock.core import Agent
    from flock.core.artifacts import Artifact
    from flock.utils.runtime import Context, EvalInputs, EvalResult

logger = get_logger(__name__)


class ComponentLifecycle:
    """Manages agent component lifecycle hook execution.

    This module handles all component hook execution during agent lifecycle:
    - on_initialize
    - on_pre_consume
    - on_pre_evaluate
    - on_post_evaluate
    - on_post_publish
    - on_error
    - on_terminate
    """

    def __init__(self, agent_name: str):
        """Initialize ComponentLifecycle for a specific agent.

        Args:
            agent_name: Name of the agent (for logging)
        """
        self._agent_name = agent_name
        self._logger = logging.getLogger(__name__)

    def _component_display_name(
        self, component: AgentComponent | EngineComponent
    ) -> str:
        """Get display name for component logging."""
        return getattr(component, "name", None) or component.__class__.__name__

    async def run_initialize(
        self,
        agent: Agent,
        ctx: Context,
        utilities: list[AgentComponent],
        engines: list[EngineComponent],
    ) -> None:
        """Execute on_initialize hooks for all components.

        Args:
            agent: Agent instance
            ctx: Execution context
            utilities: List of utility components
            engines: List of engine components

        Raises:
            Exception: If any component initialization fails
        """
        for component in utilities:
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent initialize: agent={self._agent_name}, component={comp_name}, priority={priority}"
            )
            try:
                await component.on_initialize(agent, ctx)
            except Exception as exc:
                logger.exception(
                    f"Agent initialize failed: agent={self._agent_name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise

        for engine in engines:
            await engine.on_initialize(agent, ctx)

    async def run_pre_consume(
        self,
        agent: Agent,
        ctx: Context,
        inputs: list[Artifact],
        utilities: list[AgentComponent],
    ) -> list[Artifact]:
        """Execute on_pre_consume hooks, allowing components to transform inputs.

        Args:
            agent: Agent instance
            ctx: Execution context
            inputs: Input artifacts to be consumed
            utilities: List of utility components

        Returns:
            Transformed input artifacts after all components process them

        Raises:
            Exception: If any component pre_consume hook fails
        """
        current = inputs
        for component in utilities:
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent pre_consume: agent={self._agent_name}, component={comp_name}, "
                f"priority={priority}, input_count={len(current)}"
            )
            try:
                current = await component.on_pre_consume(agent, ctx, current)
            except Exception as exc:
                logger.exception(
                    f"Agent pre_consume failed: agent={self._agent_name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise
        return current

    async def run_pre_evaluate(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs,
        utilities: list[AgentComponent],
    ) -> EvalInputs:
        """Execute on_pre_evaluate hooks, allowing components to transform evaluation inputs.

        Args:
            agent: Agent instance
            ctx: Execution context
            inputs: Evaluation inputs with artifacts and state
            utilities: List of utility components

        Returns:
            Transformed evaluation inputs after all components process them

        Raises:
            Exception: If any component pre_evaluate hook fails
        """
        current = inputs
        for component in utilities:
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent pre_evaluate: agent={self._agent_name}, component={comp_name}, "
                f"priority={priority}, artifact_count={len(current.artifacts)}"
            )
            try:
                current = await component.on_pre_evaluate(agent, ctx, current)
            except Exception as exc:
                logger.exception(
                    f"Agent pre_evaluate failed: agent={self._agent_name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise
        return current

    async def run_post_evaluate(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs,
        result: EvalResult,
        utilities: list[AgentComponent],
    ) -> EvalResult:
        """Execute on_post_evaluate hooks, allowing components to transform results.

        Args:
            agent: Agent instance
            ctx: Execution context
            inputs: Original evaluation inputs
            result: Evaluation result to be transformed
            utilities: List of utility components

        Returns:
            Transformed evaluation result after all components process it

        Raises:
            Exception: If any component post_evaluate hook fails
        """
        current = result
        for component in utilities:
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent post_evaluate: agent={self._agent_name}, component={comp_name}, "
                f"priority={priority}, artifact_count={len(current.artifacts)}"
            )
            try:
                current = await component.on_post_evaluate(agent, ctx, inputs, current)
            except Exception as exc:
                logger.exception(
                    f"Agent post_evaluate failed: agent={self._agent_name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise
        return current

    async def run_post_publish(
        self,
        agent: Agent,
        ctx: Context,
        artifacts: Sequence[Artifact],
        utilities: list[AgentComponent],
    ) -> None:
        """Execute on_post_publish hooks for each published artifact.

        Args:
            agent: Agent instance
            ctx: Execution context
            artifacts: Published artifacts
            utilities: List of utility components

        Raises:
            Exception: If any component post_publish hook fails
        """
        for artifact in artifacts:
            for component in utilities:
                comp_name = self._component_display_name(component)
                priority = getattr(component, "priority", 0)
                logger.debug(
                    f"Agent post_publish: agent={self._agent_name}, component={comp_name}, "
                    f"priority={priority}, artifact_id={artifact.id}"
                )
                try:
                    await component.on_post_publish(agent, ctx, artifact)
                except Exception as exc:
                    logger.exception(
                        f"Agent post_publish failed: agent={self._agent_name}, component={comp_name}, "
                        f"priority={priority}, artifact_id={artifact.id}, error={exc!s}"
                    )
                    raise

    async def run_error(
        self,
        agent: Agent,
        ctx: Context,
        error: Exception,
        utilities: list[AgentComponent],
        engines: list[EngineComponent],
    ) -> None:
        """Execute on_error hooks for all components.

        Args:
            agent: Agent instance
            ctx: Execution context
            error: Exception that occurred
            utilities: List of utility components
            engines: List of engine components

        Raises:
            Exception: If any component error hook fails
        """
        for component in utilities:
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)

            # Python 3.12+ TaskGroup raises BaseExceptionGroup - extract sub-exceptions
            error_detail = str(error)
            if isinstance(error, BaseExceptionGroup):
                sub_exceptions = [f"{type(e).__name__}: {e}" for e in error.exceptions]
                error_detail = f"{error!s} - Sub-exceptions: {sub_exceptions}"

            logger.debug(
                f"Agent error hook: agent={self._agent_name}, component={comp_name}, "
                f"priority={priority}, error={error_detail}"
            )
            try:
                await component.on_error(agent, ctx, error)
            except Exception as exc:
                logger.exception(
                    f"Agent error hook failed: agent={self._agent_name}, component={comp_name}, "
                    f"priority={priority}, original_error={error!s}, hook_error={exc!s}"
                )
                raise

        for engine in engines:
            await engine.on_error(agent, ctx, error)

    async def run_terminate(
        self,
        agent: Agent,
        ctx: Context,
        utilities: list[AgentComponent],
        engines: list[EngineComponent],
    ) -> None:
        """Execute on_terminate hooks for all components.

        Args:
            agent: Agent instance
            ctx: Execution context
            utilities: List of utility components
            engines: List of engine components

        Raises:
            Exception: If any component termination fails
        """
        for component in utilities:
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent terminate: agent={self._agent_name}, component={comp_name}, priority={priority}"
            )
            try:
                await component.on_terminate(agent, ctx)
            except Exception as exc:
                logger.exception(
                    f"Agent terminate failed: agent={self._agent_name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise

        for engine in engines:
            await engine.on_terminate(agent, ctx)


__all__ = ["ComponentLifecycle"]
