# Server Components Examples

This directory contains comprehensive examples demonstrating Flock's server component system - a modular, composable architecture for extending the HTTP API server.

## 📚 What are Server Components?

Server Components are reusable modules that extend Flock's HTTP server with custom middleware, routes, and lifecycle management. They follow the same pattern as Agent Components but operate at the HTTP server level.

**Learn more:** [Server Components Concepts](../../docs/getting-started/server-components-concepts.md)

---

## 🎯 Examples by Category

### Security Components

1. **[01_authentication_component.py](01_authentication_component.py)** ⭐ Start Here!
   - API key authentication
   - JWT token authentication
   - Route-specific authentication handlers
   - Excluded paths (public endpoints)
   - Custom error responses
   - Multiple authentication strategies

2. **[02_cors_component.py](02_cors_component.py)**
   - Global CORS settings
   - Origin regex patterns
   - Route-specific CORS overrides
   - Exposed headers configuration
   - Max age and credentials control

3. **[03_middleware_component.py](03_middleware_component.py)**
   - Custom timing middleware
   - Custom header middleware
   - GZip compression
   - Middleware factories
   - Multiple middleware composition

---

### Infrastructure Components

4. **[04_health_component.py](04_health_component.py)**
   - Basic health check endpoint
   - Prometheus-style metrics
   - Configuring endpoint paths
   - Integration with monitoring systems

5. **[11_tracing_component.py](11_tracing_component.py)**
   - OpenTelemetry trace collection
   - Trace export and visualization
   - Custom trace configuration
   - Integration with observability platforms

---

### Business Logic Components

6. **[05_websocket_component.py](05_websocket_component.py)**
   - Basic WebSocket connection
   - Real-time event streaming
   - Connection management
   - Broadcasting agent events

7. **[06_artifacts_component.py](06_artifacts_component.py)**
   - REST API for querying artifacts
   - Publishing artifacts via HTTP POST
   - Pagination and filtering
   - Integration with blackboard storage

8. **[07_agents_component.py](07_agents_component.py)**
   - List all registered agents
   - Get agent details and metadata
   - View agent subscriptions
   - REST API integration

9. **[08_control_routes_component.py](08_control_routes_component.py)**
   - Invoking specific agents via REST API
   - Passing input artifacts to agents
   - Controlling agent execution
   - Monitoring agent responses

---

### Presentation Components

10. **[09_static_files_component.py](09_static_files_component.py)**
    - Serving static files (HTML, CSS, JS)
    - SPA (Single Page Application) routing
    - Custom directory configuration
    - Priority management (must be last!)

11. **[10_themes_component.py](10_themes_component.py)**
    - Custom theme configuration
    - Dashboard appearance customization
    - Theme API endpoints
    - Real-time theme switching

---

### Complete Examples

12. **[12_complete_composition.py](12_complete_composition.py)** ⭐ Best Example!
    - Production-ready server setup
    - Health monitoring
    - CORS configuration
    - Authentication
    - WebSocket real-time updates
    - REST API for agents and artifacts
    - Distributed tracing
    - Complete workflow demonstration

---

## 🚀 Quick Start

Run any example:

```bash
# Basic authentication
uv run python examples/09-server-components/01_authentication_component.py

# CORS configuration
uv run python examples/09-server-components/02_cors_component.py

# Complete production setup
uv run python examples/09-server-components/12_complete_composition.py
```

Each example:
- ✅ Runs standalone (no dependencies on other examples)
- ✅ Includes detailed comments and explanations
- ✅ Demonstrates best practices
- ✅ Shows common use cases
- ✅ Provides curl examples for testing

---

## 📖 Learning Path

**New to Server Components?** Follow this path:

1. **[Server Components Concepts](../../docs/getting-started/server-components-concepts.md)** (15 min)
   - Understand the architecture
   - Learn the lifecycle
   - Master the priority system

2. **[01_authentication_component.py](01_authentication_component.py)** (5 min)
   - See how components work in practice
   - Learn the basic structure
   - Test with curl commands

3. **[12_complete_composition.py](12_complete_composition.py)** (10 min)
   - See production-ready setup
   - Understand component composition
   - Learn priority ordering

4. **[Server Components Guide](../../docs/guides/server-components.md)** (ongoing)
   - Complete API reference
   - All built-in components
   - Custom component patterns

---

## 🔑 Key Concepts

### Priority System

Components register in priority order (lower numbers first):

| Priority | Purpose | Examples |
|----------|---------|----------|
| 0-5 | Core infrastructure | Health, metrics |
| 6-10 | Security layer | CORS, auth, rate limiting |
| 11-50 | Business logic | Agents, artifacts, control |
| 51-99 | Static assets | Dashboard UI, static files |

**Rule:** Static files MUST have highest priority (99) - they use catch-all routes!

### Component Lifecycle

```
1. __init__()                    # Component creation
2. configure(app, orchestrator)  # Configure FastAPI app
3. register_routes(app, orchestrator)  # Add endpoints
4. on_startup_async(orchestrator)  # Async startup tasks
5. ...service runs...
6. on_shutdown_async(orchestrator)  # Async cleanup
```

### Composition Pattern

```python
# ✅ CORRECT: Mix and match components
await flock.serve(
    components=[
        HealthAndMetricsComponent(priority=0),
        CORSComponent(priority=8),
        AuthenticationComponent(priority=7),
        AgentsServerComponent(priority=20),
        StaticFilesServerComponent(priority=99),  # Last!
    ]
)
```

---

## 🎯 Common Use Cases

### Minimal Server (Health Only)

```python
await flock.serve(
    components=[HealthAndMetricsComponent()]
)
```

### Public API with Security

```python
await flock.serve(
    components=[
        HealthAndMetricsComponent(priority=0),
        CORSComponent(priority=8),
        AuthenticationComponent(priority=7),
        AgentsServerComponent(priority=20),
        ArtifactsComponent(priority=20),
    ]
)
```

### Full Dashboard Server

```python
await flock.serve(
    components=[
        HealthAndMetricsComponent(priority=0),
        CORSComponent(priority=8),
        WebSocketServerComponent(priority=15),
        AgentsServerComponent(priority=20),
        ArtifactsComponent(priority=20),
        StaticFilesServerComponent(priority=99),
    ]
)
```

---

## 💡 Best Practices

### ✅ DO

- Use correct priorities (infrastructure → security → business → static)
- Declare dependencies with `get_dependencies()`
- Handle errors in middleware
- Clean up resources in `on_shutdown_async()`
- Use configuration objects for settings

### ❌ DON'T

- Put static files with low priority (breaks routing!)
- Skip error handling in auth handlers
- Forget to clean up resources
- Hardcode paths (use `_join_path()` helper)

---

## 📚 Related Documentation

- **[Server Components Concepts](../../docs/getting-started/server-components-concepts.md)** - Architecture and design patterns
- **[Server Components Guide](../../docs/guides/server-components.md)** - Complete API reference
- **[REST API Guide](../../docs/guides/rest-api.md)** - HTTP API documentation
- **[Agent Components](../../docs/guides/components.md)** - Agent-level components
- **[Orchestrator Components](../../docs/guides/orchestrator-components.md)** - Orchestrator-level components

---

## 🆘 Need Help?

- 📖 **Documentation:** [Server Components Guide](../../docs/guides/server-components.md)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/whiteducksoftware/flock/discussions)
- 🐛 **Issues:** [GitHub Issues](https://github.com/whiteducksoftware/flock/issues)

---

**Ready to start?** → [01_authentication_component.py](01_authentication_component.py)
