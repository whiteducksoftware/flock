---
title: AgentServerComponent
description: The AgentServerComponent
tags:
 - server-components
 - endpoints
 - agents
search:
  boost: 0.5
---
# AgentsServerComponent

The `AgentsServerComponent` exposes agent metadata and control via HTTP endpoints, enabling programmatic access to agent information and execution history.

## Overview

This component provides REST API endpoints for querying agent information, viewing agent subscriptions, checking execution history, and monitoring workflow status.

## Configuration

### AgentsServerComponentConfig

**Fields:**
- `prefix` (str, default: `"/api/v1/plugin/"`) - URL prefix for all endpoints
- `tags` (list[str], default: `["Agents", "Public API"]`) - OpenAPI documentation tags

## Usage

```python
from flock import Flock
from flock.components.server import (
    AgentsServerComponent,
    AgentsServerComponentConfig
)

flock = Flock()

agents = AgentsServerComponent(
    config=AgentsServerComponentConfig(
        prefix="/api/v1",
        tags=["Agents", "API"]
    )
)

await flock.serve(components=[agents])
```

## Endpoints

### GET /api/v1/plugin/agents

List all registered agents with their metadata.

**Response:**
```json
{
  "agents": [
    {
      "id": "pizza_master",
      "name": "pizza_master",
      "description": "Creates perfect pizzas from ideas",
      "consumes": ["MyDreamPizza"],
      "publishes": ["Pizza"],
      "subscriptions": [...]
    }
  ]
}
```

### GET /api/v1/plugin/agents/{agent_id}/history-summary

Get execution history summary for a specific agent.

**Query Parameters:**
- `type_names` (list[str]) - Filter by artifact types
- `produced_by` (list[str]) - Filter by producer agents
- `correlation_id` (str) - Filter by correlation ID
- `tags` (list[str]) - Filter by tags
- `start` (ISO datetime) - Start of time range
- `end` (ISO datetime) - End of time range

**Response:**
```json
{
  "agent_id": "pizza_master",
  "total_runs": 42,
  "artifacts_consumed": [
    {"type": "MyDreamPizza", "count": 42}
  ],
  "artifacts_produced": [
    {"type": "Pizza", "count": 42}
  ]
}
```

### GET /api/v1/plugin/correlations/{correlation_id}/status

Get workflow status by correlation ID.

**Response:**
```json
{
  "correlation_id": "workflow-123",
  "status": "completed",
  "started_at": "2025-10-31T12:00:00Z",
  "completed_at": "2025-10-31T12:00:05Z",
  "artifacts": [
    {
      "id": "uuid-1",
      "type": "Pizza",
      "produced_by": "pizza_master"
    }
  ]
}
```

## Best Practices

### 1. Use with Dashboard

```python
components = [
    AgentsServerComponent(),  # Provides agent metadata
    WebSocketServerComponent(),  # Real-time updates
]
```

### 2. Secure Endpoints

```python
from flock.components.server import AuthenticationComponent

auth = AuthenticationComponent(...)
agents = AgentsServerComponent()

# Agents endpoints now require authentication
```

### 3. Monitor Workflows

```python
# Track workflow progress via correlation ID
response = await client.get(f"/api/v1/plugin/correlations/{correlation_id}/status")
status = response.json()

if status["status"] == "completed":
    print("Workflow finished!")
```

## Component Properties

- **Name:** `agents`
- **Priority:** `5`
- **Dependencies:** None

## Example

See: **[examples/09-server-components/07_agents_component.py](../../../examples/09-server-components/07_agents_component.py)**
