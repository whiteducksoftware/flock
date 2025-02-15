import asyncio
import uuid
from datetime import timedelta

from temporalio.client import Client, WorkflowIDReusePolicy
from temporalio.service import RPCError

from flock.core.flock_agent import FlockAgent
from flock.core.context.context import FlockContext
from flock.core.logging import flock_logger, live_update_handler, performance_handler


class TemporalLoggingAgent(FlockAgent):
    """Demo agent that showcases logging with Temporal integration."""

    async def run_async(self, context: FlockContext) -> dict:
        workflow_id = context.state.get("workflow_id", "temporal-demo")
        flock_logger.set_context(workflow_id=workflow_id)

        with performance_handler.track_time("agent_execution"):
            # Log agent startup
            flock_logger.info("Starting Temporal logging agent")
            flock_logger.debug("Context state", state=context.state)

            # Simulate work with progress tracking
            with live_update_handler.progress_tracker("Processing workflow data") as update_progress:
                for i in range(3):
                    with performance_handler.track_time(f"step_{i + 1}"):
                        await asyncio.sleep(0.5)  # Simulate work
                        update_progress((i + 1) * 33)
                        flock_logger.activity_event(f"Completed workflow step {i + 1}")

            # Show workflow status
            with live_update_handler.update_workflow_status(workflow_id, "Completing", {"steps_completed": 3}):
                await asyncio.sleep(0.5)  # Simulate final work
                flock_logger.success("Workflow execution completed")

        # Display performance metrics
        performance_handler.display_timings()
        return {"status": "success", "steps_completed": 3}


async def run_temporal_workflow(client: Client, workflow_id: str):
    """Run the workflow with proper logging."""
    # Create agent and context
    agent = TemporalLoggingAgent(name="temporal-logging-demo", model="demo-model")
    context = FlockContext()
    context.state["workflow_id"] = workflow_id
    context.state["current_agent"] = agent.name

    try:
        # Execute workflow
        with performance_handler.track_time("workflow_execution"):
            result = await client.execute_workflow(
                "FlockWorkflow.run",
                context.to_dict(),
                id=workflow_id,
                task_queue="default",
                execution_timeout=timedelta(minutes=5),
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,  # Prevent duplicate workflows
            )

        flock_logger.success("Workflow completed", result=result)
        return result

    except Exception as e:
        flock_logger.error(f"Workflow failed: {e}")
        raise


async def main():
    """Run the Temporal logging demonstration."""
    # Generate a unique workflow ID
    workflow_id = f"temporal-logging-demo-{uuid.uuid4()}"

    try:
        # Attempt to connect to Temporal with a timeout
        flock_logger.info("Connecting to Temporal server...")
        try:
            async with asyncio.timeout(3.0):  # 3 second timeout
                client = await Client.connect("localhost:7233")
        except TimeoutError:
            raise RuntimeError("Connection attempt timed out")

        # If we get here, we successfully connected
        flock_logger.workflow_event("Starting Temporal workflow", workflow_id=workflow_id)
        await run_temporal_workflow(client, workflow_id)

    except (RPCError, RuntimeError) as e:
        if any(msg in str(e).lower() for msg in ["connection refused", "timed out"]):
            # Handle connection failure gracefully
            flock_logger.warning(
                "Could not connect to Temporal server. Make sure the server is running on localhost:7233"
            )
            # Demonstrate logging still works without Temporal
            flock_logger.info("Running agent locally instead...")
            agent = TemporalLoggingAgent(name="local-demo", model="demo-model")
            context = FlockContext()
            context.state["workflow_id"] = workflow_id
            await agent.run_async(context)
        else:
            # Let our error handler format other errors beautifully
            raise

    except Exception:
        # Let our error handler format this beautifully
        raise


if __name__ == "__main__":
    # The error handler is already installed via flock.core.logging import
    asyncio.run(main())
