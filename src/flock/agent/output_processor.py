"""Agent output processing - validation, filtering, and artifact creation.

Phase 4: Extracted from agent.py to eliminate C-rated complexity in _make_outputs_for_group.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from flock.core.artifacts import Artifact
from flock.logging.logging import get_logger
from flock.registry import type_registry
from flock.utils.runtime import Context, EvalResult
from flock.utils.type_resolution import TypeResolutionHelper


if TYPE_CHECKING:
    from flock.agent import AgentOutput, OutputGroup


logger = get_logger(__name__)


class OutputProcessor:
    """Handles agent output validation, filtering, and artifact creation.

    This module encapsulates all output processing logic including:
    - Engine contract validation (expected vs actual artifact counts)
    - WHERE filtering (reduces artifacts based on predicates)
    - VALIDATE checks (fail-fast on validation errors)
    - Dynamic visibility resolution
    - Artifact matching and payload extraction
    """

    def __init__(self, agent_name: str):
        """Initialize OutputProcessor for a specific agent.

        Args:
            agent_name: Name of the agent (for error messages and logging)
        """
        self._agent_name = agent_name
        self._logger = logging.getLogger(__name__)

    async def make_outputs_for_group(
        self,
        ctx: Context,
        result: EvalResult,
        output_group: OutputGroup,
    ) -> list[Artifact]:
        """Phase 3/5: Validate, filter, and create artifacts for specific OutputGroup.

        This function:
        1. Validates that the engine fulfilled its contract (produced expected count)
        2. Applies WHERE filtering (reduces artifacts, no error)
        3. Applies VALIDATE checks (raises ValueError if validation fails)
        4. Applies visibility (static or dynamic)
        5. Creates final artifacts with agent metadata

        Args:
            ctx: Context for this group
            result: EvalResult from engine for THIS group
            output_group: OutputGroup defining expected outputs

        Returns:
            List of artifacts matching this group's outputs

        Raises:
            ValueError: If engine violated contract or validation failed
        """
        produced: list[Artifact] = []

        for output_decl in output_group.outputs:
            # 1. Find ALL matching artifacts for this type
            expected_canonical = type_registry.resolve_name(output_decl.spec.type_name)

            matching_artifacts: list[Artifact] = []
            for artifact in result.artifacts:
                artifact_canonical = TypeResolutionHelper.safe_resolve(
                    type_registry, artifact.type
                )
                if artifact_canonical == expected_canonical:
                    matching_artifacts.append(artifact)

            # 2. STRICT VALIDATION: Engine must produce exactly what was promised
            # (This happens BEFORE filtering so engine contract is validated first)
            expected_count = output_decl.count
            actual_count = len(matching_artifacts)

            if actual_count != expected_count:
                raise ValueError(
                    f"Engine contract violation in agent '{self._agent_name}': "
                    f"Expected {expected_count} artifact(s) of type '{output_decl.spec.type_name}', "
                    f"but engine produced {actual_count}. "
                    f"Check your engine implementation to ensure it generates the correct number of outputs."
                )

            # 3. Apply WHERE filtering (Phase 5)
            # Filtering reduces the number of published artifacts (this is intentional)
            # NOTE: Predicates expect Pydantic model instances, not dicts
            model_cls = type_registry.resolve(output_decl.spec.type_name)

            if output_decl.filter_predicate:
                original_count = len(matching_artifacts)
                filtered = []
                for a in matching_artifacts:
                    # Reconstruct Pydantic model from payload dict
                    model_instance = model_cls(**a.payload)
                    if output_decl.filter_predicate(model_instance):
                        filtered.append(a)
                matching_artifacts = filtered
                logger.debug(
                    f"Agent {self._agent_name}: WHERE filter reduced artifacts from "
                    f"{original_count} to {len(matching_artifacts)} for type {output_decl.spec.type_name}"
                )

            # 4. Apply VALIDATE checks (Phase 5)
            # Validation failures raise errors (fail-fast)
            if output_decl.validate_predicate:
                if callable(output_decl.validate_predicate):
                    # Single predicate
                    for artifact in matching_artifacts:
                        # Reconstruct Pydantic model from payload dict
                        model_instance = model_cls(**artifact.payload)
                        if not output_decl.validate_predicate(model_instance):
                            raise ValueError(
                                f"Validation failed for {output_decl.spec.type_name} "
                                f"in agent '{self._agent_name}'"
                            )
                elif isinstance(output_decl.validate_predicate, list):
                    # List of (callable, error_msg) tuples
                    for artifact in matching_artifacts:
                        # Reconstruct Pydantic model from payload dict
                        model_instance = model_cls(**artifact.payload)
                        for check, error_msg in output_decl.validate_predicate:
                            if not check(model_instance):
                                raise ValueError(
                                    f"{error_msg}: {output_decl.spec.type_name}"
                                )

            # 5. Apply visibility and create artifacts (Phase 5)
            for artifact_from_engine in matching_artifacts:
                metadata = {
                    "correlation_id": ctx.correlation_id,
                    "artifact_id": artifact_from_engine.id,  # Preserve engine's ID
                }

                # Determine visibility (static or dynamic)
                visibility = output_decl.default_visibility
                if callable(visibility):
                    # Dynamic visibility based on artifact content
                    # Reconstruct Pydantic model from payload dict
                    model_instance = model_cls(**artifact_from_engine.payload)
                    visibility = visibility(model_instance)

                # Override metadata visibility
                metadata["visibility"] = visibility

                # Re-wrap the artifact with agent metadata
                artifact = output_decl.apply(
                    artifact_from_engine.payload,
                    produced_by=self._agent_name,
                    metadata=metadata,
                )
                produced.append(artifact)
                # Phase 6 SECURITY FIX: REMOVED publishing - orchestrator now handles it
                # This fixes Vulnerability #2 (WRITE Bypass) - agents can no longer publish directly
                # await ctx.board.publish(artifact)

        return produced

    async def make_outputs(
        self, ctx: Context, result: EvalResult, output_groups: list[OutputGroup]
    ) -> list[Artifact]:
        """Output creation method for all output groups.

        This method processes all output groups from a single engine evaluation.

        Args:
            ctx: Execution context
            result: EvalResult from engine
            output_groups: All output groups for the agent

        Returns:
            List of produced artifacts
        """
        if not output_groups:
            # Utility agents may not publish anything
            return list(result.artifacts)

        produced: list[Artifact] = []

        # For Phase 2: Iterate ALL output_groups (even though we only have 1 engine call)
        # Phase 3 will modify this to call engine once PER group
        for output_group in output_groups:
            for output_decl in output_group.outputs:
                # Phase 6: Find the matching artifact from engine result to preserve its ID
                matching_artifact = self.find_matching_artifact(output_decl, result)

                payload = self.select_payload(output_decl, result)
                if payload is None:
                    continue
                metadata = {
                    "correlation_id": ctx.correlation_id,
                }

                # Phase 6: Preserve artifact ID from engine (for streaming message preview)
                if matching_artifact:
                    metadata["artifact_id"] = matching_artifact.id

                artifact = output_decl.apply(
                    payload, produced_by=self._agent_name, metadata=metadata
                )
                produced.append(artifact)
                # Phase 6: REMOVED publishing - orchestrator now handles it
                # await ctx.board.publish(artifact)

        return produced

    def prepare_group_context(
        self, ctx: Context, group_idx: int, output_group: OutputGroup
    ) -> Context:
        """Phase 3: Prepare context specific to this OutputGroup.

        Creates a modified context for this group's engine call, potentially
        with group-specific instructions or metadata.

        Args:
            ctx: Base context
            group_idx: Index of this group (0-based)
            output_group: The OutputGroup being processed

        Returns:
            Context for this group (may be the same instance or modified)
        """
        # For now, return the same context
        # Phase 4 will add group-specific system prompts here
        # Future: ctx.clone() and add group_description to system prompt
        return ctx

    def find_matching_artifact(
        self, output_decl: AgentOutput, result: EvalResult
    ) -> Artifact | None:
        """Phase 6: Find artifact from engine result that matches this output declaration.

        Returns the artifact object (with its ID) so we can preserve it when creating
        the final published artifact. This ensures streaming events use the same ID.

        Args:
            output_decl: Output declaration to match
            result: Engine result containing artifacts

        Returns:
            Matching artifact or None if not found
        """
        if not result.artifacts:
            return None

        # Normalize the expected type name to canonical form
        expected_canonical = type_registry.resolve_name(output_decl.spec.type_name)

        for artifact in result.artifacts:
            # Normalize artifact type name to canonical form for comparison
            artifact_canonical = TypeResolutionHelper.safe_resolve(
                type_registry, artifact.type
            )
            if artifact_canonical == expected_canonical:
                return artifact

        return None

    def select_payload(
        self, output_decl: AgentOutput, result: EvalResult
    ) -> dict[str, Any] | None:
        """Extract payload from engine result for output declaration.

        Args:
            output_decl: Output declaration defining expected type
            result: Engine result containing artifacts

        Returns:
            Payload dict or None if not found
        """
        # Normalize the expected type name to canonical form
        expected_canonical = type_registry.resolve_name(output_decl.spec.type_name)

        # Try to find payload in artifacts first
        if result.artifacts:
            for artifact in result.artifacts:
                # Normalize artifact type name to canonical form for comparison
                artifact_canonical = TypeResolutionHelper.safe_resolve(
                    type_registry, artifact.type
                )
                if artifact_canonical == expected_canonical:
                    return artifact.payload

        # Fallback to state entries keyed by type name
        maybe_data = result.state.get(output_decl.spec.type_name)
        if isinstance(maybe_data, dict):
            return maybe_data
        return None


__all__ = ["OutputProcessor"]
