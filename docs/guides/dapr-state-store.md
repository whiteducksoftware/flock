---
title: Dapr State Store Integration
description: Use Dapr-supported state stores as an optional distributed blackboard backend for Flock.
tags:
  - blackboard
  - persistence
  - dapr
  - integrations
search:
  boost: 1.4
---

# Dapr State Store Integration

Flock includes Dapr-backed blackboard storage as an optional feature. This lets you keep your existing agent and artifact model while switching the backend from local storage to any Dapr-supported state store.

Use Dapr storage when you need distributed state, backend-level encryption, or backend-specific TTL and query capabilities.

---

## Install

For this repository:

```bash
uv sync --extra dapr
```

For external projects using Flock:

```bash
uv add "flock-core[dapr]"
```

If you only need local durable history in a single process, prefer SQLite via [Persistent Blackboard History](persistent-blackboard.md).

---

## Quick Start

```python
from flock import Flock
from flock.storage import (
    DaprStateBlackboardConfig,
    DaprStateBlackboardStore,
    DaprStateBlackboardStoreClientConfig,
)

client_config = DaprStateBlackboardStoreClientConfig(
    dapr_grpc_endpoint="localhost:50001",
)

store_config = DaprStateBlackboardConfig(
    store_name="flockstate",       # must match Dapr component metadata.name
    supports_transactions=True,
    supports_etag=True,
    consistency="strong",          # eventual | strong | unspecified
    client_config=client_config,
)

store = DaprStateBlackboardStore(config=store_config)

flock = Flock(
    model="openai/gpt-4.1",
    store=store,
)
```

The rest of your agent setup stays unchanged.

### Backend Capability Notes

- `supports_transactions=True` is recommended for unencrypted Redis/PostgreSQL backends.
- For encrypted Redis (`encrypted_backend=True`), transactions are automatically disabled by the store implementation because of a Dapr runtime limitation.
- Enable `supports_dapr_query_lang=True` only when your selected state store/component actually supports Dapr query API.

---

## Backend Matrix

The examples in this repository include three reference Dapr setups:

| Backend | Example Directory | Encryption | Transactions | Query API | TTL |
| --- | --- | --- | --- | --- | --- |
| In-memory | `examples/12-dapr/inmemory/` | No | No | No | No |
| Redis (encrypted) | `examples/12-dapr/redis_encrypted/` | Yes | No (auto-disabled) | Yes | Yes |
| PostgreSQL 17 | `examples/12-dapr/postgresql_unencrypted/` | No | Yes | No | No |

---

## Configuration Reference

### DaprStateBlackboardConfig

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| store_name | str | statestore | Dapr component name (metadata.name) |
| supports_ttl | bool | False | Enable TTL-based expiration if backend supports TTL |
| encrypted_backend | bool | False | Use Dapr encryption metadata path |
| backend_encryption_key | str \| None | None | Optional encryption key when encrypted backend is enabled |
| supports_transactions | bool | False | Use execute_state_transaction where supported |
| supports_dapr_query_lang | bool | False | Enable Dapr query API paths |
| supports_etag | bool | False | Pass ETags to Dapr writes for optimistic concurrency |
| etag_max_retries | int | 3 | Reserved for follow-up ETag retry hardening |
| consistency | str | unspecified | eventual, strong, or unspecified |
| entries_ttl_seconds | int \| None | None | TTL in seconds when supports_ttl is enabled |
| client_config | DaprStateBlackboardStoreClientConfig \| None | None | Optional Dapr client settings |

### DaprStateBlackboardStoreClientConfig

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| dapr_grpc_endpoint | str \| None | None | Dapr gRPC endpoint, for example localhost:50001 |
| headers_callback | Callable \| None | None | Request headers callback |
| interceptors | list \| None | None | gRPC interceptors |
| http_timeout_seconds | int \| None | None | HTTP timeout for Dapr SDK calls |
| max_grpc_message_length | int \| None | None | Max gRPC message size |
| retry_policy | RetryPolicy \| None | None | Dapr SDK retry policy |

---

## Known Limitations

- Encryption and transactions cannot be combined due to a Dapr runtime transaction serialization issue; Flock automatically falls back to non-transactional writes for encrypted backends.
- Dapr query support depends on the selected state store and component implementation.
- TTL support depends on backend capabilities.
- Distributed writes can still race across multiple Flock instances. ETags are passed where supported; automatic conflict retry and stronger atomicity guarantees are tracked in [issue #415](https://github.com/whiteducksoftware/flock/issues/415).

---

## Run The Example Stacks

Only run one backend stack at a time because they share host ports.

1. In-memory backend:

```bash
cd examples/12-dapr/inmemory
cp secrets.example.json secrets.json
docker compose up -d
```

2. Redis encrypted backend:

```bash
cd examples/12-dapr/redis_encrypted
cp secrets.example.json secrets.json
docker compose up -d
```

3. PostgreSQL backend:

```bash
cd examples/12-dapr/postgresql_unencrypted
cp secrets.example.json secrets.json
docker compose up -d
```

For all three setups, copy `secrets.example.json` to `secrets.json` and fill in required keys before running.

Then run the matching example script from repository root:

```bash
export DAPR_GRPC_ENDPOINT="localhost:50001"

uv run python examples/12-dapr/inmemory/flock_dapr_inmemory.py
# or
uv run python examples/12-dapr/redis_encrypted/flock_dapr_redis.py
# or
uv run python examples/12-dapr/postgresql_unencrypted/flock_dapr_postgresql.py
```

---

## Choosing SQLite vs Dapr

- Choose SQLite for single-node durable history and simple local operations.
- Choose Dapr for shared distributed state, pluggable backend infrastructure, and backend-specific capabilities.

For SQLite-focused persistence and dashboard history workflows, see the [Persistent Blackboard guide](persistent-blackboard.md).

For full Dapr example details, see [examples/12-dapr/README.md](https://github.com/whiteducksoftware/flock/tree/main/examples/12-dapr/README.md).

You can also browse runnable setup variants in [Examples Index](../examples/index.md).
