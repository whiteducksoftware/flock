# REST API Guide

Flock includes a production-ready REST API for programmatic access to the blackboard orchestrator. This enables integration with external systems, building custom UIs, and monitoring production deployments.

## Quick Start

Start the API server with your Flock orchestrator:

```python
from flock import Flock

flock = Flock("openai/gpt-4.1")

# Add your agents here...

# Start server with both API and Dashboard
await flock.serve(dashboard=True)  # Runs on http://localhost:8344
```

The API documentation is available at `http://localhost:8344/docs` with interactive OpenAPI explorer.

## Core Endpoints

### Artifacts

#### Publish Artifact
```http
POST /api/v1/artifacts
Content-Type: application/json

{
  "type": "YourArtifactType",
  "payload": {
    "field1": "value1",
    "field2": "value2"
  }
}
```

**Response:**
```json
{
  "status": "accepted"
}
```

**Use case:** Publish artifacts programmatically to trigger agent workflows.

---

#### List Artifacts
```http
GET /api/v1/artifacts?type=YourType&limit=50&offset=0
```

**Query parameters:**
- `type` (list[str]) - Filter by artifact type names
- `produced_by` (list[str]) - Filter by producer agent names
- `correlation_id` (str) - Filter by workflow correlation ID
- `tag` (list[str]) - Filter by tags
- `from` (ISO 8601) - Start timestamp
- `to` (ISO 8601) - End timestamp
- `visibility` (list[str]) - Filter by visibility kind
- `limit` (int, 1-500) - Items per page (default: 50)
- `offset` (int) - Page offset (default: 0)
- `embed_meta` (bool) - Include consumption metadata (default: false)

**Response:**
```json
{
  "items": [
    {
      "id": "uuid-here",
      "type": "YourType",
      "payload": {...},
      "produced_by": "agent_name",
      "visibility": {...},
      "visibility_kind": "Public",
      "created_at": "2025-10-19T10:00:00Z",
      "correlation_id": "workflow-uuid",
      "partition_key": null,
      "tags": ["tag1", "tag2"],
      "version": 1,
      "consumptions": [...],  // Only if embed_meta=true
      "consumed_by": ["agent1", "agent2"]  // Only if embed_meta=true
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 123
  }
}
```

**Use case:** Query artifacts for analytics, debugging, or building custom dashboards.

---

#### Get Single Artifact
```http
GET /api/v1/artifacts/{artifact_id}
```

**Response:** Single artifact object (same structure as list items).

**Use case:** Retrieve specific artifact details by UUID.

---

#### Artifact Summary
```http
GET /api/v1/artifacts/summary?type=YourType&from=2025-10-19T00:00:00Z
```

**Query parameters:** Same as List Artifacts (except limit/offset)

**Response:**
```json
{
  "summary": {
    "total_count": 123,
    "by_type": {...},
    "by_producer": {...},
    "by_visibility": {...}
  }
}
```

**Use case:** Get aggregate statistics for monitoring and reporting.

---

### Agents

#### List Agents
```http
GET /api/v1/agents
```

**Response:**
```json
{
  "agents": [
    {
      "name": "bug_detector",
      "description": "Detects bugs in code submissions",
      "subscriptions": [
        {
          "types": ["CodeSubmission"],
          "mode": "all"
        }
      ],
      "outputs": ["BugAnalysis"]
    }
  ]
}
```

**Use case:** Discover available agents and their subscriptions.

---

#### Run Agent Directly
```http
POST /api/v1/agents/{agent_name}/run
Content-Type: application/json

{
  "inputs": [
    {
      "type": "CodeSubmission",
      "payload": {
        "code": "def foo(): pass",
        "language": "python"
      }
    }
  ]
}
```

**Response:**
```json
{
  "artifacts": [
    {
      "id": "uuid-here",
      "type": "BugAnalysis",
      "payload": {...},
      "produced_by": "bug_detector"
    }
  ]
}
```

**Use case:** Direct agent invocation for testing or synchronous execution.

---

#### Agent History Summary
```http
GET /api/v1/agents/{agent_id}/history-summary?from=2025-10-19T00:00:00Z
```

**Query parameters:** Same as Artifact filters

**Response:**
```json
{
  "agent_id": "bug_detector",
  "summary": {
    "total_executions": 42,
    "total_artifacts_consumed": 84,
    "total_artifacts_produced": 42,
    "execution_timeline": {...}
  }
}
```

**Use case:** Monitor agent activity and performance over time.

---

### Correlation Status (Workflow Tracking)

#### Get Correlation Status
```http
GET /api/v1/correlations/{correlation_id}/status
```

**Response:**
```json
{
  "correlation_id": "workflow-uuid",
  "state": "completed",
  "has_pending_work": false,
  "artifact_count": 15,
  "error_count": 0,
  "started_at": "2025-10-19T10:00:00Z",
  "last_activity_at": "2025-10-19T10:05:23Z"
}
```

**State values:**
- `active` - Workflow is still processing (has pending work)
- `completed` - Workflow finished successfully
- `failed` - Workflow completed with only errors
- `not_found` - No artifacts found for this correlation ID

**Use case:** Poll for workflow completion. Keep polling while `state` is `"active"`.

**Polling pattern:**
```python
import httpx
import time

async def wait_for_completion(correlation_id: str, timeout: int = 300):
    start = time.time()
    while time.time() - start < timeout:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://localhost:8344/api/v1/correlations/{correlation_id}/status"
            )
            data = resp.json()

            if data["state"] in ["completed", "failed"]:
                return data

            await asyncio.sleep(2)  # Poll every 2 seconds

    raise TimeoutError("Workflow did not complete in time")
```

---

### Health & Metrics

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "ok"
}
```

**Use case:** Kubernetes liveness/readiness probes.

---

#### Prometheus Metrics
```http
GET /metrics
```

**Response:** Prometheus-compatible text format
```
blackboard_artifacts_total 123
blackboard_agents_count 5
blackboard_executions_total 42
```

**Use case:** Scrape with Prometheus for monitoring.

---

## Production Patterns

### Multi-Step Workflow Tracking

1. Publish initial artifact with `correlation_id`
2. Poll `/api/v1/correlations/{correlation_id}/status` every 2-5 seconds
3. When `state` is `"completed"`, query results with `/api/v1/artifacts?correlation_id={correlation_id}`

```python
# Step 1: Publish with correlation_id
correlation_id = str(uuid.uuid4())
async with httpx.AsyncClient() as client:
    await client.post(
        "http://localhost:8344/api/v1/artifacts",
        json={
            "type": "CodeSubmission",
            "payload": {"code": "...", "language": "python"}
        },
        headers={"X-Correlation-ID": correlation_id}
    )

# Step 2: Poll for completion
while True:
    resp = await client.get(
        f"http://localhost:8344/api/v1/correlations/{correlation_id}/status"
    )
    status = resp.json()

    if status["state"] == "completed":
        break
    elif status["state"] == "failed":
        raise RuntimeError("Workflow failed")

    await asyncio.sleep(2)

# Step 3: Get results
resp = await client.get(
    f"http://localhost:8344/api/v1/artifacts?correlation_id={correlation_id}"
)
results = resp.json()["items"]
```

---

### Building Custom Dashboards

Query artifacts with `embed_meta=true` to get full consumption data:

```python
# Get all artifacts with their consumers
async with httpx.AsyncClient() as client:
    resp = await client.get(
        "http://localhost:8344/api/v1/artifacts?embed_meta=true&limit=100"
    )
    artifacts = resp.json()["items"]

# Each artifact includes:
# - consumptions: List of {consumer, run_id, consumed_at}
# - consumed_by: List of unique consumer names

# Build dependency graph
graph = {}
for artifact in artifacts:
    producer = artifact["produced_by"]
    consumers = artifact.get("consumed_by", [])
    graph[producer] = graph.get(producer, set()) | set(consumers)
```

---

### Multi-Tenant Isolation

Use tags or partition keys to isolate tenant data:

```python
# Publish with tenant tag
await client.post(
    "http://localhost:8344/api/v1/artifacts",
    json={
        "type": "CustomerData",
        "payload": {...},
        "tags": ["tenant:customer_123"]
    }
)

# Query only tenant's data
resp = await client.get(
    "http://localhost:8344/api/v1/artifacts?tag=tenant:customer_123"
)
tenant_artifacts = resp.json()["items"]
```

---

## OpenAPI Schema

The full OpenAPI 3.0 schema is available at:
- Interactive docs: `http://localhost:8344/docs`
- OpenAPI JSON: `http://localhost:8344/openapi.json`

Use the schema to generate client SDKs in any language:
```bash
# Generate TypeScript client
openapi-generator-cli generate \
  -i http://localhost:8344/openapi.json \
  -g typescript-fetch \
  -o ./flock-client

# Generate Python client
openapi-generator-cli generate \
  -i http://localhost:8344/openapi.json \
  -g python \
  -o ./flock-client
```

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200 OK` - Success
- `400 Bad Request` - Invalid input (check `detail` field)
- `404 Not Found` - Resource not found (agent, artifact)
- `500 Internal Server Error` - Server error (check logs)

**Error response format:**
```json
{
  "detail": "Agent not found: invalid_agent_name"
}
```

---

## Security Considerations

**⚠️ Production Deployment:**

The current API has **no authentication**. For production:

1. **Run behind reverse proxy** (nginx, Traefik) with authentication
2. **Use API gateway** (Kong, Tyk) for rate limiting and OAuth
3. **Firewall rules** - Restrict access to trusted networks
4. **TLS/HTTPS** - Always use HTTPS in production

**Visibility enforcement:** The API respects artifact visibility rules. Agents can only see artifacts their visibility permissions allow.

---

## Next Steps

- [Dashboard Guide](dashboard.md) - Visual monitoring
- [Tracing Guide](tracing/index.md) - Distributed tracing
- [Persistent Blackboard](persistent-blackboard.md) - Durable storage
- [Visibility Guide](visibility.md) - Access control
