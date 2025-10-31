---
title: HealthAndMetricsComponent
description: Health and Metrics Server Component
tags:
 - endpoints
 - middleware
 - healthchecks
search:
  boost: 1.0
---
# HealthAndMetricsComponent

The `HealthAndMetricsComponent` provides essential health check and metrics endpoints for monitoring and observability of your Flock application.

## Overview

This component is typically the first to register (priority 0) and provides basic health monitoring capabilities required for production deployments, container orchestration, and load balancers.

## Features

- **Health Check Endpoint** - Simple HTTP endpoint returning service health status
- **Metrics Endpoint** - Prometheus-style metrics for monitoring (future expansion)
- **Zero Configuration** - Works out of the box with sensible defaults
- **Customizable Prefix** - Add version prefixes like `/api/v1/health`
- **OpenAPI Tags** - Organize endpoints in API documentation

## Configuration

### HealthComponentConfig

Configuration class for the health component.

**Fields:**

- `prefix` (str | None, default: `None`) - Optional prefix for all endpoints
- `tags` (list[str], default: `["Health & Metrics"]`) - OpenAPI documentation tags

## Usage Examples

### Example 1: Basic Health Check

```python
from flock import Flock
from flock.components.server import HealthAndMetricsComponent

flock = Flock()

# Use default configuration
health = HealthAndMetricsComponent()

await flock.serve(
    components=[health],
    host="0.0.0.0",
    port=8000
)
```

**Endpoints:**
- `GET /health` → `{"status": "ok"}`
- `GET /metrics` → Prometheus-style metrics

### Example 2: With API Versioning

```python
from flock.components.server import (
    HealthAndMetricsComponent,
    HealthComponentConfig
)

health = HealthAndMetricsComponent(
    config=HealthComponentConfig(
        prefix="/api/v1",
        tags=["Health & Metrics", "Infrastructure"]
    )
)

await flock.serve(components=[health])
```

**Endpoints:**
- `GET /api/v1/health` → `{"status": "ok"}`
- `GET /api/v1/metrics` → Prometheus metrics

### Example 3: Custom Tags for API Documentation

```python
health = HealthAndMetricsComponent(
    config=HealthComponentConfig(
        prefix="/internal",
        tags=["Internal", "Monitoring", "Ops"]
    )
)
```

## Endpoint Reference

### GET /health

Returns the health status of the service.

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200 OK` - Service is healthy

**Use Cases:**
- Kubernetes liveness/readiness probes
- Load balancer health checks
- Uptime monitoring
- Container orchestration

### GET /metrics

Returns Prometheus-style metrics for monitoring.

**Response Format:**
```
# Currently returns minimal metrics
# Future: Extended metrics for agent execution, artifact counts, etc.
```

**Status Codes:**
- `200 OK` - Metrics retrieved successfully

**Use Cases:**
- Prometheus scraping
- Grafana dashboards
- Custom monitoring solutions
- Performance tracking

## Best Practices

### 1. Always Include in Production

```python
# ✅ CORRECT: Health check enabled
components = [
    HealthAndMetricsComponent(),  # Priority 0 - first!
    # ... other components
]
```

### 2. Use Consistent Prefixes

```python
# ✅ CORRECT: Consistent versioning
health = HealthAndMetricsComponent(
    config=HealthComponentConfig(prefix="/api/v1")
)
agents = AgentsServerComponent(
    config=AgentsServerComponentConfig(prefix="/api/v1")
)
```

### 3. Configure for Container Environments

```python
# Kubernetes deployment example
health = HealthAndMetricsComponent()  # Default /health endpoint

# In your deployment.yaml:
# livenessProbe:
#   httpGet:
#     path: /health
#     port: 8000
#   initialDelaySeconds: 3
#   periodSeconds: 3
```

### 4. Exclude from Authentication

```python
# ✅ CORRECT: Health endpoint accessible without auth
from flock.components.server import (
    AuthenticationComponent,
    AuthenticationComponentConfig
)

auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="api_key",
        exclude_paths=[
            r"^/health$",      # ✅ Exclude health
            r"^/metrics$",     # ✅ Exclude metrics
        ]
    )
)
```

## Integration Examples

### Docker Healthcheck

```dockerfile
FROM python:3.12

# ... your application setup ...

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

### Kubernetes Probe

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: flock-app
spec:
  containers:
  - name: flock
    image: my-flock-app:latest
    ports:
    - containerPort: 8000
    livenessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 10
    readinessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 5
```

### Load Balancer Health Check

```python
# AWS Application Load Balancer expects /health endpoint
health = HealthAndMetricsComponent(
    config=HealthComponentConfig(prefix="")  # Use root path
)
# Creates: GET /health
```

## Future Enhancements

The metrics endpoint is designed for future expansion:

- **Agent Metrics** - Execution counts, success rates, duration
- **Artifact Metrics** - Published/consumed counts by type
- **System Metrics** - Memory, CPU, request rates
- **Custom Metrics** - Application-specific measurements

## Component Properties

- **Name:** `health`
- **Priority:** `0` (registered first)
- **Default Prefix:** `None` (root path)
- **Dependencies:** None
- **Middleware:** None
- **Lifecycle Hooks:** None

## Related Components

- **[TracingComponent](tracing-component.md)** - Advanced observability with OpenTelemetry
- **[MiddlewareComponent](middleware-component.md)** - Add logging/timing middleware
- **[CORSComponent](cors-component.md)** - Configure CORS for cross-origin health checks

## Example Code

See the complete example: **[examples/09-server-components/04_health_component.py](../../../examples/09-server-components/04_health_component.py)**

## Troubleshooting

### Health endpoint returns 404

**Problem:** `/health` endpoint not found

**Solution:** Check component registration order and prefix configuration

```python
# Check that health component is included
health = HealthAndMetricsComponent()
await flock.serve(components=[health])  # ✅

# Check prefix matches your requests
health = HealthAndMetricsComponent(
    config=HealthComponentConfig(prefix="/api/v1")
)
# Endpoint is now: /api/v1/health (not /health)
```

### Health check fails in Kubernetes

**Problem:** Kubernetes pod fails liveness probe

**Solution:** Ensure proper startup timing

```yaml
# Give app time to start before first check
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 15  # ⚠️ Increase if app takes time to start
  periodSeconds: 10
  failureThreshold: 3
```

### CORS blocking health checks

**Problem:** Browser-based health checks blocked by CORS

**Solution:** Configure CORS to allow health endpoint

```python
from flock.components.server import CORSComponent, CORSComponentConfig

cors = CORSComponent(
    config=CORSComponentConfig(
        allow_origins=["*"],  # For health checks
        allow_methods=["GET"],
    )
)

components = [
    HealthAndMetricsComponent(),
    cors,
    # ... other components
]
```
