# My Amazing Steering Implementation

## Goals
- Provide a first-class way for orchestrator authors to broadcast steering guidance that every agent can inspect without risking accidental cascades.
- Preserve existing blackboard semantics (artifacts, visibility, tags, history) so announcements are auditable and dashboard-friendly.
- Offer per-agent opt-out so builders can keep certain agents deterministic or sandboxed from steering.

## Non-Goals
- Replacing per-agent prompt/engine configuration.
- Introducing a new persistence backend or storage schema migration.
- Delivering tenant-scoped policy enforcement (we reuse current visibility controls).

## Surface Area Changes
1. `Flock.post_announcement(...)` helper on the orchestrator and `BoardHandle.post_announcement(...)` for utilities/components.
2. New Pydantic model `SystemAnnouncement` registered via `flock_type`.
3. Constant tag `ANNOUNCEMENT_TAG = "__announcement__"` for filter logic.
4. Agent builder toggle `.ignore_announcements()` backed by `Agent.ignore_announcements: bool`.
5. Context plumbing update so engine components automatically receive announcements unless the agent opted out.

## Data Model
```python
@flock_type(name="flock.SystemAnnouncement")
class SystemAnnouncement(BaseModel):
    message: str
    level: Literal["info", "warning", "critical"] = "info"
    topics: set[str] = Field(default_factory=set)
    expires_at: datetime | None = None
```

- We keep the schema in a new `src/flock/system_artifacts.py` so it stays decoupled from core `Artifact` definitions.
- `expires_at` lets us prune stale announcements at read time without mutating history.
- Additional metadata lives in `Artifact.tags` and `Artifact.visibility`.

## Orchestrator API
```python
class Flock:
    async def post_announcement(
        self,
        ann: SystemAnnouncement | str,
        *,
        level: str | None = None,
        topics: set[str] | None = None,
        visibility: Visibility | None = None,
        correlation_id: str | None = None,
        partition_key: str | None = None,
        tags: set[str] | None = None,
    ) -> Artifact:
        ...
```

- Accept either a `SystemAnnouncement` instance or raw string (auto-wrap).
- Enforce tag decoration: `tags = (tags or set()) | {ANNOUNCEMENT_TAG}`.
- Convert simple strings into the default schema using provided overrides.
- Rework the existing `_persist_and_schedule` helper into `_persist(artifact, *, schedule=True)` so we can persist without scheduling:
  - `await self._persist(artifact, schedule=False)` for announcements.
  - Maintain metrics: increment `artifacts_published` and a new counter `announcements_posted`.
- Skip `_schedule_artifact` entirely; nothing consumes announcements automatically.
- Set `self.metrics["announcements_posted"] += 1` so dashboards can expose global state.

### Board Handle
Extend `BoardHandle` with:
```python
class BoardHandle:
    async def post_announcement(self, *args, **kwargs) -> Artifact:
        return await self._orchestrator.post_announcement(*args, **kwargs)
```
Agents and utilities already receive a board handle inside `Context`, so they can emit steering updates without direct orchestrator access (still respecting visibility rules).

## Scheduler Guardrail
Inside `_schedule_artifact` add:
```python
if ANNOUNCEMENT_TAG in artifact.tags:
    continue
```
This makes the skip explicit even if announcements are inserted through lower-level APIs.

## Agent Opt-Out
- `Agent.ignore_announcements: bool = False` on `Agent`.
- `AgentBuilder.ignore_announcements(enabled: bool = True) -> AgentBuilder` to toggle the flag fluently.
- No runtime penalty: the check happens during context assembly.

## Context Integration
Update `EngineComponent.fetch_conversation_context` to merge announcements:
1. Fetch conversation-scoped artifacts as today.
2. Pull announcements once (cacheable per request):
   ```python
   if not getattr(agent, "ignore_announcements", False):
       global_announcements = [
           a for a in await ctx.board.list()
           if ANNOUNCEMENT_TAG in a.tags and self._announcement_is_active(a)
           and orchestrator._check_visibility(a, agent.identity)
       ]
   ```
3. `_announcement_is_active` validates `expires_at` and optional `topics`.
4. Append sanitized announcement payloads ahead of the conversation history so LLMs treat them like system messages.
- Engines that already set `context_exclude_types` automatically skip announcements by type if necessary; we include `"flock.SystemAnnouncement"` by default when `ignore_announcements()` is set.

## Persistence & Observability
- No schema changes: announcements store like any artifact, so SQLite and dashboards pick them up immediately.
- Update `Store.query_artifacts` helpers to allow filtering by `ANNOUNCEMENT_TAG`.
- Add dashboard badge: when announcements exist, surface them in the historical view and live console.

## Rollout Plan
1. **Foundations**
   - Implement schema + constant + orchestrator changes.
   - Add metrics counter and ensure dashboards read it.
2. **Context Plumbing**
   - Update `EngineComponent.fetch_conversation_context` and unit tests.
   - Provide sample usage in `examples/02-the-blackboard`.
3. **Documentation**
   - Update `docs/guides/patterns.md` with new steering pattern.
   - Cross-link from `AGENTS.md` under critical patterns.
4. **QA**
   - Unit tests: orchestrator scheduling skip, builder opt-out, context fetch.
   - Integration test: run declarative pizza example with announcements switched on and ensure no extra agent runs fire.
   - Dashboard smoke test: verify announcement banner appears.
5. **Release**
   - Bump backend version (`pyproject.toml`) per existing policy.
   - Announce in release notes.

## Testing Matrix
- `tests/test_orchestrator.py` (new): ensure `_schedule_artifact` ignores tagged artifacts.
- `tests/test_components.py`: extend context tests to validate announcements injection/skip.
- `tests/test_store_sqlite.py`: assert announcements survive roundtrip with tags/visibility intact.
- `tests/examples/test_announcements.py`: scenario-level regression.

## Open Questions
- Do we need per-topic agent opt-out (e.g., ignore only `"cost_controls"` topics)?
- Should announcements emit structured artifacts per engine (e.g., DSPy prompt suffix) instead of raw payloads?
- How aggressively should we prune expired announcements from hot storage (background task vs lazy read)?

## API Usage Examples

### Bootstrap a Release Banner
```python
from datetime import datetime, timedelta

from flock.orchestrator import Flock
from flock.system_artifacts import SystemAnnouncement

flock = Flock("openai/gpt-4.1")

# Call during startup or migration scripts
await flock.post_announcement(
    SystemAnnouncement(
        message="Runtime is in read-only maintenance until 14:00 UTC.",
        level="warning",
        topics={"maintenance", "runtime"},
        expires_at=datetime.utcnow() + timedelta(hours=4),
    ),
    visibility=PublicVisibility(),  # optional override
)
```

### Agent-Specific Steering Burst
```python
@flock_type
class SafetyEscalation(BaseModel):
    incident_id: str
    severity: str

safety_agent = (
    flock.agent("safety_triage")
    .consumes(SafetyEscalation)
    .publishes(IncidentAssignment)
)

await flock.post_announcement(
    "All severity=critical escalations must page the on-call lead.",
    level="critical",
    topics={"safety", "paging"},
)
```

### Lifecycle Components Broadcasting Feedback
```python
class BudgetWatcher(AgentComponent):
    async def on_post_publish(self, agent, ctx, outputs):
        budget = ctx.state.get("budget_remaining")
        if budget is not None and budget < 20:
            await ctx.board.post_announcement(
                f"Budget under 20% for tenant {agent.tenant_id}; throttle heavy agents.",
                level="warning",
                topics={"budget", agent.tenant_id or "global"},
            )
```

### Opting Out a Deterministic Agent
```python
stdlib_agent = (
    flock.agent("audit_logger")
    .consumes(ExecutionLog)
    .publishes(AuditSummary)
    .ignore_announcements()  # stays deterministic regardless of global steering
)
```

### Filtering Announcements Manually
```python
announcements = [
    artifact
    for artifact in await flock.store.list_by_type("flock.SystemAnnouncement")
    if "__announcement__" in artifact.tags
]
for ann in announcements:
    print(ann.payload["message"])
```

## Dashboard / UI Integration

The React dashboard (`src/flock/frontend/src/App.tsx`) already bootstraps historical artifacts (`fetchArtifacts`) and listens to WebSocket updates via `initializeWebSocket`. Announcements piggyback on the same primitives:

- **Data Fetching**
  Extend `fetchArtifactSummary` / `fetchArtifacts` to accept `tags={"__announcement__"}`. During the initial load in `App.tsx`, store the result in a new slice (e.g., `useUIStore` or `useFilterStore`) dedicated to active announcements. Because announcements persist in the blackboard, IndexedDB persistence continues to work without extra plumbing.

- **Live Updates**
  When the WebSocket pushes an `ArtifactPublished` event, `mapArtifactToMessage` already normalizes payloads. Detect the announcement tag and dispatch a lightweight action (`uiStore.setAnnouncements([...])`). This matches how existing events populate the graph.

- **Presentation Layer**
  `DashboardLayout.tsx` renders the top header, control buttons, and filter pills. We can introduce an `AnnouncementBanner` component directly under `<header className="dashboard-header">`, borrowing design tokens from `DESIGN_SYSTEM.md` (callout background, iconography). Key states:
  - collapsed banner when no announcements.
  - stacked cards for multiple announcements with level-specific colors (`info`, `warning`, `critical`).
  - quick actions: “Dismiss for session”, “View history” (deep-link to artifacts table).

  For denser contexts (e.g., blackboard graph), add a subtle indicator next to the `View` toggle or in `FilterPills` so users see that steering is active even when the banner is dismissed.

- **Detail Windows & Modules**
  Each `DetailWindowContainer` entry already receives agent metadata. Add an icon or tooltip inside the agent detail panel showing which announcements apply (filtered by topics + visibility). This reuse of `useGraphStore` keeps agent-centric workflows aware of steering constraints without re-querying the backend.

- **Settings & Controls**
  In `SettingsPanel`, expose a toggle to show/hide the banner, plus a diagnostic table that lists announcements with their expiration and visibility. Operators can confirm that a post succeeded without hitting the REST API manually.

- **Testing**
  Frontend unit tests in `src/flock/frontend/src/__tests__` gain a suite that mocks the REST/WebSocket interfaces and asserts the banner renders level-specific styles, handles dismissals, and respects agent opt-out states when showing per-agent badges.

This UI plan stays consistent with existing layout primitives and avoids new network contracts beyond tagging announcements, while giving operators immediate visual feedback when steering is active.
