---
title: "feat/skills vs main: Subagent Code Review"
date: 2026-05-07
branch: feat/skills
base: a4a24b79c396228c96cd1b69a03b0d0c08f3b83c
head: 130efd182aa5e1c3cf1d42dd5ce74b08dd787c56
reviewer: Codie with Compound Engineering subagents
status: not-ready
---

# feat/skills vs main: Subagent Code Review

## Verdict

**Not ready to merge.**

This branch is doing real work, but the current diff reopens several sharp surfaces at once: token auth, artifact/changelog HTTP APIs, external agent process execution, persistent SQLite state, and dashboard observability. The highest-risk issue is that token scopes and visibility are modeled but not consistently enforced on the served routes. The changelog stream then compounds that by storing full artifact payloads in `payload_summary` and replaying them through unscoped stream/cursor endpoints.

Fix order:

1. Centralize artifact/changelog auth, scopes, allowed types, and visibility filtering.
2. Remove full payloads from changelog summaries or make changelog delivery as protected as artifact reads.
3. Fix external-engine initialization, timeouts, and cancellation cleanup.
4. Make SQLite external session and publish transactions cancellation/concurrency safe.
5. Repair retention, SSE replay, dashboard lifecycle, docs, tests, and versioning.

## Scope

- Diff: `feat/skills` against `origin/main`, merge-base `a4a24b79c396228c96cd1b69a03b0d0c08f3b83c`.
- Head reviewed: `130efd182aa5e1c3cf1d42dd5ce74b08dd787c56`.
- Size: 81 files changed, 17,083 insertions, 80 deletions.
- PR: none found for branch `feat/skills`, so this was a standalone branch review.
- Mode: report-only by user intent. No fixes were applied beyond this review artifact.

## Reviewer Coverage

| Reviewer | Focus |
|---|---|
| `ce-correctness-reviewer` | logic, state, output contracts, edge cases |
| `ce-security-reviewer` | auth, scopes, data exposure, subprocess risk |
| `ce-adversarial-reviewer` | failure scenarios across large diff and auth/runtime surfaces |
| `ce-testing-reviewer` | missing negative and integration tests |
| `ce-maintainability-reviewer` | coupling, duplicate paths, dead contracts |
| `ce-project-standards-reviewer` | AGENTS/version/logging standards |
| `ce-api-contract-reviewer` | HTTP/SSE/WS contract parity |
| `ce-reliability-reviewer` | cancellation, timeouts, background loops, transactions |
| `ce-performance-reviewer` | stream replay, indexes, payload size, runtime memory |
| `ce-kieran-python-reviewer` | Python correctness and type/flow clarity |
| `ce-agent-native-reviewer` | agent-operable API/dashboard/runtime parity |
| `ce-learnings-researcher` | prior review lessons from `docs/reviews/` |

## Findings

### P0 - Critical

| ID | Finding | Evidence | Suggested fix |
|---|---|---|---|
| F-01 | **Artifact API auth is decorative on the actual served routes.** Token scopes and `allowed_types` are defined and stored, but the served artifact routes do not enforce them consistently. `BlackboardHTTPService` publish/sync only check `allowed_types`, not `artifact:publish`; its reads do not accept `Request` and do not check `artifact:read` or `allowed_types`. The default served API is `ArtifactsComponent`, which does not read request auth state at all. | `src/flock/api/service.py:164`, `src/flock/api/service.py:238`, `src/flock/api/service.py:336`, `src/flock/api/service.py:402`, `src/flock/components/server/artifacts/artifacts_component.py:118`, `src/flock/components/server/artifacts/artifacts_component.py:132`, `src/flock/components/server/artifacts/artifacts_component.py:204`, `src/flock/orchestrator/server_manager.py:277`, `src/flock/components/server/auth/auth_component.py:64` | Create shared route guards for `artifact:publish`, `artifact:read`, `token_allowed_types`, and visibility. Use them in both `BlackboardHTTPService` and `ArtifactsComponent`, plus agent/history/summary routes. Add negative tests for read-only tokens publishing, publish-only tokens reading, and type-scoped reads/writes on both route stacks. |
| F-02 | **Changelog streams persist and replay full private payloads without visibility filtering.** The docs describe `payload_summary` as lightweight and visibility-aware, but `_build_changelog_event()` embeds `artifact.payload`, and SSE/cursor replay returns the serialized event without auth/visibility filtering. WebSocket auth is optional and not connected to the global HTTP auth middleware. Auto-registration creates a `ChangelogStreamComponent()` without a token store, so external-agent apps can get an open `/ws/changelog` by default. | `src/flock/orchestrator/artifact_manager.py:224`, `src/flock/orchestrator/artifact_manager.py:234`, `src/flock/components/server/changelog/changelog_component.py:110`, `src/flock/components/server/changelog/changelog_component.py:138`, `src/flock/components/server/changelog/changelog_component.py:181`, `src/flock/components/server/changelog/changelog_component.py:245`, `src/flock/core/orchestrator.py:996`, `src/flock/core/orchestrator.py:1012`, `src/flock/components/server/auth/auth_component.py:271`, `docs/guides/changelog-stream.md:112`, `docs/guides/changelog-stream.md:113` | Keep changelog events metadata-only or bounded-summary-only. Apply the same identity, scope, `allowed_types`, and `Visibility` checks as artifact reads to cursor, SSE, and WS replay/live delivery. Do not auto-register an unauthenticated changelog stream when auth is configured. Add private/tenant artifact leak tests. |

### P1 - High

| ID | Finding | Evidence | Suggested fix |
|---|---|---|---|
| F-03 | **External agents can be scheduled before their `ExternalEngineComponent` is auto-attached.** Normal `publish()` delegates directly to `ArtifactManager`; `schedule_artifact()` initializes only `ComponentRunner`. The external auto-wiring lives in `Flock._run_initialize()`, which `run_until_idle()` calls later. A publish can schedule and start an external agent task before the engine is attached. | `src/flock/core/orchestrator.py:1045`, `src/flock/orchestrator/scheduler.py:51`, `src/flock/core/orchestrator.py:648`, `src/flock/core/orchestrator.py:1194`, `src/flock/core/orchestrator.py:1261` | Route first-use initialization through a single idempotent orchestrator initializer before any scheduling or direct invoke, or move external auto-wiring into the same initialization path the scheduler uses. Add a test that `await flock.publish(input)` schedules an external agent without a manual `_run_initialize()`. |
| F-04 | **External agent `spawn_timeout` is configured but never enforced, and cancellation can leave subprocesses alive.** `SpawnConfig.timeout` is populated, but `adapter.monitor()` is awaited directly. The base adapter reads stdout/stderr until EOF and waits for process exit with no timeout. The engine catches `Exception`, so `asyncio.CancelledError` bypasses `terminate()`. | `src/flock/integrations/external/engine.py:213`, `src/flock/integrations/external/engine.py:219`, `src/flock/integrations/external/engine.py:224`, `src/flock/integrations/external/engine.py:225`, `src/flock/integrations/external/adapters/base.py:97`, `src/flock/integrations/external/adapters/base.py:101` | Wrap spawn/monitor in an actual timeout budget. On `TimeoutError` or cancellation, call `adapter.terminate()` under a bounded shield, then raise `ExternalEngineExecutionError` for timeouts or re-raise cancellation. Add a hanging-monitor test. |
| F-05 | **SQLite external session writes reuse the blackboard connection and commit outside the store write lock.** Artifact/changelog publish uses an explicit transaction under `_write_lock`, while `LazySQLiteExternalSessionStore` grabs the same connection and `SQLiteExternalSessionStore.set()` commits independently. That can interfere with another task's active transaction on the shared connection. | `src/flock/core/store.py:528`, `src/flock/core/store.py:530`, `src/flock/core/store.py:601`, `src/flock/integrations/external/models.py:177`, `src/flock/integrations/external/models.py:183`, `src/flock/integrations/external/models.py:221`, `src/flock/integrations/external/models.py:223` | Route session operations through `SQLiteBlackboardStore` methods that share `_write_lock`, or give the session store its own connection/transaction boundary. Avoid independent `commit()` calls on the shared store connection. Add concurrent publish/session-write tests. |
| F-06 | **Cancelled SQLite publishes can leave the shared connection inside an open transaction.** `publish()` starts `BEGIN` and rolls back only under `except Exception`; on Python 3.12, `asyncio.CancelledError` is not caught by `Exception`. A cancellation between `BEGIN` and `COMMIT` can poison the connection for later writes. | `src/flock/core/store.py:530`, `src/flock/core/store.py:601`, `src/flock/core/store.py:602` | Catch `asyncio.CancelledError` or use a transaction helper that rolls back under `BaseException` with `contextlib.suppress`, then re-raises cancellation. Add cancellation tests around `SQLiteBlackboardStore.publish()`. |
| F-07 | **Cascade depth tracking counts artifact width, not causal depth, and never resets.** The new `_cascade_depths` counter increments for every artifact with the same correlation ID. A legitimate fan-out or broad workflow with more than 10 sibling artifacts is persisted but no longer scheduled, even if there is no loop. | `src/flock/orchestrator/artifact_manager.py:48`, `src/flock/orchestrator/artifact_manager.py:183`, `src/flock/orchestrator/artifact_manager.py:186`, `src/flock/orchestrator/artifact_manager.py:198` | Replace the width counter with true causal depth/iteration tracking, reset it on idle, or remove this limiter and rely on explicit loop detection. Add a fan-out workflow test with more than 10 artifacts sharing one correlation ID. |
| F-08 | **External output prompting and parsing disagree for multiple output groups and fan-out.** `evaluate()` parses only the current `output_group.outputs`, but `_compose_prompt()` asks the external agent for schemas from every `agent.output_group`. `_parse_outputs()` then requires exactly one output per type, ignoring `count`/`FanOutRange` semantics enforced elsewhere. | `src/flock/integrations/external/engine.py:141`, `src/flock/integrations/external/engine.py:157`, `src/flock/integrations/external/engine.py:323`, `src/flock/integrations/external/engine.py:324`, `src/flock/integrations/external/engine.py:327` | Build one expected-output spec from the current `OutputGroup`, including fan-out/count constraints, and use it for both prompt generation and parsing. Add tests for multiple `.publishes()` groups and dynamic fan-out external outputs. |
| F-09 | **External lifecycle dashboard events are defined but not emitted by the runtime.** The event emitter has external spawned/completed/failed methods, and event models include external lifecycle types, but `ExternalEngineComponent` never calls those methods around `spawn()`/`monitor()`. Separately, generic dashboard events and snapshots default `agent_kind` to `internal` and the collector does not pass the external kind through. | `src/flock/orchestrator/event_emitter.py:178`, `src/flock/orchestrator/event_emitter.py:207`, `src/flock/orchestrator/event_emitter.py:233`, `src/flock/integrations/external/engine.py:222`, `src/flock/integrations/external/engine.py:224`, `src/flock/api/collector.py:207`, `src/flock/api/collector.py:312`, `src/flock/api/collector.py:538`, `src/flock/components/server/models/events.py:50`, `src/flock/components/server/models/events.py:151` | Emit external lifecycle events inside `ExternalEngineComponent`, and persist/broadcast `agent_kind` through collector events and snapshots. Add an integration test through a real external-engine invocation, not only direct event-emitter unit tests. |
| F-10 | **Backend package version was not bumped despite backend behavior changes.** The branch changes 48 backend/test files under Flock runtime surfaces and adds dependencies, but `pyproject.toml` remains `0.5.402`, the same as `origin/main`. Project instructions require a backend version bump for Python behavior changes. | `pyproject.toml:3`, `AGENTS.md:730`, `AGENTS.md:760` | Bump the backend version before publishing or opening a PR. Docs-only changes do not need a bump, but this is not docs-only. |

### P2 - Moderate

| ID | Finding | Evidence | Suggested fix |
|---|---|---|---|
| F-11 | **SSE reconnect replay can silently drop persisted events.** Reconnect replay queries only one `limit=1000` page and then subscribes to live events. If the client is more than 1000 events behind, events after that first page are skipped. There is also a publish-between-query-and-subscribe race. | `src/flock/components/server/changelog/changelog_component.py:245`, `src/flock/components/server/changelog/changelog_component.py:259`, `src/flock/components/server/changelog/changelog_component.py:269` | Subscribe first, then page replay until caught up to `latest_seq`, deduping by `seq`; or emit an explicit resync/gap event when replay cannot cover the backlog. |
| F-12 | **Count retention over-prunes when changelog sequence numbers have gaps.** Age pruning or transactional gaps can make `latest_seq - oldest_seq + 1` larger than the actual row count. The current count policy then deletes based on sequence span rather than actual retained events. | `src/flock/components/orchestrator/retention.py:101`, `src/flock/components/orchestrator/retention.py:121`, `src/flock/components/orchestrator/retention.py:126`, `docs/guides/changelog-stream.md:101` | Implement a store-level `prune_changelog_keep_latest(max_count)` that deletes rows older than the Nth newest actual row. Add non-contiguous sequence tests. |
| F-13 | **Retention background task dies permanently on one prune failure.** `_pruning_loop()` catches only cancellation. Any transient store error from `_run_prune()` exits the task and disables future retention silently. | `src/flock/components/orchestrator/retention.py:57`, `src/flock/components/orchestrator/retention.py:82`, `src/flock/components/orchestrator/retention.py:87`, `src/flock/components/orchestrator/retention.py:88` | Catch and log per-iteration exceptions, continue with bounded backoff, and attach a done callback or health signal so unexpected task death is visible. |
| F-14 | **Age-based changelog retention lacks a timestamp index.** `prune_changelog(before_time=...)` deletes by timestamp, but schema indexes cover event type, artifact type, producer, and correlation only. Large retained logs will scan during each age prune. | `src/flock/core/store.py:1089`, `src/flock/storage/sqlite/schema_manager.py:189`, `src/flock/storage/sqlite/schema_manager.py:192`, `src/flock/storage/sqlite/schema_manager.py:198`, `src/flock/storage/sqlite/schema_manager.py:204`, `src/flock/storage/sqlite/schema_manager.py:210` | Add a timestamp-oriented index, for example `(timestamp, seq)`, and keep batch pruning aligned to that index. |
| F-15 | **Documented changelog event coverage is broader than runtime emission.** The guide describes publish, consumption, and agent snapshot changelog events, but this diff only appends artifact-published events. Consumption recording and snapshot upserts do not append changelog events. | `docs/guides/changelog-stream.md:15`, `src/flock/orchestrator/artifact_manager.py:224`, `src/flock/core/store.py:606`, `src/flock/core/store.py:905` | Either emit `artifact_consumed` and `agent_snapshot_updated` events or narrow the docs and event model until those paths exist. |
| F-16 | **Token-auth docs show setup code that cannot run as written.** The guide instantiates `AuthenticationComponent()` and `TokenManagementComponent()` without a shared token store or registered bearer handler, but `TokenManagementComponent` raises if no store is passed. | `docs/guides/meta-orchestrator.md:148`, `docs/guides/meta-orchestrator.md:151`, `docs/guides/meta-orchestrator.md:152`, `src/flock/components/server/auth/token_management_component.py:131` | Document complete wiring: shared `TokenStore`, `make_bearer_token_handler`, `AuthenticationComponentConfig(default_handler=...)`, and an explicit bootstrap/admin-token path. |
| F-17 | **New auth modules bypass the Flock logger helper.** Project standards say new logging should use `flock.logging.logging.get_logger`, but `token_store.py` imports stdlib `logging` directly and the auth middleware prints handler exceptions. | `src/flock/auth/token_store.py:6`, `src/flock/auth/token_store.py:14`, `src/flock/auth/token_store.py:18`, `src/flock/components/server/auth/auth_component.py:328`, `AGENTS.md:842`, `AGENTS.md:855` | Use `get_logger(__name__)` and a named Flock-compatible audit logger or documented helper. Replace `print()` with structured logger calls. |

## Testing Gaps

The focused test command printed `117 passed in 2.20s`:

```bash
uv run pytest tests/api/test_token_api.py tests/test_token_auth.py tests/test_external_engine.py tests/test_changelog_store.py tests/api/test_changelog_api.py -q
```

The pytest process remained alive after printing the pass summary, so I terminated the dangling process. I treated the printed test result as a focused pass, but the hang itself is worth watching if it repeats.

Missing coverage that should be added before merge:

- Negative route tests for `artifact:publish`, `artifact:read`, `token:manage`, and `allowed_types` across both `/api/v1/artifacts` implementations.
- Changelog visibility tests for private, tenant, label, and type-scoped artifacts across cursor, SSE replay, and WebSocket live streams.
- External engine tests for normal `publish()` initialization, enforced `spawn_timeout`, cancellation cleanup, multiple output groups, and fan-out.
- SQLite concurrency/cancellation tests for artifact/changelog publish and external session writes.
- Retention tests with non-contiguous sequences and a failing prune iteration.
- SSE replay tests with more than 1000 missed events and with a publish occurring between replay query and live subscribe.
- Dashboard integration tests proving external lifecycle events are emitted from the real external engine path.

## Prior Lessons Applied

The learnings pass found no `docs/solutions/` directory in this repo, so it scanned `docs/reviews/` and adjacent pattern docs instead. The relevant prior lessons were:

- Auth was previously reviewed as an all-boundaries concern; scopes that are only modeled are not enough.
- External agents should remain on the normal engine path, not a separate scheduler/runtime path.
- Changelog history has already had retention and visibility sharp edges; docs/API parity matters here.
- Dashboard/WebSocket hot paths need nonblocking delivery and explicit loss/gap semantics.
- Version bumps are part of publish readiness for backend behavior changes.

## Demoted Or Suppressed Items

- External adapter permission-bypass CLI flags were treated as a residual deployment risk, not a primary blocker, because the plan and examples appear to intentionally allow local operator-controlled CLI agents.
- Some style-only findings were omitted from the main table unless they touched project rules, release flow, or production diagnostics.
- `docs/solutions/` learnings could not be searched because the directory does not exist in this repo.

## Closeout

This review should block merge until at least F-01 through F-10 are resolved or explicitly accepted. The strongest path is to first make auth/visibility a shared helper layer, then reuse it everywhere: artifact REST, component REST, changelog cursor, SSE, WebSocket, dashboard history, and tests.
