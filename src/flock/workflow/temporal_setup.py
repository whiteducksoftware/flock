import uuid

from temporalio.client import Client
from temporalio.worker import Worker


async def create_temporal_client() -> Client:
    # Consider making the address configurable
    client = await Client.connect("localhost:7233")
    return client


async def setup_worker(
    client: Client, task_queue: str, workflow: type, activities: list
) -> Worker:
    """Creates and configures a worker instance, but does not run it.

    Args:
        client: The Temporal client to associate with the worker.
        task_queue: The task queue the worker should listen on.
        workflow: The workflow class definition.
        activities: A list of activity functions.

    Returns:
        A configured Worker instance.
    """
    # Creates and configures the worker instance
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[workflow],
        activities=activities,
    )
    return worker  # Return the configured worker instance


async def run_worker(client: Client, task_queue: str, workflows, activities):
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=workflows,
        activities=activities,
    )
    await worker.run()


async def run_activity(client: Client, name: str, func, param):
    run_id = f"{name}_{uuid.uuid4().hex[:4]}"

    try:
        result = await client.execute_activity(
            func,
            param,
            id=run_id,
            task_queue="flock-queue",
            start_to_close_timeout=300,  # e.g., 5 minutes
        )
        return result
    except Exception:
        raise
