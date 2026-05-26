# src/flock/core/util/hydrator.py (Revised - Simpler)

import asyncio
import json
from typing import (
    Any,
    TypeVar,
    get_type_hints,
)

from pydantic import BaseModel

# Import necessary Flock components
from flock.core import Flock, FlockFactory
from flock.core.logging.logging import get_logger

# Import helper to format type hints back to strings
from flock.core.serialization.serialization_utils import _format_type_to_string

logger = get_logger("hydrator")
T = TypeVar("T", bound=BaseModel)


def flockclass(model: str = "openai/gpt-4o", agent_description: str | None = None):
    """Decorator to add a .hydrate() method to a Pydantic class.
    Leverages a dynamic Flock agent to fill missing (None) fields.

    Args:
        model: The default LLM model identifier to use for hydration.
        agent_description: An optional description for the dynamically created agent.
    """

    def decorator(cls: type[T]) -> type[T]:
        if not issubclass(cls, BaseModel):
            raise TypeError(
                "@flockclass can only decorate Pydantic BaseModel subclasses."
            )

        # Store metadata on the class
        setattr(cls, "__flock_model__", model)
        setattr(cls, "__flock_agent_description__", agent_description)

        # --- Attach the async hydrate method directly ---
        async def hydrate_async(self) -> T:
            """Hydrates the object by filling None fields using a dynamic Flock agent.
            Uses existing non-None fields as input context.
            Returns the hydrated object (self).
            """
            class_name = self.__class__.__name__
            logger.info(f"Starting hydration for instance of {class_name}")

            # Get field information
            all_fields, type_hints = _get_model_fields(self, class_name)
            if all_fields is None or type_hints is None:
                return self  # Return early if field introspection failed

            # Identify existing and missing fields
            existing_data, missing_fields = _identify_fields(self, all_fields)

            if not missing_fields:
                logger.info(f"No fields to hydrate for {class_name} instance.")
                return self

            logger.debug(f"{class_name}: Fields to hydrate: {missing_fields}")
            logger.debug(
                f"{class_name}: Existing data for context: {json.dumps(existing_data, default=str)}"
            )

            # Create agent signatures
            input_str, output_str, input_parts = _build_agent_signatures(
                existing_data,
                missing_fields,
                type_hints,
                all_fields,
                class_name,
            )

            # Create and run agent
            result = await _run_hydration_agent(
                self,
                input_str,
                output_str,
                input_parts,
                existing_data,
                class_name,
            )
            if result is None:
                return self  # Return early if agent run failed

            # Update object fields with results
            _update_fields_with_results(self, result, missing_fields, class_name)

            return self

        # --- Attach the sync hydrate method directly ---
        def hydrate(self) -> T:
            """Synchronous wrapper for the async hydrate method."""
            try:
                # Try to get the current running loop
                loop = asyncio.get_running_loop()

                # If we reach here, there is a running loop
                if loop.is_running():
                    # This runs the coroutine in the existing loop from a different thread
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, hydrate_async(self))
                        return future.result()
                else:
                    # There's a loop but it's not running
                    return loop.run_until_complete(hydrate_async(self))

            except RuntimeError:  # No running loop
                # If no loop is running, create a new one and run our coroutine
                return asyncio.run(hydrate_async(self))

        # Attach the methods to the class
        setattr(cls, "hydrate_async", hydrate_async)
        setattr(cls, "hydrate", hydrate)
        setattr(cls, "hydrate_sync", hydrate)  # Alias for backward compatibility

        logger.debug(f"Attached hydrate methods to class {cls.__name__}")
        return cls

    return decorator


def _get_model_fields(
    obj: BaseModel, class_name: str
) -> tuple[dict | None, dict | None]:
    """Extracts field information from a Pydantic model, handling v1/v2 compatibility."""
    try:
        if hasattr(obj, "model_fields"):  # Pydantic v2
            all_fields = obj.model_fields
            type_hints = {name: field.annotation for name, field in all_fields.items()}
        else:  # Pydantic v1 fallback
            type_hints = get_type_hints(obj.__class__)
            all_fields = getattr(obj, "__fields__", {name: None for name in type_hints})
        return all_fields, type_hints
    except Exception as e:
        logger.error(
            f"Could not get fields/type hints for {class_name}: {e}",
            exc_info=True,
        )
        return None, None


def _identify_fields(
    obj: BaseModel, all_fields: dict
) -> tuple[dict[str, Any], list[str]]:
    """Identifies existing (non-None) and missing fields in the object."""
    existing_data: dict[str, Any] = {}
    missing_fields: list[str] = []

    for field_name in all_fields:
        if hasattr(obj, field_name):  # Check if attribute exists
            value = getattr(obj, field_name)
            if value is not None:
                existing_data[field_name] = value
            else:
                missing_fields.append(field_name)

    return existing_data, missing_fields


def _build_agent_signatures(
    existing_data: dict[str, Any],
    missing_fields: list[str],
    type_hints: dict,
    all_fields: dict,
    class_name: str,
) -> tuple[str, str, list]:
    """Builds input and output signatures for the dynamic agent."""
    # Input signature based on existing data
    input_parts = []
    for name in existing_data:
        field_type = type_hints.get(name, Any)
        type_str = _format_type_to_string(field_type)
        field_info = all_fields.get(name)
        field_desc = getattr(field_info, "description", "")
        if field_desc:
            input_parts.append(f"{name}: {type_str} | {field_desc}")
        else:
            input_parts.append(f"{name}: {type_str}")

    input_str = (
        ", ".join(input_parts)
        if input_parts
        else "context_info: dict | Optional context if no fields have values"
    )

    # Output signature based on missing fields
    output_parts = []
    for name in missing_fields:
        field_type = type_hints.get(name, Any)
        type_str = _format_type_to_string(field_type)
        field_info = all_fields.get(name)
        field_desc = getattr(field_info, "description", "")
        if field_desc:
            output_parts.append(f"{name}: {type_str} | {field_desc}")
        else:
            output_parts.append(f"{name}: {type_str}")

    output_str = ", ".join(output_parts)

    return input_str, output_str, input_parts


async def _run_hydration_agent(
    obj: BaseModel,
    input_str: str,
    output_str: str,
    input_parts: list,
    existing_data: dict[str, Any],
    class_name: str,
) -> dict[str, Any] | None:
    """Creates and runs a dynamic Flock agent to hydrate the object."""
    # Agent configuration
    agent_name = f"hydrator_{class_name}_{id(obj)}"
    description = (
        getattr(obj, "__flock_agent_description__", None)
        or f"Agent that completes missing data for a {class_name} object."
    )
    hydration_model = getattr(obj, "__flock_model__", "openai/gpt-4o")

    logger.debug(f"Creating dynamic agent '{agent_name}' for {class_name}")
    logger.debug(f"  Input Schema: {input_str}")
    logger.debug(f"  Output Schema: {output_str}")

    try:
        # Create agent
        dynamic_agent = FlockFactory.create_default_agent(
            name=agent_name,
            description=description,
            input=input_str,
            output=output_str,
            model=hydration_model,
            no_output=True,
            use_cache=False,
        )

        # Create temporary Flock
        temp_flock = Flock(
            name=f"temp_hydrator_flock_{agent_name}",
            model=hydration_model,
            show_flock_banner=False,
        )
        temp_flock.add_agent(dynamic_agent)

        # Prepare input data
        agent_input_data = (
            existing_data
            if input_parts
            else {"context_info": {"object_type": class_name}}
        )

        logger.info(f"Running hydration agent '{agent_name}' for {class_name}...")

        # Run agent
        result = await temp_flock.run_async(
            start_agent=agent_name,
            input=agent_input_data,
            box_result=False,
        )
        logger.info(f"Hydration agent returned for {class_name}: {list(result.keys())}")

        return result

    except Exception as e:
        logger.error(
            f"Hydration agent creation or run failed for {class_name}: {e}",
            exc_info=True,
        )
        return None


def _update_fields_with_results(
    obj: BaseModel,
    result: dict[str, Any],
    missing_fields: list[str],
    class_name: str,
) -> None:
    """Updates object fields with results from the hydration agent."""
    updated_count = 0
    for field_name in missing_fields:
        if field_name in result:
            try:
                setattr(obj, field_name, result[field_name])
                logger.debug(
                    f"Hydrated field '{field_name}' in {class_name} with value: {getattr(obj, field_name)}"
                )
                updated_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to set hydrated value for '{field_name}' in {class_name}: {e}. Value received: {result[field_name]}"
                )
        else:
            logger.warning(
                f"Hydration result missing expected field for {class_name}: '{field_name}'"
            )

    logger.info(
        f"Hydration complete for {class_name}. Updated {updated_count}/{len(missing_fields)} fields."
    )


# Ensure helper functions are available
# from flock.core.serialization.serialization_utils import _format_type_to_string
