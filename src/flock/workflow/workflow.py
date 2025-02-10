from datetime import timedelta

from temporalio import workflow

from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger
from flock.workflow.activities import run_agent

# Import activity, passing it through the sandbox without reloading the module


logger = get_logger("workflow")


@workflow.defn
class FlockWorkflow:
    def __init__(self) -> None:
        self.context = None

    @workflow.run
    async def run(self, context_dict: dict) -> dict:
        self.context = FlockContext.from_dict(context_dict)
        self.context.workflow_id = workflow.info().workflow_id
        self.context.workflow_timestamp = workflow.info().start_time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            logger.info(
                "Starting workflow execution",
                timestamp=self.context.workflow_timestamp,
            )

            result = await workflow.execute_activity(
                run_agent,
                self.context,
                start_to_close_timeout=timedelta(minutes=5),
            )

            self.context.set_variable(
                "flock.result",
                {
                    "result": result,
                    "success": True,
                },
            )

            logger.success("Workflow completed successfully")
            return result

        except Exception as e:
            logger.exception("Workflow execution failed", error=str(e))
            self.context.set_variable(
                "flock.result",
                {
                    "result": f"Failed: {e}",
                    "success": False,
                },
            )
            return self.context
