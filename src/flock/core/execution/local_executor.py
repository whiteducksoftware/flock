# src/your_package/core/execution/local_executor.py
from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger
from flock.workflow.activities import (
    run_agent,  # This should be the local activity function
)

logger = get_logger("flock")


async def run_local_workflow(
    context: FlockContext, box_result: bool = True
) -> dict:
    """Execute the agent workflow locally (for debugging).

    Args:
        context: The FlockContext instance with state and history.
        output_formatter: Formatter options for displaying results.
        box_result: If True, wraps the result in a Box for nicer display.

    Returns:
        A dictionary containing the workflow result.
    """
    logger.info("Running local debug workflow")
    result = await run_agent(context)
    if box_result:
        from box import Box

        logger.debug("Boxing result")
        return Box(result)
    return result
