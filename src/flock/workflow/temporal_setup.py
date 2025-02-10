import asyncio
import uuid

from temporalio.client import Client
from temporalio.worker import Worker


async def create_temporal_client() -> Client:
    client = await Client.connect("localhost:7233")
    return client


async def setup_worker(workflow, activity) -> Client:
    worker_client = await create_temporal_client()
    worker = Worker(worker_client, task_queue="flock-queue", workflows=[workflow], activities=[activity])
    asyncio.create_task(worker.run())
    await asyncio.sleep(1)


async def run_worker(client: Client, task_queue: str, workflows, activities):
    worker = Worker(client, task_queue=task_queue, workflows=workflows, activities=activities)
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
