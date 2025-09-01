from datetime import timedelta
from typing import Any

from temporalio import workflow

# Import activities from the new file
with workflow.unsafe.imports_passed_through():
    from flock.core.context.context import AgentDefinition, FlockContext
    from flock.core.context.context_vars import FLOCK_CURRENT_AGENT
    # HandOffRequest removed - using agent.next_agent directly
    from flock.core.logging.logging import get_logger
    from flock.workflow.agent_execution_activity import (
        determine_next_agent,
        execute_single_agent,
    )
    from flock.workflow.temporal_config import (
        TemporalActivityConfig,
        TemporalRetryPolicyConfig,
    )


logger = get_logger("workflow")


@workflow.defn
class FlockWorkflow:
    # No need for __init__ storing context anymore if passed to run

    @workflow.run
    async def run(self, workflow_args: dict[str, Any]) -> dict:
        # --- Workflow Initialization ---
        # Arguments are packed into a single dictionary
        context_dict = workflow_args["context_dict"]
        default_retry_config_dict = workflow_args["default_retry_config_dict"]

        # Deserialize context and default retry config
        context = FlockContext.from_dict(context_dict)
        default_retry_config = TemporalRetryPolicyConfig.model_validate(
            default_retry_config_dict
        )

        context.workflow_id = workflow.info().workflow_id
        context.workflow_timestamp = workflow.info().start_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        current_agent_name = context.get_variable(FLOCK_CURRENT_AGENT)
        final_result = None
        previous_agent_name = (
            None  # Keep track of the agent that called the current one
        )

        logger.info(
            "Starting workflow execution",
            workflow_id=context.workflow_id,
            start_time=context.workflow_timestamp,
            initial_agent=current_agent_name,
        )

        try:
            while current_agent_name:
                logger.info(
                    "Executing agent activity", agent=current_agent_name
                )

                # --- Determine Activity Settings ---
                agent_def: AgentDefinition | None = (
                    context.get_agent_definition(current_agent_name)
                )
                agent_activity_config: TemporalActivityConfig | None = None
                final_retry_config = (
                    default_retry_config  # Start with the workflow default
                )

                if agent_def and agent_def.agent_data.get(
                    "temporal_activity_config"
                ):
                    try:
                        agent_activity_config = (
                            TemporalActivityConfig.model_validate(
                                agent_def.agent_data["temporal_activity_config"]
                            )
                        )
                        logger.debug(
                            f"Loaded agent-specific temporal config for {current_agent_name}"
                        )
                    except Exception as e:
                        logger.warn(
                            f"Failed to validate agent temporal config for {current_agent_name}: {e}. Using defaults."
                        )

                # Layering logic: Agent config overrides workflow default config
                activity_task_queue = (
                    workflow.info().task_queue
                )  # Default to workflow task queue
                activity_timeout = timedelta(
                    minutes=5
                )  # Fallback default timeout

                if agent_activity_config:
                    activity_task_queue = (
                        agent_activity_config.task_queue or activity_task_queue
                    )
                    activity_timeout = (
                        agent_activity_config.start_to_close_timeout
                        or activity_timeout
                    )
                    if agent_activity_config.retry_policy:
                        final_retry_config = agent_activity_config.retry_policy

                # Convert config to actual Temporal object
                final_retry_policy = final_retry_config.to_temporalio_policy()

                logger.debug(
                    f"Final activity settings for {current_agent_name}: "
                    f"queue='{activity_task_queue}', timeout={activity_timeout}, "
                    f"retries={final_retry_policy.maximum_attempts}"
                )

                # --- Execute the current agent activity ---
                try:
                    agent_result = await workflow.execute_activity(
                        execute_single_agent,
                        args=[current_agent_name, context.model_dump(mode="json")],
                        task_queue=activity_task_queue,
                        start_to_close_timeout=activity_timeout,
                        retry_policy=final_retry_policy,
                    )
                except Exception as e:
                    logger.error("execute_single_agent activity failed", agent=current_agent_name, error=str(e))
                    raise

                # Record the execution in the context history
                # Note: The 'called_from' is the agent *before* this one
                context.record(
                    agent_name=current_agent_name,
                    data=agent_result,
                    timestamp=workflow.now().isoformat(),  # Use deterministic workflow time
                    hand_off=None,  # Will be updated if handoff occurs
                    called_from=previous_agent_name,  # Pass the correct previous agent
                )

                final_result = agent_result  # Store the result of the last successful agent

                logger.info(
                    "Determining next agent activity",
                    current_agent=current_agent_name,
                )
                # --- Determine the next agent (using routing component) ---
                try:
                    next_agent_name = await workflow.execute_activity(
                        determine_next_agent,
                        args=[current_agent_name, agent_result, context.model_dump(mode="json")],
                        start_to_close_timeout=timedelta(minutes=1),
                        retry_policy=default_retry_config.to_temporalio_policy(),
                    )
                except Exception as e:
                    logger.error("determine_next_agent activity failed", agent=current_agent_name, error=str(e))
                    raise

                # Update previous agent name for the next loop iteration
                previous_agent_name = current_agent_name

                if next_agent_name:
                    logger.debug("Next agent received", data=next_agent_name)
                    # Update the last record's handoff information for observability
                    if context.history:
                        context.history[-1].hand_off = {"next_agent": next_agent_name}

                    # Set the next agent
                    current_agent_name = next_agent_name
                    context.set_variable(FLOCK_CURRENT_AGENT, current_agent_name)
                    logger.info("Next agent set", agent=current_agent_name)
                else:
                    logger.info("No next agent, workflow terminating.")
                    current_agent_name = None

            # --- Workflow Completion ---
            logger.success(
                "Workflow completed successfully",
                final_agent=previous_agent_name,
            )
            context.set_variable(
                "flock.result",
                {
                    "result": final_result,  # Return the last agent's result
                    "success": True,
                },
            )
            return final_result  # Return the actual result of the last agent

        except Exception as e:
            # Catch exceptions from activities (e.g., after retries fail) or workflow logic errors
            logger.exception(f"Workflow execution failed: {e!r}")
            try:
                from temporalio.exceptions import ActivityError
                if isinstance(e, ActivityError) and getattr(e, "cause", None) is not None:
                    logger.error(f"ActivityError cause: {e.cause!r}")
            except Exception:
                pass
            context.set_variable(
                "flock.result",
                {
                    "result": f"Workflow failed: {e}",
                    "success": False,
                },
            )
            # It's often better to let Temporal record the failure status
            # by re-raising the exception rather than returning a custom error dict.
            # However, returning the context might be useful for debugging.
            # Consider re-raising: raise
            return context.model_dump(
                mode="json"
            )  # Return context state on failure
