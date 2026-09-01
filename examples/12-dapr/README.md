# 🐦 flock-dapr

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Flock ≥ 0.5](https://img.shields.io/badge/flock--core-%E2%89%A5%200.5-orange.svg)](https://pypi.org/project/flock-core/)
[![Dapr 1.13–1.14](https://img.shields.io/badge/dapr-1.13--1.14-blueviolet.svg)](https://dapr.io/)

> **Bring your own state store.**
> Plug any Dapr-supported backend — Redis, PostgreSQL, CosmosDB, and more — into
> [Flock](https://whiteducksoftware.github.io/flock/)'s Blackboard.

> Looking for docs-site version? See the
> [Dapr State Store Integration guide](https://whiteducksoftware.github.io/flock/guides/dapr-state-store/).

---

## Why flock-dapr?

Flock ships with an **in-memory** store and a **SQLite** store for local
development and single-node persistence.  That's great for prototyping, but
production workloads often need:

- 🔄 **Distributed state** — multiple Flock instances sharing a single
  blackboard (Redis, CosmosDB, …)
- 🔒 **Encryption at rest** — leveraging Dapr's built-in
  `primaryEncryptionKey` support
- ⏱️ **TTL-based expiration** — automatic cleanup of stale artifacts
- 🏗️ **Operational flexibility** — swap backends without changing
  application code

**flock-dapr** implements Flock's
[`BlackboardStore`](https://whiteducksoftware.github.io/flock/guides/persistent-blackboard/)
contract on top of [Dapr State Management](https://docs.dapr.io/developing-applications/building-blocks/state-management/),
so you can point Flock at *any* Dapr state-store component and keep the rest of
your agent code untouched.

---

## 🚀 Installation

From this repository root:

```bash
uv sync --extra dapr
```

For external projects:

```bash
uv add "flock-core[dapr]"
```

If you only need single-node durable history, consider SQLite first via the
[Persistent Blackboard guide](https://whiteducksoftware.github.io/flock/guides/persistent-blackboard/).

---

## ⚡ Quick Start

```python
import asyncio

from flock import Flock

from flock.storage import (
    DaprStateBlackboardConfig,
    DaprStateBlackboardStore,
    DaprStateBlackboardStoreClientConfig,
)

# 1. Configure the Dapr state store connection
client_config = DaprStateBlackboardStoreClientConfig()

store_config = DaprStateBlackboardConfig(
    store_name="flockstate",            # must match your Dapr component name
    supports_transactions=True,         # Redis, PostgreSQL, CosmosDB
    supports_etag=True,                 # optimistic concurrency control
    consistency="strong",               # "eventual" | "strong" | "unspecified"
    client_config=client_config,
)

# 2. Create the store and wire it into Flock
dapr_store = DaprStateBlackboardStore(config=store_config)

flock = Flock(
    model="openai/gpt-4.1",
    store=dapr_store,                   # ← swap in the Dapr backend
)

# 3. Define agents as usual — they know nothing about the backend
# bug_detector = flock.agent("bugs").consumes(Code).publishes(BugReport)

async def main():
    await flock.serve(dashboard=True)

asyncio.run(main())
```

That's it — your entire agent swarm now reads and writes through Dapr.  No
other code changes required. 🎉

---

## 🗄️ Supported Backends

flock-dapr works with **any** [Dapr state-store component](https://docs.dapr.io/reference/components-reference/supported-state-stores/).
The repository ships with ready-to-use example environments for three
backends:

| Backend | Example Directory | Encryption | Transactions | Query API | TTL |
|---|---|---|---|---|---|
| **In-memory** | `examples/12-dapr/inmemory/` | — | — | — | — |
| **Redis** (redis-stack, encrypted) | `examples/12-dapr/redis_encrypted/` | ✅ Primary + secondary key | Disabled by Flock for encrypted backends | ✅ | ✅ |
| **PostgreSQL 17** | `examples/12-dapr/postgresql_unencrypted/` | — | ✅ | — | — |

> **Tip:** All setups use the same `DaprStateBlackboardStore` class — only the
> Dapr component YAML and config flags change.

Other state stores known to work with Dapr (CosmosDB, DynamoDB, Cassandra, …)
should work out of the box; just provide the matching Dapr component definition
and adjust the config flags accordingly.

---

## ⚙️ Configuration

### `DaprStateBlackboardConfig`

| Field | Type | Default | Description |
|---|---|---|---|
| `store_name` | `str` | `"statestore"` | Dapr component name (`metadata.name` in the component YAML) |
| `supports_ttl` | `bool` | `False` | Enable TTL-based entry expiration (backend must support it) |
| `encrypted_backend` | `bool` | `False` | Indicate the backend uses Dapr encryption (`primaryEncryptionKey`) |
| `backend_encryption_key` | `str \| None` | `None` | Encryption key (only used when `encrypted_backend=True`) |
| `supports_transactions` | `bool` | `False` | Use `execute_state_transaction` where supported (Redis, PostgreSQL, CosmosDB) |
| `supports_dapr_query_lang` | `bool` | `False` | Use Dapr's query API for `query_artifacts` / `fetch_graph_artifacts` |
| `supports_etag` | `bool` | `False` | Optimistic concurrency control via ETags (first-write-wins options passed to Dapr) |
| `etag_max_retries` | `int` | `3` | Reserved for follow-up ETag retry hardening |
| `consistency` | `str` | `"unspecified"` | Consistency level: `"eventual"`, `"strong"`, or `"unspecified"` |
| `entries_ttl_seconds` | `int \| None` | `None` | TTL in seconds for state entries (requires `supports_ttl=True`) |
| `client_config` | `...ClientConfig \| None` | `None` | Optional Dapr client settings (see below) |

### `DaprStateBlackboardStoreClientConfig`

| Field | Type | Default | Description |
|---|---|---|---|
| `dapr_grpc_endpoint` | `str \| None` | `None` | Dapr runtime gRPC address (e.g. `localhost:50001`) |
| `headers_callback` | `Callable \| None` | `None` | Callable returning `dict[str, str]` headers per request |
| `interceptors` | `list[...] \| None` | `None` | gRPC client interceptors |
| `http_timeout_seconds` | `int \| None` | `None` | HTTP timeout for Dapr connections |
| `max_grpc_message_length` | `int \| None` | `None` | Max gRPC message size in bytes |
| `retry_policy` | `RetryPolicy \| None` | `None` | Dapr SDK retry policy |

---

## 🏗️ Architecture

```
┌─────────────────────────────┐
│        Your Flock App       │
│  agents · types · workflows │
└────────────┬────────────────┘
             │  store=dapr_store
┌────────────▼────────────────┐
│  DaprStateBlackboardStore   │
│  serialize · index · r/w    │
└────────────┬────────────────┘
             │  gRPC
┌────────────▼────────────────┐
│       Dapr Sidecar          │
│  state management building  │
│  block + encryption + TTL   │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│   State Store Component     │
│  Redis · PostgreSQL · ...   │
└─────────────────────────────┘
```

### Key Design Decisions

- **Transactional vs non-transactional paths** — When the backend supports
  transactions, index updates use `execute_state_transaction` where possible.
  Artifact data may still be saved separately when TTL metadata is needed.
  When encryption is enabled, transactions are automatically disabled (see
  [Known Limitations](#-known-limitations)) and the store falls back to
  individual `save_state` calls with lazy index reconciliation on read. Full
  artifact/index atomicity hardening is tracked in
  [issue #415](https://github.com/whiteducksoftware/flock/issues/415).

- **Index-based key management** — Dapr state stores are key-value stores.
  flock-dapr maintains secondary indexes manually:

  | Key pattern | Value |
  |---|---|
  | `artifact:{uuid}` | Serialized `Artifact` JSON |
  | `idx:artifacts` | JSON list of all artifact UUID strings |
  | `idx:type:{type_name}` | JSON list of UUIDs for that artifact type |
  | `consumptions:{artifact_id}` | JSON list of `ConsumptionRecord` dicts |
  | `snapshot:{agent_name}` | Serialized `AgentSnapshotRecord` JSON |
  | `idx:snapshots` | JSON list of agent name strings |

- **Custom serialization layer** — Artifacts use Pydantic's built-in
  serialization; dataclass-based types (`ConsumptionRecord`,
  `AgentSnapshotRecord`) are handled via a dedicated
  [serialization module](../../src/flock/storage/dapr/_serialization.py) that deals with
  `UUID`, `datetime`, and visibility discriminators.

---

## ⚠️ Known Limitations

| Limitation | Details |
|---|---|
| **Encryption disables transactions** | Dapr's Go runtime corrupts values in `ExecuteStateTransaction` before encrypting (converts `[]byte` via `fmt.Appendf`). flock-dapr auto-detects this and falls back to non-transactional writes. Index consistency is maintained via lazy reconciliation. |
| **Query API varies by backend** | `supports_dapr_query_lang=True` requires a backend that implements [Dapr's query API](https://docs.dapr.io/developing-applications/building-blocks/state-management/howto-state-query-api/) (e.g. Redis with RediSearch). PostgreSQL v2 does not support it. |
| **TTL depends on the state store** | Set `supports_ttl=True` only if the backing store actually supports TTL; otherwise Dapr will return errors. |
| **No distributed locking** | Concurrent writes from multiple Flock instances to the same index can race. `supports_etag=True` passes ETags to Dapr writes where supported; automatic conflict retry and stronger atomicity guarantees are tracked in [issue #415](https://github.com/whiteducksoftware/flock/issues/415). |

---

## 🛠️ Development Setup

The `examples/` directory ships three Docker Compose stacks — one for each
reference backend.  **They share the same host ports, so run only one at a
time.**

### 1. Choose a backend

**In-memory (simplest — no external services):**

```bash
cd examples/12-dapr/inmemory
cp secrets.example.json secrets.json   # fill in your LLM API key, model, etc.
docker compose up -d
```

> State lives inside the Dapr sidecar and is lost on restart.  Great for quick
> iteration without any database dependencies.

**Redis (encrypted):**

```bash
cd examples/12-dapr/redis_encrypted
cp secrets.example.json secrets.json   # fill in your LLM API key, model, etc.
docker compose up -d
```

**PostgreSQL (unencrypted):**

```bash
cd examples/12-dapr/postgresql_unencrypted
cp secrets.example.json secrets.json   # fill in your LLM API key, model, etc.
docker compose up -d
```

### 2. Configure secrets

> `daprd` runs as a non-root user inside the container. `secrets.json` must be
> readable by it (`chmod 644 secrets.json`), otherwise the secret store fails to
> initialize and the sidecar exits.

Edit `secrets.json` with your values:

```jsonc
{
    "api_key": "sk-...",                   // your LLM API key
    "base_url": "https://...",             // LLM endpoint
    "api_version": "2024-12-01-preview",   // API version (Azure OpenAI)
    "state_store_name": "flockstate",      // must match component YAML
    "default_model": "openai/gpt-4.1"     // model identifier
}
```

  Note: the Redis example also expects `default_model` in `secrets.json`.

### 3. Run an example

```bash
# Make sure the Dapr sidecar is reachable
export DAPR_GRPC_ENDPOINT="localhost:50001"

# In-memory example
uv run python examples/12-dapr/inmemory/flock_dapr_inmemory.py

# Redis example
uv run python examples/12-dapr/redis_encrypted/flock_dapr_redis.py

# PostgreSQL example
uv run python examples/12-dapr/postgresql_unencrypted/flock_dapr_postgresql.py
```

### 4. Peeking at the state store

Dapr stores Redis state as a hash, keys are prefixed with the app id:

```bash
docker exec redis redis-cli -a 'flock-redis-dev-2026!' --no-auth-warning --scan --pattern '*artifact:*' | head
docker exec redis redis-cli -a 'flock-redis-dev-2026!' --no-auth-warning HGET '<key>' data   # ciphertext on the encrypted stack
```

The stacks keep their data in named Docker volumes; `docker compose down -v`
removes them.

### 5. Dapr component files

Each example stack ships three component definitions under `components/`:

| File | Purpose |
|---|---|
| `secretstore.yaml` | Local file-based secret store (`secrets.json`) |
| `statestore.yaml` | State store component (in-memory, Redis, or PostgreSQL) |
| `resiliency.yaml` | Retry and circuit-breaker policies |

---

<p align="center">
  Built with 🦆 by <a href="https://whiteduck.de/">white duck GmbH</a>
</p>
