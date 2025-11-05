---
title: TracingComponent
description: Tracing Component documentation. Tracing, Analyzing and Querying of Agent Stats
tags:
 - endpoints
 - telemetry
 - logging
 - tracing
search:
  boost: 1.5
---
# TracingComponent

The `TracingComponent` provides HTTP endpoints for querying, analyzing, and managing OpenTelemetry traces stored in DuckDB.

## Overview

This component exposes a powerful API for trace analysis, enabling developers to query execution history, debug workflows, and analyze performance bottlenecks.

## Configuration

### TracingComponentConfig

**Fields:**
- `prefix` (str, default: `"/api/plugin/"`) - URL prefix for endpoints
- `tags` (list[str], default: `["Tracing"]`) - OpenAPI tags
- `db_path` (str | Path | None) - Path to DuckDB trace database (default: `.flock/traces.duckdb`)

## Usage

```python
from flock import Flock
from flock.components.server import (
    TracingComponent,
    TracingComponentConfig
)

tracing = TracingComponent(
    config=TracingComponentConfig(
        prefix="/api/tracing",
        db_path=".flock/traces.duckdb"
    )
)

await flock.serve(components=[tracing])
```

## Endpoints

### GET /api/plugin/traces

Get OpenTelemetry traces with filtering.

**Query Parameters:**
- `service` (str) - Filter by service name
- `trace_id` (str) - Get specific trace
- `limit` (int) - Max results

**Response:**
```json
{
  "traces": [
    {
      "trace_id": "abc123...",
      "spans": [
        {
          "span_id": "span1",
          "name": "Agent.execute",
          "service": "pizza_master",
          "duration_ms": 1234.5,
          "status": "OK"
        }
      ]
    }
  ]
}
```

### GET /api/plugin/traces/services

Get list of unique services that have been traced.

**Response:**
```json
{
  "services": [
    "pizza_master",
    "pizza_reviewer",
    "orchestrator"
  ]
}
```

### DELETE /api/plugin/traces/clear

Clear all traces from the database.

**Response:**
```json
{
  "deleted_count": 42,
  "status": "cleared"
}
```

### POST /api/plugin/traces/query

Execute custom DuckDB SQL query on traces.

**Request Body:**
```json
{
  "query": "SELECT service, COUNT(*) as count FROM spans GROUP BY service"
}
```

**Response:**
```json
{
  "results": [
    {"service": "pizza_master", "count": 10},
    {"service": "pizza_reviewer", "count": 8}
  ]
}
```

### GET /api/plugin/traces/stats

Get statistics about the trace database.

**Response:**
```json
{
  "total_traces": 15,
  "total_spans": 42,
  "services_count": 3,
  "oldest_trace": "2025-10-31T12:00:00Z",
  "newest_trace": "2025-10-31T12:05:00Z"
}
```

## Best Practices

### 1. Use for Debugging

```python
# Find failed executions
response = await client.post('/api/plugin/traces/query', json={
    "query": """
        SELECT trace_id, name, status_description
        FROM spans
        WHERE status_code = 'ERROR'
        ORDER BY start_time DESC
        LIMIT 10
    """
})
```

### 2. Analyze Performance

```python
# Find slowest operations
response = await client.post('/api/plugin/traces/query', json={
    "query": """
        SELECT service, name, AVG(duration_ms) as avg_duration
        FROM spans
        GROUP BY service, name
        ORDER BY avg_duration DESC
        LIMIT 10
    """
})
```

### 3. Clear Old Traces

```python
# Periodically clean up traces
await client.delete('/api/plugin/traces/clear')
```

## Component Properties

- **Name:** `tracing`
- **Priority:** `4`
- **Dependencies:** DuckDB trace database

## Example

See: **[examples/09-server-components/11_tracing_component.py](../../../examples/09-server-components/11_tracing_component.py)**

## Related

- **[Unified Tracing Guide](../../UNIFIED_TRACING.md)** - Complete tracing documentation
- **[AGENTS.md - Tracing Section](../../AGENTS.md#-observability--debugging-with-opentelemetry--duckdb)** - Debugging with traces
