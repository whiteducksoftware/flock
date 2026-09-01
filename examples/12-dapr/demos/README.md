# 🧪 Dapr demos: kill it, share it

Two short, reproducible demos on top of the [encrypted Redis stack](../redis_encrypted/):

| Demo | Question it answers | Files |
|---|---|---|
| **1 · Kill it. It comes back.** | What happens to the blackboard when the Flock process dies? | `writer.py`, `payloads/band_concept_*.json` |
| **2 · One blackboard, many Flocks** | Can two Flock processes share one blackboard through Dapr — and what *don't* they share yet? | `writer.py` + `reader.py`, `payloads/marketing_copy.json` |

Both demos use the same three-agent band pipeline as the other Dapr examples
(`BandConcept → BandLineup → Album → MarketingCopy`). The only Dapr-specific
line in the agent code is `store=make_store(...)`; everything else is plain Flock.

```
writer.py  (:8344)  ─┐
                     ├─ gRPC :50001 ─▶ daprd ─▶ Redis Stack (encrypted at rest)
reader.py  (:8345)  ─┘
```

## Prerequisites

- Docker with Compose v2
- This repository with the Dapr extra: `uv sync --extra dapr`
- An LLM endpoint. The stack reads credentials from a Dapr **secret store**
  (`components/secretstore.yaml` → `secrets.json`), so nothing is hard-coded.
- `curl` and `jq` for the driver commands below

No Dapr CLI is needed — the Compose file brings its own `daprd`, placement and
scheduler.

## Setup (once)

```bash
cd examples/12-dapr/redis_encrypted
cp secrets.example.json secrets.json
chmod 644 secrets.json      # daprd runs as a non-root user inside the container and must be able to read it
```

Fill in `secrets.json`:

| Key | Value |
|---|---|
| `redis_password` | must match `--requirepass` in `docker-compose.yml` (`flock-redis-dev-2026!`) |
| `encryption_key`, `encryption_key_backup` | two AES keys, hex-encoded, 128/192/256 bit — e.g. `openssl rand -hex 16` |
| `api_key`, `base_url`, `api_version` | your LLM endpoint. For Azure OpenAI: key, `https://<resource>.openai.azure.com`, API version |
| `state_store_name` | `flockstate` (must equal `metadata.name` in `components/statestore.yaml`) |
| `default_model` | e.g. `azure/gpt-4.1` or `openai/gpt-4.1` (`_common.py` exports the matching provider variables) |

`secrets.json` is git-ignored. Keep it that way.

Start the stack and check that the sidecar loaded the component:

```bash
docker compose up -d
docker compose ps                                # flock-dapr, placement, scheduler, redis: Up
docker compose logs flock-dapr | grep -i "flockstate"
```

All commands below run from the repository root with the sidecar address exported:

```bash
cd ../../..
export DAPR_GRPC_ENDPOINT=localhost:50001
```

## Demo 1 — Kill it. It comes back.

**Terminal 1 — the writer**

```bash
uv run python examples/12-dapr/demos/writer.py          # dashboard + REST on http://localhost:8344
```

The first start builds the dashboard frontend (npm) and opens a browser tab;
after that a start takes about ten seconds.

**Terminal 2 — the driver**

```bash
# 1. publish one BandConcept and watch the three agents cascade
curl -s -X POST localhost:8344/api/v1/artifacts -H 'content-type: application/json' \
  -d @examples/12-dapr/demos/payloads/band_concept_1.json | jq
watch -n2 'curl -s localhost:8344/api/v1/artifacts | jq -r ".items[] | .type"'   # ~25 s until MarketingCopy shows up

# 2. look at the bytes: encrypted at rest, decrypted only by the sidecar
docker exec redis redis-cli -a 'flock-redis-dev-2026!' --no-auth-warning --scan --pattern '*artifact:*' | head -3
docker exec redis redis-cli -a 'flock-redis-dev-2026!' --no-auth-warning HGET "<one key from above>" data
#   keys look like flock-dev||artifact:<uuid>; Dapr stores Redis state as a hash and the data field is ciphertext

# 3. kill the writer, hard   (the [d] keeps pkill from matching its own shell)
pkill -9 -f '[d]emos/writer.py'
docker exec redis redis-cli -a 'flock-redis-dev-2026!' --no-auth-warning DBSIZE      # unchanged

# 4. start the writer again (terminal 1), then:
curl -s localhost:8344/api/v1/artifacts | jq '.items | length'                          # 4 — nothing was lost
curl -s 'localhost:8344/api/v1/artifacts?type=MarketingCopy' | jq '.items[0].payload.billboard_tagline'

# 5. keep going
curl -s -X POST localhost:8344/api/v1/artifacts -H 'content-type: application/json' \
  -d @examples/12-dapr/demos/payloads/band_concept_2.json | jq
```

What to notice:

- The restarted process has the same `store_name` and the same agents. It does
  **not** re-run anything: the artifacts and their consumption records are
  simply there, in the dashboard and via REST.
- The consumption records survive too: `GET /api/v1/artifacts?embed_meta=true`
  still shows which agent consumed what.
- Redis holds ciphertext. `primaryEncryptionKey` / `secondaryEncryptionKey` in
  `components/statestore.yaml` come from the secret store; rotation is a
  matter of swapping the two.
- With an encrypted backend Flock disables state transactions (a Dapr runtime
  limitation, see the [Dapr guide](../../../docs/guides/dapr-state-store.md#known-limitations))
  and reconciles its indexes lazily on read.

## Demo 2 — One blackboard, many Flocks

Keep the writer from demo 1 running.

**Terminal 3 — the reader**

```bash
uv run python examples/12-dapr/demos/reader.py          # dashboard + REST on http://localhost:8345
```

**Terminal 2 — the driver**

```bash
# 1. the reader already sees everything the writer produced
curl -s localhost:8345/api/v1/artifacts | jq -r '.items[] | "\(.type)\t\(.produced_by)"'

# 2. write on A, read on B
curl -s -X POST localhost:8344/api/v1/artifacts -H 'content-type: application/json' \
  -d @examples/12-dapr/demos/payloads/band_concept_2.json | jq .id
sleep 30
curl -s 'localhost:8345/api/v1/artifacts?type=MarketingCopy' | jq '.items | length'

# 3. write on B, read on A — the reader's own agent, critic, turns MarketingCopy into a Review
curl -s -X POST localhost:8345/api/v1/artifacts -H 'content-type: application/json' \
  -d @examples/12-dapr/demos/payloads/marketing_copy.json | jq .id
sleep 10
curl -s 'localhost:8344/api/v1/artifacts?type=Review' | jq '.items[0].payload'

# 4. the boundary: exactly one Review, not two
curl -s 'localhost:8344/api/v1/artifacts?type=Review' | jq '.items | length'
```

What to notice:

- **Shared state works today.** Two processes, one `store_name`, one Redis:
  the reader lists, filters and displays the writer's artifacts and vice versa.
  Visibility rules travel with each artifact.
- **Shared triggers do not exist yet.** The critic in the reader reacted to the
  `MarketingCopy` you published *to the reader*. It did not wake up for the
  `MarketingCopy` the writer's own agent produced in step 2. Cross-instance
  notification is planned as an opt-in Dapr Pub/Sub bridge; the state store
  stays the source of truth.
- Both instances talk to one sidecar here for simplicity. On Kubernetes each
  pod gets its own sidecar pointing at the same component.
- Concurrent writes from two instances race on the shared indexes; ETags give
  first-write-wins today, automatic retry is tracked in
  [#415](https://github.com/whiteducksoftware/flock/issues/415). The steps above
  publish sequentially on purpose.

If the LLM is unavailable, `payloads/review_fallback.json` lets you publish a
`Review` directly to `:8345` and still show it on `:8344`.

## Swap the backend (optional)

The same two scripts run against the PostgreSQL stack — edit `make_store()` in
`_common.py` to `encrypted_backend=False, supports_transactions=True` and start
[`../postgresql_unencrypted/`](../postgresql_unencrypted/) instead of Redis.
Only one stack at a time: they share host ports.

## Gotchas

- Artifact types are registered with explicit names (`@flock_type(name="BandConcept")`)
  so the dashboard and the REST API show `BandConcept` rather than
  `_common.BandConcept`. Either form works in a REST publish: simple names are
  resolved to the registered name, unknown names are rejected with 400.
- Only one example stack at a time: they share the host ports 50001, 3500 and 6379.

## Reset

```bash
docker exec redis redis-cli -a 'flock-redis-dev-2026!' --no-auth-warning FLUSHALL   # empty blackboard
# or
cd examples/12-dapr/redis_encrypted && docker compose down -v
```
