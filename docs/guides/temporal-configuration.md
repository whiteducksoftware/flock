# Configuring Temporal Execution

When you run your Flock workflows using Temporal (`enable_temporal=True`), you gain access to powerful features for reliability and scalability. Flock allows you to declaratively configure various Temporal settings for both the overall workflow and individual agent activities.

## Why Configure Temporal?

- **Task Queues:** Route different workflows or agents to specific worker pools (e.g., GPU workers, high-priority workers).
- **Timeouts:** Prevent runaway executions and manage resource usage.
- **Retry Policies:** Automatically handle transient failures (like network issues or temporary API outages) with configurable backoff strategies.

## Prerequisites

- Ensure you have Temporal running and accessible.
- Enable Temporal execution in your Flock: `Flock(enable_temporal=True, ...)`

## Workflow-Level Configuration (`TemporalWorkflowConfig`)

You can define default settings for the entire workflow execution when you initialize your `Flock`.

```python
# Import necessary classes
from datetime import timedelta
from flock.core import Flock
# Adjust path if needed: from flock.config.temporal_config import ...
from flock.workflow.temporal_config import TemporalWorkflowConfig, TemporalRetryPolicyConfig 

# Define a custom retry policy (e.g., fewer retries by default)
default_retry = TemporalRetryPolicyConfig(
    maximum_attempts=2, # Default 2 attempts for activities
    initial_interval=timedelta(seconds=2)
)

# Define workflow configuration
workflow_config = TemporalWorkflowConfig(
    task_queue="my-custom-queue", # Default queue for this Flock's workflows
    workflow_execution_timeout=timedelta(minutes=30), # Max 30 mins total
    default_activity_retry_policy=default_retry
)

# Pass the config to your Flock
my_flock = Flock(
    name="configured_flock",
    enable_temporal=True,
    temporal_config=workflow_config
    # ... other Flock args
)

print(f"Flock configured for Temporal queue: {my_flock.temporal_config.task_queue}") 
```

**Key `TemporalWorkflowConfig` Fields:**

- `task_queue`: The default Temporal Task Queue for this workflow. Workers must listen on this queue.
- `workflow_execution_timeout`: Maximum total duration for the workflow.
- `workflow_run_timeout`: Maximum duration for a single run attempt.
- `default_activity_retry_policy`: A `TemporalRetryPolicyConfig` object defining the default retry behavior for all activities *unless overridden by an agent*.

## Agent-Specific Configuration (`TemporalActivityConfig`)

Sometimes, different agents need different settings (e.g., longer timeouts for complex tasks, different retry logic for external API calls). You can specify these when defining your `FlockAgent`.

```python
# Import necessary classes
from datetime import timedelta
from flock.core import FlockFactory
# Adjust path if needed: from flock.config.temporal_config import ...
from flock.workflow.temporal_config import TemporalActivityConfig, TemporalRetryPolicyConfig 

# Define a specific retry policy for this agent
agent_retry = TemporalRetryPolicyConfig(
    maximum_attempts=5, # Allow more retries
    non_retryable_error_types=["ValueError"] # Don't retry specific errors
)

# Define activity configuration for this agent
agent_activity_config = TemporalActivityConfig(
    start_to_close_timeout=timedelta(minutes=3), # Allow 3 minutes per attempt
    retry_policy=agent_retry,
    task_queue="gpu-workers-queue" # Optionally route this agent to different workers!
)

# Create the agent and pass the config
special_agent = FlockFactory.create_default_agent(
    name="special_gpu_agent",
    input="data",
    output="processed_data",
    # Add the specific Temporal config here!
    temporal_activity_config=agent_activity_config
)

# Assuming 'my_flock' is the Flock instance from the previous example
# my_flock.add_agent(special_agent) 

# You can inspect the agent's config:
print(f"Agent '{special_agent.name}' config timeout: {special_agent.temporal_activity_config.start_to_close_timeout}")
```

**Key `TemporalActivityConfig` Fields:**

- `task_queue`: Route *this specific agent's* execution to a different task queue (overrides workflow default).
- `start_to_close_timeout`: Maximum duration for a single attempt of *this specific agent's* activity.
- `retry_policy`: A `TemporalRetryPolicyConfig` defining retry behavior specifically for *this agent*, overriding the workflow default.

**Configuration Precedence:**

Settings are applied with the following priority:

1.  Agent's `temporal_activity_config` (if set for a specific field)
2.  Flock's `temporal_config.default_activity_retry_policy` (for retries)
3.  Flock's `temporal_config.task_queue` (for activity task queue, if not set on agent)
4.  Temporal's built-in defaults (e.g., for timeouts if not set anywhere).

## Runtime Metadata (`memo`)

You can add non-indexed metadata to your workflow run for observability using the `memo` parameter in `run` or `run_async`:

```python
# Assuming 'my_flock' is the Flock instance from previous examples
# result = my_flock.run_async(
#    start_agent="some_agent",
#    input={"data": "..."},
#    memo={"user_id": "user123", "experiment_tag": "v2-prompt"}
# )
```

This metadata will be visible in the Temporal UI.

## Example

Here's a combined example similar to the one used during development:

```python
# .flock/flock_temporal_config_example.py
import asyncio
from datetime import timedelta

# Import Temporal config models (adjust path if needed)
from flock.workflow.temporal_config import (
    TemporalActivityConfig,
    TemporalRetryPolicyConfig,
    TemporalWorkflowConfig,
)
from flock.core import Flock, FlockFactory
from flock.routers.default.default_router import DefaultRouterConfig

async def main():
    # 1. Define Workflow Config
    workflow_config = TemporalWorkflowConfig(
        task_queue="flock-example-queue", 
        workflow_execution_timeout=timedelta(minutes=10), 
        default_activity_retry_policy=TemporalRetryPolicyConfig(maximum_attempts=2)
    )

    # 2. Create Flock with Temporal Config
    configure_logging("ERROR")  # show only errors
    flock = Flock(
        enable_temporal=True, # MUST be True to use Temporal config
        temporal_config=workflow_config
    )

    # 3. Presentation Agent (uses workflow defaults)
    agent = FlockFactory.create_default_agent(
        name="presentation_agent",
        input="topic",
        output="funny_title, funny_slide_headers",
    )
    flock.add_agent(agent)

    # 4. Content Agent Config (specific settings)
    content_agent_retry = TemporalRetryPolicyConfig(maximum_attempts=4)
    content_agent_activity_config = TemporalActivityConfig(
        start_to_close_timeout=timedelta(minutes=1), 
        retry_policy=content_agent_retry
    )

    # 5. Content Agent (with specific config)
    content_agent = FlockFactory.create_default_agent(
        name="content_agent",
        input="funny_title, funny_slide_headers",
        output="funny_slide_content",
        temporal_activity_config=content_agent_activity_config 
    )
    flock.add_agent(content_agent)

    # 6. Add routing
    agent.add_component(DefaultRouterConfig(hand_off="content_agent"))

    print(f"Starting Flock run on Temporal task queue: {workflow_config.task_queue}")
    print(f"Ensure a Temporal worker is listening on '{workflow_config.task_queue}'")
    
    # 7. Run the workflow (example input)
    try:
        result = await flock.run_async(
            start_agent="presentation_agent",
            input={"topic": "Why Temporal makes distributed systems easier"},
            memo={"run_type": "docs_example"} # Example memo
        )

        print("\n--- Result ---")
        print(result)
    except Exception as e:
        print(f"\n--- An error occurred ---")
        print(f"Error: {e}")
        print("Ensure Temporal service and worker are running correctly.")


if __name__ == "__main__":
    asyncio.run(main())
```

## Next Steps

- Learn more about Temporal's concepts like [Task Queues](https://docs.temporal.io/concepts/what-is-a-task-queue) and [Retries](https://docs.temporal.io/concepts/what-is-a-retry-policy).
- Explore how to run [Temporal Workers](https://docs.temporal.io/application-development/foundations#worker) to process tasks from your queues. 

## Running Temporal Workers (Production Requirement)

The examples above show how to configure Temporal settings declaratively. However, for Temporal workflows to actually execute, you need **Worker Processes** running, listening on the specified task queues.

**Development vs. Production:**

- **Current Behavior (Development/Testing):** For convenience during local development and testing, when you call `flock.run_async` with `enable_temporal=True`, the Flock framework *currently* starts a temporary, in-process worker in the background. This allows simple scripts like the examples above to run without needing a separate process. **This is NOT intended for production use.**
- **Production Requirement:** In a real deployment (staging, production), you **must** run dedicated, long-running worker processes separately from your application that calls `flock.run_async`. These workers are responsible for picking up tasks from the queue and executing your workflow and activity code.

**Why Dedicated Workers?**

- **Scalability:** You can run multiple worker processes (even on different machines) listening to the same task queue to handle higher loads.
- **Reliability:** Workers can be restarted independently of your main application.
- **Resource Management:** You can run workers on machines with specific resources (e.g., GPUs for certain agents) by having them listen on specific task queues (like `gpu-workers-queue` configured in `TemporalActivityConfig`).
- **Isolation:** Keeps the workflow execution logic separate from your application logic.

**Creating a Worker Script:**

You need to create a separate Python script (e.g., `run_flock_worker.py`) to run your workers. Here's a basic example:

```python
# run_flock_worker.py
import asyncio
import logging # Use standard logging for the worker process

from temporalio.client import Client
from temporalio.worker import Worker

# Import your Flock workflow and activities
# Ensure these imports work in the context where you run the worker
from flock.workflow.flock_workflow import FlockWorkflow
from flock.workflow.agent_execution_activity import (
    execute_single_agent,
    determine_next_agent,
)

# --- Configuration ---
# Make these configurable via environment variables, CLI args, or a config file
TEMPORAL_SERVICE_URL = "localhost:7233" 
NAMESPACE = "default"
# The task queue(s) this worker process will listen on.
# Must match the queue(s) defined in your Flock/Agent Temporal configurations.
TASK_QUEUES = ["flock-queue", "flock-example-queue", "my-custom-queue", "gpu-workers-queue"] 

# Configure logging for the worker process
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def run_worker():
    log.info(f"Connecting to Temporal at {TEMPORAL_SERVICE_URL} in namespace '{NAMESPACE}'")
    client = await Client.connect(TEMPORAL_SERVICE_URL, namespace=NAMESPACE)
    log.info(f"Client connected successfully.")

    activities_to_register = [execute_single_agent, determine_next_agent]
    workflows_to_register = [FlockWorkflow]

    # Create and run workers for each specified task queue
    # You might run multiple instances of this script for different queues
    # or handle multiple queues in one worker if resources allow.
    worker_tasks = []
    for queue in TASK_QUEUES:
        log.info(f"Starting worker for task queue: '{queue}'")
        worker = Worker(
            client,
            task_queue=queue,
            workflows=workflows_to_register,
            activities=activities_to_register,
            # identity="my-worker-process-1" # Optional: Set a worker identity
        )
        worker_tasks.append(asyncio.create_task(worker.run()))
        log.info(f"Worker for task queue '{queue}' started.")

    log.info(f"All workers started. Running indefinitely...")
    # Keep running until manually stopped or an error occurs
    await asyncio.gather(*worker_tasks)

if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        log.info("Worker process interrupted. Shutting down.")
    except Exception as e:
        log.exception(f"Worker process failed: {e}")

**Running the Worker:**

1.  Save the code above as `run_flock_worker.py` (or similar).
2.  Customize `TEMPORAL_SERVICE_URL`, `NAMESPACE`, and especially `TASK_QUEUES` to match your environment and the queues you configured in your `Flock` and `FlockAgent` objects.
3.  Run the worker from your terminal: `python run_flock_worker.py`
4.  You typically keep this worker process running indefinitely using a process manager like `systemd`, `supervisor`, or within a container orchestration system (like Kubernetes).

**Important Note on Automatic Worker Startup:**

As mentioned, `flock.run_async` currently starts a temporary worker for convenience if `enable_temporal=True` and the `temporal_start_in_process_worker` flag on your `Flock` instance is `True` (which is the default).

When you are running your own dedicated workers (like the script above), this temporary worker becomes redundant. To prevent this, you should set `temporal_start_in_process_worker=False` when initializing your `Flock` instance:

```python
my_prod_flock = Flock(
    # ... other config ...
    enable_temporal=True,
    temporal_config=workflow_config, # Your production temporal config
    temporal_start_in_process_worker=False # Disable automatic worker
)
```

Focus on ensuring your dedicated workers are correctly configured and running for production deployments. 