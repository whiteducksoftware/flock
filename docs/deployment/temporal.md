---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Deploying with Temporal 🕒

[Temporal](https://temporal.io/) is an open-source workflow engine that provides **durability**, **retries**, and **observability** for long-running processes.  Flock integrates with Temporal via a dedicated **FlockWorkflow** and **Activity** classes so your agent systems inherit these benefits with minimal setup.

---

## 1. Terminology

| Temporal Term | Flock Equivalent |
| ------------- | --------------- |
| **Workflow** | A *run* of a `Flock` instance |
| **Activity** | A single agent execution (`agent.evaluate`) |
| **Worker** | Python process hosting the Flock activity code |

---

## 2. Enabling Temporal

```python
from flock.core import Flock
from flock.workflow.temporal_config import TemporalWorkflowConfig

config = TemporalWorkflowConfig(
    server_url="temporal:7233",
    namespace="flock-example",
    task_queue="agent-tasks",
)

flock = Flock(
    name="prod_flock",
    enable_temporal=True,
    temporal_config=config,
    temporal_start_in_process_worker=False,  # set True for local dev
)
```

* `temporal_start_in_process_worker` – If `True`, Flock will spin up a worker thread automatically.  In production you'll run workers separately.

---

## 3. Worker Deployment

```bash
# Activate venv and run from project root
python -m flock.workflow.temporal_worker \
    --server "temporal:7233" \
    --namespace "flock-example" \
    --task-queue "agent-tasks"
```

* Workers can be scaled horizontally; each maintains sticky caches of workflow state.
* Use `--concurrency` flag (or env `TEMPORAL_MAX_CONCURRENCY`) to limit parallelism.

---

## 4. Observability

* **Temporal Web UI** – view workflow history, search by `run_id`, replay failures.
* **OpenTelemetry** – Flock adds spans for each activity; export via OTLP to Grafana Tempo.
* **Logs** – Worker logs include activity name, attempt, and custom metrics from modules.

---

## 5. Timeouts & Retries

Each agent can override defaults with `TemporalActivityConfig`:

```python
from flock.workflow.temporal_config import TemporalActivityConfig

agent.temporal_activity_config = TemporalActivityConfig(
    start_to_close_timeout_seconds=60,
    schedule_to_start_timeout_seconds=10,
    retry_max_attempts=3,
)
```

If not specified, the values from `TemporalWorkflowConfig.activity_defaults` apply.

---

## 6. Memo & Search Attributes

Flock serialises the entire `Flock` object and stores it as **memo** so that a run can be resumed even after code changes.  Key metadata like `flock_name`, `start_agent`, and `session_id` are stored as **search attributes** for efficient querying.

---

## 7. Versioning Guidelines

* Increment `TemporalWorkflowConfig.workflow_version` whenever the workflow logic changes incompatibly.
* Add new activities instead of changing signatures to prevent replay failures.

---

## 8. Local Development Tips

* Use the [Temporal Docker Compose](https://github.com/temporalio/docker-compose) file and set `temporal_start_in_process_worker=True` for a self-contained dev experience.
* Run `temporal workflow reset` to reset stuck runs when testing.

---

That's it! Your Flock is now production-ready with Temporal.
