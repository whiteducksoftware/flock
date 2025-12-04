---
title: Server Components Concepts
description: Understanding how server components extend Flock's HTTP capabilities
tags:
  - getting-started
  - server
  - components
  - api
search:
  boost: 1.0
---

# Server Components Concepts

**Extend Flock's built-in HTTP server with modular components.**

When you call `flock.serve()`, Flock starts an HTTP server that can be extended with server components. These components add REST endpoints, WebSocket support, health checks, and more.

---

## What Are Server Components?

Server components are modular pieces that plug into Flock's HTTP server. Each component adds specific functionality:

| Component | Purpose |
|-----------|---------|
| **ArtifactsComponent** | REST API for artifacts |
| **WebSocketComponent** | Real-time streaming |
| **HealthComponent** | Health checks & metrics |
| **AgentsComponent** | Agent status endpoints |
| **CORSComponent** | Cross-origin requests |
| **StaticFilesComponent** | Serve dashboard files |

---

## Default Components

When you start the server, several components are enabled by default:

```python
await flock.serve(dashboard=True)

# Default components:
# - ArtifactsComponent (GET/POST /api/v1/artifacts)
# - WebSocketComponent (/ws)
# - HealthComponent (/health, /metrics)
# - AgentsComponent (/api/v1/agents)
```

---

## Adding Custom Components

You can add or configure components before starting the server:

```python
from flock import Flock
from flock.components.server import (
    CORSComponent, CORSComponentConfig,
    HealthComponentConfig, HealthAndMetricsComponent,
)

flock = Flock("openai/gpt-4.1")

# Add CORS support
flock.add_server_component(CORSComponent(
    config=CORSComponentConfig(
        allow_origins=["https://myapp.com"],
        allow_methods=["GET", "POST"],
    )
))

# Customize health checks
flock.add_server_component(HealthAndMetricsComponent(
    config=HealthComponentConfig(
        include_metrics=True,
        custom_checks={"database": check_db_connection}
    )
))

await flock.serve(dashboard=True)
```

---

## Component Lifecycle

Server components have lifecycle hooks:

1. **on_startup** - Called when server starts
2. **register_routes** - Add HTTP routes
3. **on_shutdown** - Called when server stops

```python
from flock.components.server import ServerComponent

class MyComponent(ServerComponent):
    async def on_startup(self, app):
        print("Server starting...")
    
    def register_routes(self, app):
        @app.get("/my-endpoint")
        async def my_endpoint():
            return {"status": "ok"}
    
    async def on_shutdown(self, app):
        print("Server stopping...")
```

---

## Learn More

- [Server Components Guide](../guides/server-components.md) - Complete reference
- [REST API Guide](../guides/rest-api.md) - API endpoints
- [Dashboard Guide](../guides/dashboard.md) - Real-time monitoring
