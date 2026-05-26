---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Deployment 🚀

Getting a prototype running locally is great; putting it in production requires reliability, observability, and scalability.  Flock ships with first-class **Temporal** integration which gives you all three out of the box.

---

## 1. Local vs. Temporal

| Aspect | Local Mode (default) | Temporal Mode |
| ------ | ------------------- | ------------- |
| Fault Tolerance | Exceptions bubble to caller | Automatic retries, timeouts, watchdogs |
| State Persistence | Memory-only | Durable (DB, visibility store) |
| Concurrency | Single Python process | Horizontal scaling across workers |
| Visibility | Stdout + logs | Temporal Web UI, Prometheus, Grafana |

Switching modes is as easy as:

```python
flock = Flock(enable_temporal=True, temporal_config=TemporalWorkflowConfig(...))
```

---

## 2. Production Checklist

1. **Secrets Management** – Store LLM API keys in Vault, AWS Parameter Store, etc.
2. **Observability** – Export OpenTelemetry traces to Jaeger or Tempo.
3. **Autoscaling** – Use `temporal worker --concurrency` or K8s HPA.
4. **Caching** – Enable evaluator cache (Redis, Memcached, or `litellm` built-in).
5. **Security** – Restrict tool access; disable `cloudpickle` deserialization if loading untrusted payloads.

---

## 3. Reference Architectures

### Docker Compose (PoC)

* api (FastAPI) + flock code
* Temporal server (Cadence) or temporal-io docker image
* Prometheus + Grafana for metrics

### Kubernetes (Prod)

* Flock API image
* Temporal Cluster (6-service helm chart)
* Workers scaled by queue
* OpenTelemetry Collector → Tempo → Grafana

---

## 4. Next Steps

* Learn the details in [Temporal Deployment](temporal.md).
* Check the `scripts/` folder for helper shell scripts.
* Browse `tests/` for smoke tests that validate a cluster.
