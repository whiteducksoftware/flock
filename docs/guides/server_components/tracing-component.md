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

### GET /api/plugin/traces/agents/{agent_name}

An agent's latest runs and the spans below them, in the format of `/traces`. A run is an `Agent.execute` span whose `agent.name` attribute names the agent; the spans below it are read with a recursive query, so the trace database is never read whole. The dashboard's unfolded node reads its Traces tab from here.

**Query parameters:**
- `runs` (int, 1 to 50, default 5) - How many of the latest runs

Without a trace database the response is `[]`.

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

### GET /api/plugin/runs/active

The runs going on now, oldest first, from the dashboard's event collector: a dashboard that connects (or reconnects) while runs go on learns of them here, since it otherwise hears of a run only from its start event. Without the dashboard (no event collector) the list is empty.

**Response:**
```json
{
  "runs": [
    {
      "run_id": "<uuid>",
      "agent_name": "billing_team",
      "correlation_id": "<uuid>",
      "consumed_artifacts": ["<artifact uuid>"],
      "start_time": "2026-10-11T12:00:01+00:00"
    }
  ]
}
```

`consumed_artifacts` are the IDs the run's start event named (for a decision handle, the decision). An agent's past runs with their tokens and cost are at `GET /api/agents/{name}/runs`.

## Best Practices

### 1. Debug with Local DuckDB Analysis

Trusted operators with filesystem access can run SQL directly against the local trace database. Custom SQL execution is not available through the HTTP API.

```python
import duckdb

# Find failed executions
with duckdb.connect(".flock/traces.duckdb", read_only=True) as conn:
    errors = conn.execute("""
        SELECT trace_id, name, status_description
        FROM spans
        WHERE status_code = 'ERROR'
        ORDER BY start_time DESC
        LIMIT 10
    """).fetchall()
```

### 2. Analyze Performance Locally

```python
import duckdb

# Find slowest operations
with duckdb.connect(".flock/traces.duckdb", read_only=True) as conn:
    slow_operations = conn.execute("""
        SELECT service, name, AVG(duration_ms) as avg_duration
        FROM spans
        GROUP BY service, name
        ORDER BY avg_duration DESC
        LIMIT 10
    """).fetchall()
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
