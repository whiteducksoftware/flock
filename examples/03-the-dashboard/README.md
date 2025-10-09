# 📊 Dashboard UI

> **Status:** 🚧 Coming Soon

This section will showcase Flock's real-time dashboard and visualization capabilities:

## Planned Examples

**01_basic_dashboard.py**
- Starting the dashboard with `flock.serve(dashboard=True)`
- Understanding Agent View vs Blackboard View
- Real-time WebSocket updates

**02_trace_viewer.py**
- Using `traced_run()` for workflow tracing
- Exploring the 7 trace viewer modes
- AI-queryable DuckDB traces

**03_production_monitoring.py**
- Setting up production observability
- Custom metrics and alerts
- Performance profiling

## In the Meantime

The dashboard is already available! Just run:
```python
await flock.serve(dashboard=True)
# Then visit http://localhost:8000
```

For trace examples, see:
- ✅ [05-claudes-workshop/](../05-claudes-workshop/) - Lesson 05 (Tracing Detective) covers distributed tracing

## Want to Contribute?

We'd love help creating these examples! If you're interested:
1. Check the [Contributing Guide](../../CONTRIBUTING.md)
2. Open an issue to discuss your example idea
3. Submit a PR with well-documented code

---

*This example set is part of our roadmap. Follow the repo for updates!*
