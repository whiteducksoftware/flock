---
title: ControlRoutesComponent
description: The ControlRoutesComponent
tags:
 - server-components
 - endpoints
 - dashboard
search:
  boost: 0.2
---
# ControlRoutesComponent

The `ControlRoutesComponent` provides control endpoints for agent execution, artifact type discovery, and graph visualization.

## Overview

This component exposes HTTP endpoints for controlling the orchestrator, discovering available artifact types, and retrieving graph snapshots for visualization.

## Configuration

### ControlRoutesComponentConfig

**Fields:**
- `prefix` (str, default: `"/api/plugin/"`) - URL prefix for endpoints
- `tags` (list[str], default: `["Control Routes"]`) - OpenAPI tags

## Usage

```python
from flock import Flock
from flock.components.server import (
    ControlRoutesComponent,
    ControlRoutesComponentConfig
)

control = ControlRoutesComponent(
    config=ControlRoutesComponentConfig(
        prefix="/api/control",
        tags=["Control", "Admin"]
    )
)

await flock.serve(components=[control])
```

## Endpoints

### GET /api/plugin/artifact_types

Get all registered artifact types with their JSON schemas.

**Response:**
```json
{
  "artifact_types": [
    {
      "name": "Pizza",
      "schema": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "toppings": {
            "type": "array",
            "items": {"type": "string"}
          }
        },
        "required": ["name", "toppings"]
      }
    }
  ]
}
```

### POST /api/plugin/publish

Publish an artifact and trigger agents.

**Request Body:**
```json
{
  "artifact_type": "Pizza",
  "data": {
    "name": "Margherita",
    "toppings": ["tomato", "mozzarella"]
  },
  "tags": ["customer-order"],
  "correlation_id": "order-123",
  "visibility": {
    "kind": "public"
  }
}
```

**Response:**
```json
{
  "artifact_id": "uuid-123",
  "artifact_type": "Pizza",
  "triggered_agents": ["pizza_reviewer"],
  "status": "published"
}
```

### GET /api/plugin/graph

Get current graph snapshot for visualization.

**Response:**
```json
{
  "nodes": [
    {
      "id": "pizza_master",
      "type": "agent",
      "label": "pizza_master",
      "status": "idle",
      "consumes": ["MyDreamPizza"],
      "publishes": ["Pizza"]
    }
  ],
  "edges": [
    {
      "source": "external",
      "target": "pizza_master",
      "artifact_type": "MyDreamPizza"
    }
  ]
}
```

## Best Practices

### 1. Use for Dashboard Integration

```python
# Frontend fetches graph for visualization
const response = await fetch('/api/plugin/graph');
const graph = await response.json();
renderGraph(graph.nodes, graph.edges);
```

### 2. Discover Artifact Schemas

```python
# Get schemas for dynamic form generation
response = await client.get('/api/plugin/artifact_types')
types = response.json()['artifact_types']

for artifact_type in types:
    schema = artifact_type['schema']
    generate_form(schema)  # Dynamic UI
```

### 3. Publish via HTTP

```python
# External system publishes artifacts
await client.post('/api/plugin/publish', json={
    "artifact_type": "CustomerOrder",
    "data": {"order_id": "123"},
    "correlation_id": "order-123"
})
```

## Component Properties

- **Name:** `control`
- **Priority:** `3`
- **Dependencies:** GraphAssembler (optional)

## Example

See: **[examples/09-server-components/08_control_routes_component.py](../../../examples/09-server-components/08_control_routes_component.py)**
