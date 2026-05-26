# src/your_package/core/execution/temporal_executor.py

import asyncio  # Import asyncio
from typing import TYPE_CHECKING, Any

from temporalio.worker import Worker  # Import Worker

if TYPE_CHECKING:
    from flock.core.flock import Flock  # Import Flock for type hinting

from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_RUN_ID
from flock.core.logging.logging import get_logger
from flock.workflow.agent_execution_activity import (
    determine_next_agent,
    execute_single_agent,
)
from flock.workflow.temporal_config import (
    TemporalRetryPolicyConfig,
    TemporalWorkflowConfig,
)
from flock.workflow.temporal_setup import create_temporal_client, setup_worker

logger = get_logger("flock")


async def run_temporal_workflow(
    flock_instance: "Flock",  # Accept Flock instance
    context: FlockContext,
    box_result: bool = True,
    memo: dict[str, Any] | None = None,  # Add memo argument
) -> dict:
    """Execute the agent workflow via Temporal for robust, distributed processing.

    Args:
        flock_instance: The Flock instance.
        context: The FlockContext instance with state and history.
        box_result: If True, wraps the result in a Box for nicer display.
        memo: Optional dictionary of metadata to attach to the Temporal workflow.

    Returns:
        A dictionary containing the workflow result.
    """
    try:
        from flock.workflow.flock_workflow import (
            FlockWorkflow,  # Your workflow class
        )

        # Get workflow config from Flock instance or use defaults
        wf_config = flock_instance.temporal_config or TemporalWorkflowConfig()

        logger.debug("Creating Temporal client")
        flock_client = await create_temporal_client()

        # Determine if we need to manage an in-process worker
        start_worker_locally = flock_instance.temporal_start_in_process_worker

        # Setup worker instance
        worker: Worker | None = None
        worker_task: asyncio.Task | None = None

        if start_worker_locally:
            logger.info(
                f"Setting up temporary in-process worker for task queue '{wf_config.task_queue}'"
            )
            worker = await setup_worker(
                flock_client,  # Pass the client
                wf_config.task_queue,  # Pass the task queue
                FlockWorkflow,
                [execute_single_agent, determine_next_agent],
            )

            # Run the worker in the background
            worker_task = asyncio.create_task(worker.run())
            logger.info("Temporal worker started in background.")

            # Allow worker time to start polling (heuristic for local testing)
            await asyncio.sleep(2)
        else:
            logger.info(
                "Skipping in-process worker startup. Assuming dedicated workers are running."
            )

        try:
            workflow_id = context.get_variable(FLOCK_RUN_ID)
            logger.info(
                "Executing Temporal workflow",
                workflow_id=workflow_id,
                task_queue=wf_config.task_queue,
            )

            # Prepare the single workflow argument dictionary
            workflow_args_dict = {
                "context_dict": context.model_dump(mode="json"),
                "default_retry_config_dict": (
                    wf_config.default_activity_retry_policy.model_dump(
                        mode="json"
                    )
                    if wf_config.default_activity_retry_policy
                    else TemporalRetryPolicyConfig().model_dump(mode="json")
                ),
            }

            # Start the workflow using start_workflow
            handle = await flock_client.start_workflow(
                FlockWorkflow.run,
                # Pass the single dictionary as the only element in the args list
                args=[workflow_args_dict],
                id=workflow_id,
                task_queue=wf_config.task_queue,
                # Corrected timeout argument names
                execution_timeout=wf_config.workflow_execution_timeout,
                run_timeout=wf_config.workflow_run_timeout,
                memo=memo or {},  # Pass memo if provided
            )

            logger.info(
                "Workflow started, awaiting result...", workflow_id=handle.id
            )
            # Await the result from the handle
            result = await handle.result()
            logger.info("Workflow result received.")

            agent_name = context.get_variable("FLOCK_CURRENT_AGENT")
            logger.debug("Formatting Temporal result", agent=agent_name)

            if box_result:
                from box import Box

                logger.debug("Boxing Temporal result")
                return Box(result)
            return result
        except Exception as e:
            logger.error(
                "Error during Temporal workflow execution or result retrieval",
                error=e,
            )
            raise e  # Re-raise the exception after logging
        finally:
            # Ensure worker is shut down regardless of success or failure
            if (
                start_worker_locally
                and worker
                and worker_task
                and not worker_task.done()
            ):
                logger.info("Shutting down temporal worker...")
                await worker.shutdown()  # Await the shutdown coroutine
                try:
                    await asyncio.wait_for(
                        worker_task, timeout=10.0
                    )  # Wait for task to finish
                    logger.info("Temporal worker shut down gracefully.")
                except asyncio.TimeoutError:
                    logger.warning(
                        "Temporal worker shutdown timed out. Cancelling task."
                    )
                    worker_task.cancel()
                except Exception as shutdown_err:
                    logger.error(
                        f"Error during worker shutdown: {shutdown_err}",
                        exc_info=True,
                    )
    except Exception as e:
        logger.error("Error executing Temporal workflow", error=e)
        raise e
