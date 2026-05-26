# src/flock/routers/list_generator/iterative_list_router.py (New File)

from typing import Any

from pydantic import Field

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_registry import flock_component
from flock.core.flock_router import (
    FlockRouter,
    FlockRouterConfig,
    HandOffRequest,
)
from flock.core.logging.logging import get_logger

# Need signature utils

logger = get_logger("router.list_generator")


class IterativeListGeneratorRouterConfig(FlockRouterConfig):
    target_list_field: str = Field(
        ...,
        description="Name of the final list output field (e.g., 'chapters').",
    )
    item_output_field: str = Field(
        ...,
        description="Name of the single item output field for each iteration (e.g., 'chapter').",
    )
    context_input_field: str = Field(
        default="previous_items",
        description="Input field name for passing back generated items (e.g., 'existing_chapters').",
    )
    max_iterations: int = Field(
        default=10, description="Maximum number of items to generate."
    )
    # More advanced: termination_condition: Optional[Callable] = None
    # Store iteration state in context under this prefix
    context_state_prefix: str = Field(
        default="flock.iterator_state_",
        description="Prefix for context keys storing iteration state.",
    )

    # Field to extract item type from target_list_field signature
    # This might require parsing the original agent's output signature
    # item_type_str: Optional[str] = None # e.g., 'dict[str, str]' or 'MyChapterType'


@flock_component(config_class=IterativeListGeneratorRouterConfig)
class IterativeListGeneratorRouter(FlockRouter):
    name: str = "iterative_list_generator"
    config: IterativeListGeneratorRouterConfig = Field(
        default_factory=IterativeListGeneratorRouterConfig
    )

    # Helper to get state keys
    def _get_state_keys(self, agent_name: str) -> tuple[str, str]:
        prefix = self.config.context_state_prefix
        list_key = f"{prefix}{agent_name}_{self.config.target_list_field}"
        count_key = f"{prefix}{agent_name}_iteration_count"
        return list_key, count_key

    async def route(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        context: FlockContext,
    ) -> HandOffRequest:
        list_key, count_key = self._get_state_keys(current_agent.name)

        # --- State Initialization (First Run) ---
        if count_key not in context.state:
            logger.debug(
                f"Initializing iterative list generation for '{self.config.target_list_field}' in agent '{current_agent.name}'."
            )
            context.set_variable(count_key, 0)
            context.set_variable(list_key, [])
            # Modify agent signature for the *first* iteration (remove context_input_field, use item_output_field)
            # This requires modifying the agent's internal state or creating a temporary one.
            # Let's try modifying the context passed to the *next* run instead.
            context.set_variable(
                f"{current_agent.name}.next_run_output_field",
                self.config.item_output_field,
            )
            context.set_variable(
                f"{current_agent.name}.next_run_input_fields_to_exclude",
                {self.config.context_input_field},
            )

        # --- Process Result of Previous Iteration ---
        iteration_count = context.get_variable(count_key, 0)
        generated_items = context.get_variable(list_key, [])

        # Get the single item generated in the *last* run
        # The result dict should contain the 'item_output_field' if it wasn't the very first run
        new_item = result.get(self.config.item_output_field)

        if (
            new_item is not None and iteration_count > 0
        ):  # Add item from previous run (not the init run)
            generated_items.append(new_item)
            context.set_variable(list_key, generated_items)  # Update context
            logger.info(
                f"Added item #{iteration_count} to list '{self.config.target_list_field}' for agent '{current_agent.name}'."
            )
        elif iteration_count > 0:
            logger.warning(
                f"Iteration {iteration_count} for agent '{current_agent.name}' did not produce expected output field '{self.config.item_output_field}'."
            )
            # Decide how to handle: stop, retry, continue? Let's continue for now.

        # Increment iteration count *after* processing the result of the previous one
        current_iteration = iteration_count + 1
        context.set_variable(count_key, current_iteration)

        # --- Termination Check ---
        if current_iteration > self.config.max_iterations:
            logger.info(
                f"Max iterations ({self.config.max_iterations}) reached for '{self.config.target_list_field}' in agent '{current_agent.name}'. Finalizing."
            )
            # Clean up state
            del context.state[count_key]
            # Final result should be the list itself under the target_list_field key
            final_result = {self.config.target_list_field: generated_items}
            # Handoff with empty next_agent to stop, but potentially override the *result*
            # This is tricky. Routers usually decide the *next agent*, not the *final output*.
            # Maybe the router should just signal termination, and the Flock run loop handles assembling the final output?
            # Let's assume the router signals termination by returning next_agent=""
            # The final list is already in the context under list_key.
            # A final "AssemblerAgent" could read this context variable.
            # OR we modify the HandOffRequest:
            return HandOffRequest(
                next_agent="", final_output_override=final_result
            )  # Needs HandOffRequest modification

        # --- Prepare for Next Iteration ---
        logger.info(
            f"Routing back to agent '{current_agent.name}' for item #{current_iteration} of '{self.config.target_list_field}'."
        )

        # The agent needs the context (previously generated items) and the original inputs again.
        # We will pass the generated items via the context_input_field.
        # The original inputs (like story_outline) should still be in the context.
        next_input_override = {
            self.config.context_input_field: generated_items  # Pass the list back
        }

        # Modify agent signature for the *next* iteration (add context_input_field, use item_output_field)
        # This is the trickiest part - how to modify the agent's perceived signature for the next run?
        # Option 1: Pass overrides via HandOffRequest (cleanest)
        next_signature_input = f"{current_agent.input}, {self.config.context_input_field}: list | Previously generated items"  # Needs smarter joining
        next_signature_output = (
            self.config.item_output_field
        )  # Only ask for one item

        # This requires HandOffRequest and Flock execution loop to support signature overrides
        return HandOffRequest(
            next_agent=current_agent.name,
            output_to_input_merge_strategy="add",  # Add the context_input_field to existing context
            input_override=next_input_override,  # Provide the actual list data
            # --- Hypothetical Overrides ---
            next_run_input_signature_override=next_signature_input,
            next_run_output_signature_override=next_signature_output,
            # -----------------------------
        )
