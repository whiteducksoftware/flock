# 🔌 REST API Integration

> **Status:** 🚧 Coming Soon

This section will demonstrate how to integrate Flock with REST APIs and external services:

## Planned Examples

**01_fastapi_integration.py**
- Serving Flock workflows via FastAPI
- HTTP endpoints that publish artifacts
- RESTful agent orchestration

**02_webhook_consumer.py**
- Consuming external webhooks
- Event-driven workflows
- Integration with third-party services

**03_api_client.py**
- Agents that call external APIs
- HTTP clients with `@flock_tool`
- Rate limiting and retry logic

## In the Meantime

Flock already has API serving built-in:
```python
await flock.serve(dashboard=True)
# Dashboard includes REST API endpoints
```

For tool integration examples, see:
- ✅ [01-the-declarative-way/](../01-the-declarative-way/) - Example 03 shows MCP and tools integration

## Want to Contribute?

We'd love help creating these examples! If you're interested:
1. Check the [Contributing Guide](../../CONTRIBUTING.md)
2. Open an issue to discuss your example idea
3. Submit a PR with well-documented code

---

*This example set is part of our roadmap. Follow the repo for updates!*
