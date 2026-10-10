# 🗺️ Flock Roadmap to 1.0

Flock 0.5 is the current release line (`flock-core` on PyPI). The open backlog below is planned for **Flock 1.0 in Q4 2026**. Every item links to its GitHub issue, which holds the scope and the current state.

---

## ✅ Available in 0.5

- **Blackboard core:** typed artifacts, declarative subscriptions with predicates, joins, batches and semantic matching, fan-out publishing, visibility (public, private, tenant, label and time based), circuit breakers.
- **Decision models:** `Choice`, `YesNo`, `Scale` and `Checklist` questions with calibrated probabilities, tournaments for large choices, decision networks, rate limits per provider.
- **Storage:** in-memory, SQLite and Dapr blackboard stores with history queries and retention.
- **Scheduling:** interval, daily, one-time and cron timers.
- **REST API:** publish (sync and async), artifact listing, schema discovery, correlation status, idempotency keys, OpenAPI, custom endpoints and webhooks.
- **Hosting:** application hosting, including Microsoft Foundry.
- **Observability:** real-time dashboard, OpenTelemetry tracing with DuckDB storage.
- **Tools and media:** MCP tools, images in artifacts and decisions.

---

## 🚀 Flock 1.0 (Q4 2026)

### Safe access and data protection
- Authenticated API, dashboard and WebSocket access with per-recipient visibility ([#280](https://github.com/whiteducksoftware/flock/issues/280), [#430](https://github.com/whiteducksoftware/flock/issues/430), [#431](https://github.com/whiteducksoftware/flock/issues/431), [#432](https://github.com/whiteducksoftware/flock/issues/432)).
- Private input data kept out of error artifacts, trace data minimized and redacted before export ([#428](https://github.com/whiteducksoftware/flock/issues/428), [#429](https://github.com/whiteducksoftware/flock/issues/429)).

### Bounded execution
- Bounded admission and global concurrency, bounded AND/batch/join collections, context and execution budgets ([#440](https://github.com/whiteducksoftware/flock/issues/440), [#441](https://github.com/whiteducksoftware/flock/issues/441), [#442](https://github.com/whiteducksoftware/flock/issues/442)).

### Runs: history, interruption and control
- Run history in SQLite that survives restarts, interrupted runs shown after a restart without auto-resume, terminal outcomes preserved ([#433](https://github.com/whiteducksoftware/flock/issues/433), [#443](https://github.com/whiteducksoftware/flock/issues/443), [#444](https://github.com/whiteducksoftware/flock/issues/444)).
- Run cancellation, pause of new starts and workflow lifecycle controls ([#446](https://github.com/whiteducksoftware/flock/issues/446), [#294](https://github.com/whiteducksoftware/flock/issues/294)).
- Correlation status from actual work, connected run views with per-run live output ([#434](https://github.com/whiteducksoftware/flock/issues/434), [#445](https://github.com/whiteducksoftware/flock/issues/445)).

### Dashboard and API
- UI rework, dashboard state reconciled after reconnects, image support across the dashboard ([#374](https://github.com/whiteducksoftware/flock/issues/374), [#447](https://github.com/whiteducksoftware/flock/issues/447), [#464](https://github.com/whiteducksoftware/flock/issues/464)).
- Fixes for CLI `serve`, read-only tracing settings, history pagination and complex publish inputs ([#435](https://github.com/whiteducksoftware/flock/issues/435), [#436](https://github.com/whiteducksoftware/flock/issues/436), [#437](https://github.com/whiteducksoftware/flock/issues/437), [#438](https://github.com/whiteducksoftware/flock/issues/438)).
- Explanations for why a subscription is waiting or did not trigger ([#448](https://github.com/whiteducksoftware/flock/issues/448)).

### Agents and decisions
- Agent skills: instruction skills and bounded reference tools ([#449](https://github.com/whiteducksoftware/flock/issues/449), [#450](https://github.com/whiteducksoftware/flock/issues/450)).
- Decision networks: escalation, ensembles, aggregation, calibration, shadow mode and human review ([#474](https://github.com/whiteducksoftware/flock/issues/474)).
- Serialization of blackboard state and agents ([#274](https://github.com/whiteducksoftware/flock/issues/274)).

### Reliability and deployment
- Advanced retries and dead-letter queues, Dapr store hardening ([#277](https://github.com/whiteducksoftware/flock/issues/277), [#415](https://github.com/whiteducksoftware/flock/issues/415)).
- Kafka event backbone and Kubernetes deployment tooling ([#278](https://github.com/whiteducksoftware/flock/issues/278), [#279](https://github.com/whiteducksoftware/flock/issues/279)).

### Quality and release
- Application-factory entry point and deterministic onboarding ([#439](https://github.com/whiteducksoftware/flock/issues/439)).
- Benchmarking suite, evaluation harness and production pilots ([#275](https://github.com/whiteducksoftware/flock/issues/275), [#276](https://github.com/whiteducksoftware/flock/issues/276), [#285](https://github.com/whiteducksoftware/flock/issues/285)).
- Release qualification and operating guidance ([#451](https://github.com/whiteducksoftware/flock/issues/451), [#452](https://github.com/whiteducksoftware/flock/issues/452)).
- DSPy 3.4 upgrade once the upstream fix is released ([#499](https://github.com/whiteducksoftware/flock/issues/499)).

---

The [issue tracker](https://github.com/whiteducksoftware/flock/issues) is the source of truth; this page summarizes it. Release notes are in the [changelog](docs/about/changelog.md). For enterprise questions, contact [support@whiteduck.de](mailto:support@whiteduck.de).
