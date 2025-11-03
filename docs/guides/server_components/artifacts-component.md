---
title: ArtifactsComponent
description: The Artifacts ServerComponent
tags:
 - server-components
 - endpoints
 - components
search:
  boost: 0.5
---
# ArtifactsComponent

The `ArtifactsComponent` provides a REST API for querying and publishing artifacts on the blackboard, enabling external systems to interact with the Flock orchestrator.

## Overview

This component exposes HTTP endpoints for artifact operations, including querying with advanced filters, publishing new artifacts, and viewing consumption history.

## Configuration

### ArtifactComponentConfig

**Fields:**
- `prefix` (str, default: `"/api/v1/plugin/"`) - URL prefix for endpoints
- `tags` (list[str], default: `["Artifacts"]`) - OpenAPI tags

## Usage

```python
from flock import Flock
from flock.components.server import (
    ArtifactsComponent,
    ArtifactComponentConfig
)

artifacts = ArtifactsComponent(
    config=ArtifactComponentConfig(
        prefix="/api/v1",
        tags=["Artifacts", "Blackboard"]
    )
)

await flock.serve(components=[artifacts])
```

## Endpoints

### GET /api/v1/plugin/artifacts

Query artifacts with filtering and pagination.

**Query Parameters:**
- `type_names` (list[str]) - Filter by artifact types
- `produced_by` (list[str]) - Filter by producer agents
- `correlation_id` (str) - Filter by correlation ID
- `tags` (list[str]) - Filter by tags
- `visibility` (list[str]) - Filter by visibility kind
- `start` (ISO datetime) - Start of time range
- `end` (ISO datetime) - End of time range
- `limit` (int) - Max results (default: 100)
- `offset` (int) - Pagination offset
- `embed_consumptions` (bool) - Include consumption records

**Response:**
```json
{
  "artifacts": [
    {
      "id": "uuid-1",
      "type": "Pizza",
      "payload": {
        "name": "Hawaiian Supreme",
        "toppings": ["pineapple", "ham"]
      },
      "produced_by": "pizza_master",
      "created_at": "2025-10-31T12:00:00Z",
      "tags": ["urgent"],
      "consumptions": [
        {
          "consumer": "pizza_reviewer",
          "consumed_at": "2025-10-31T12:00:01Z"
        }
      ]
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### POST /api/v1/plugin/artifacts

Publish a new artifact to the blackboard.

**Request Body:**
```json
{
  "artifact_type": "Pizza",
  "payload": {
    "name": "Margherita",
    "toppings": ["tomato", "mozzarella", "basil"]
  },
  "tags": ["urgent", "customer-request"],
  "correlation_id": "order-123",
  "visibility": {
    "kind": "public"
  }
}
```

**Response:**
```json
{
  "artifact_id": "uuid-new",
  "status": "published",
  "triggered_agents": ["pizza_reviewer", "pizza_delivery"]
}
```

## Best Practices

### 1. Use Filtering for Performance

```python
# ✅ Filter by correlation ID for workflow tracking
response = await client.get(
    "/api/v1/plugin/artifacts",
    params={"correlation_id": "workflow-123"}
)
```

### 2. Include Consumption Data

```python
# Get artifacts with consumption history
response = await client.get(
    "/api/v1/plugin/artifacts",
    params={"embed_consumptions": True}
)

# See which agents consumed each artifact
for artifact in response.json()["artifacts"]:
    print(f"Consumed by: {artifact['consumed_by']}")
```

### 3. Paginate Large Result Sets

```python
# Fetch in batches
limit = 50
offset = 0

while True:
    response = await client.get(
        "/api/v1/plugin/artifacts",
        params={"limit": limit, "offset": offset}
    )

    artifacts = response.json()["artifacts"]
    if not artifacts:
        break

    process_artifacts(artifacts)
    offset += limit
```

## Component Properties

- **Name:** `artifacts`
- **Priority:** `1`
- **Dependencies:** None

## Example

See: **[examples/09-server-components/06_artifacts_component.py](../../../examples/09-server-components/06_artifacts_component.py)**
