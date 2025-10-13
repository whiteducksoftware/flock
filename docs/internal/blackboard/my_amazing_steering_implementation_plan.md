# System Announcements Implementation Plan

**Status:** Ready for Implementation
**Assignee:** TBD
**Estimated Time:** 3-4 days
**Priority:** Medium
**Dependencies:** None (builds on existing infrastructure)

---

## 📋 Overview

This plan implements the **System Announcements** feature as specified in [`my_amazing_steering_implementation.md`](./my_amazing_steering_implementation.md).

**Goal:** Allow orchestrator authors to broadcast steering guidance that every agent can inspect without triggering agent cascades.

**Key Principle:** Announcements are artifacts (stored on blackboard) but NOT consumable (won't trigger agent subscriptions).

---

## 📚 Required Background Reading

Before starting, read these files to understand the architecture:

1. **[AGENTS.md](../../AGENTS.md)** - Core patterns, especially:
   - Blackboard architecture (lines 26-45)
   - Agent lifecycle (lines 127-147)
   - Test isolation patterns (lines 266-305)

2. **[src/flock/orchestrator.py](../../src/flock/orchestrator.py)** - Understand:
   - `publish()` method (lines 614-702)
   - `_persist_and_schedule()` (line 839)
   - `_schedule_artifact()` (lines 844-867)

3. **[src/flock/agent.py](../../src/flock/agent.py)** - Understand:
   - `AgentBuilder` fluent API (lines 403-977)
   - Agent properties like `prevent_self_trigger` (line 109)

4. **[src/flock/components.py](../../src/flock/components.py)** - Understand:
   - `EngineComponent.fetch_conversation_context()` (lines 112-161)

5. **[src/flock/engines/dspy_engine.py](../../src/flock/engines/dspy_engine.py)** - Understand:
   - How context is integrated (lines 176-186)

---

## 🎯 Success Criteria

**Feature is complete when:**
- ✅ `flock.post_announcement()` publishes non-consumable artifacts
- ✅ Scheduler ignores announcement artifacts
- ✅ Agents see announcements in context by default
- ✅ Agents can opt-out with `.ignore_announcements()`
- ✅ Announcements respect visibility controls
- ✅ Expired announcements are filtered automatically
- ✅ All tests pass (existing + new)
- ✅ Documentation is updated
- ✅ Example code demonstrates the feature

---

## 🚀 Implementation Phases

### Phase 1: Foundations (Data Model + Constants)
### Phase 2: Orchestrator API (Publishing)
### Phase 3: Scheduler Guardrail (Prevent Consumption)
### Phase 4: Agent Opt-Out (Builder API)
### Phase 5: Context Integration (Engine Changes)
### Phase 6: Testing (Unit + Integration)
### Phase 7: Documentation + Examples

---

# Phase 1: Foundations (Data Model + Constants)

**Goal:** Create the announcement data structure and tag constant.

---

## Task 1.1: Create System Artifacts Module

**File:** Create new file `src/flock/system_artifacts.py`

**What to do:**
```python
"""System-level artifact types for orchestration control."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SystemAnnouncement(BaseModel):
    """System-level announcement visible to all agents.

    Announcements are broadcast messages that appear in agent context
    but do not trigger agent subscriptions. Use for:
    - Global policy updates
    - System-wide guidelines
    - Runtime steering

    Examples:
        >>> # Simple announcement
        >>> ann = SystemAnnouncement(message="Always validate user input")

        >>> # Warning with expiration
        >>> ann = SystemAnnouncement(
        ...     message="Cost controls active",
        ...     level="warning",
        ...     expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        ... )

        >>> # Topic-tagged announcement
        >>> ann = SystemAnnouncement(
        ...     message="Use defensive SQL practices",
        ...     topics={"security", "database"}
        ... )
    """

    message: str = Field(..., description="The announcement text")
    level: Literal["info", "warning", "critical"] = Field(
        default="info",
        description="Severity level for dashboard filtering"
    )
    topics: set[str] = Field(
        default_factory=set,
        description="Topic tags for categorization (e.g., 'security', 'performance')"
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional expiration timestamp (UTC). Expired announcements are filtered automatically."
    )


__all__ = [
    "SystemAnnouncement",
]
```

**Why we're doing this:**
- Creates dedicated module for system-level types (keeps core `artifacts.py` clean)
- Provides structured schema (not just strings)
- Enables future expansion (more system types)

**Test it:**
```bash
# Interactive test
uv run python -c "
from flock.system_artifacts import SystemAnnouncement
from datetime import datetime, timezone, timedelta

# Test basic creation
ann = SystemAnnouncement(message='Test')
print(f'✅ Basic: {ann.message}')

# Test with all fields
ann2 = SystemAnnouncement(
    message='Complex test',
    level='warning',
    topics={'security'},
    expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
)
print(f'✅ Complex: {ann2.level} - {ann2.topics}')
"
```

**Acceptance Criteria:**
- [ ] File `src/flock/system_artifacts.py` exists
- [ ] `SystemAnnouncement` class validates with Pydantic
- [ ] All fields have correct types and defaults
- [ ] Docstring explains usage with examples
- [ ] Interactive test runs without errors

---

## Task 1.2: Register Type with Flock

**File:** Modify `src/flock/system_artifacts.py`

**What to do:** Add type registration at the bottom of the file:

```python
# At the end of src/flock/system_artifacts.py, before __all__:

from flock.registry import flock_type

# Register the type with a stable name
SystemAnnouncement = flock_type(name="flock.SystemAnnouncement")(SystemAnnouncement)
```

**Why we're doing this:**
- Makes `SystemAnnouncement` discoverable by the type registry
- Uses stable namespace (`flock.*` prefix)
- Follows pattern from examples (see `examples/01-the-declarative-way/01_declarative_pizza.py:39`)

**Test it:**
```bash
uv run python -c "
from flock.system_artifacts import SystemAnnouncement
from flock.registry import type_registry

# Verify registration
registered_name = type_registry.name_for(SystemAnnouncement)
print(f'✅ Registered as: {registered_name}')
assert registered_name == 'flock.SystemAnnouncement', 'Wrong name!'
"
```

**Acceptance Criteria:**
- [ ] Type is registered in `type_registry`
- [ ] Registered name is `"flock.SystemAnnouncement"`
- [ ] Test runs without assertion errors

---

## Task 1.3: Define Announcement Tag Constant

**File:** Modify `src/flock/system_artifacts.py`

**What to do:** Add constant at the top after imports:

```python
# After imports in src/flock/system_artifacts.py:

# Tag constant for filtering announcements
ANNOUNCEMENT_TAG = "__announcement__"
```

**Update exports:**
```python
__all__ = [
    "SystemAnnouncement",
    "ANNOUNCEMENT_TAG",  # Add this
]
```

**Why we're doing this:**
- Centralized constant (single source of truth)
- Double underscore prefix signals "system internal"
- Prevents typos ("__anouncement__" vs "__announcement__")

**Test it:**
```bash
uv run python -c "
from flock.system_artifacts import ANNOUNCEMENT_TAG
print(f'✅ Tag: {ANNOUNCEMENT_TAG}')
assert ANNOUNCEMENT_TAG == '__announcement__'
"
```

**Acceptance Criteria:**
- [ ] `ANNOUNCEMENT_TAG` constant exists
- [ ] Value is `"__announcement__"`
- [ ] Exported in `__all__`

---

## Task 1.4: Update Main Package Exports

**File:** Modify `src/flock/__init__.py`

**What to do:** Add system artifacts to public API:

```python
# Find the imports section in src/flock/__init__.py (around line 1-30)
# Add this import:

from flock.system_artifacts import ANNOUNCEMENT_TAG, SystemAnnouncement

# Find the __all__ list (around line 40-60)
# Add these exports:

__all__ = [
    # ... existing exports ...
    "SystemAnnouncement",
    "ANNOUNCEMENT_TAG",
]
```

**Why we're doing this:**
- Makes types available via `from flock import SystemAnnouncement`
- Follows existing pattern (see how `Artifact` is exported)

**Test it:**
```bash
uv run python -c "
from flock import SystemAnnouncement, ANNOUNCEMENT_TAG
print('✅ Import from flock works')
print(f'✅ Tag: {ANNOUNCEMENT_TAG}')
"
```

**Acceptance Criteria:**
- [ ] Can import `SystemAnnouncement` from `flock`
- [ ] Can import `ANNOUNCEMENT_TAG` from `flock`
- [ ] No import errors

---

## Phase 1 Checkpoint ✅

**Verify Phase 1 is complete:**
```bash
# Run all Phase 1 tests
uv run python -c "
from flock import SystemAnnouncement, ANNOUNCEMENT_TAG
from flock.registry import type_registry
from datetime import datetime, timezone, timedelta

# Test 1: Type creation
ann = SystemAnnouncement(message='Test', level='warning')
print('✅ 1. SystemAnnouncement created')

# Test 2: Type registration
assert type_registry.name_for(SystemAnnouncement) == 'flock.SystemAnnouncement'
print('✅ 2. Type registered correctly')

# Test 3: Tag constant
assert ANNOUNCEMENT_TAG == '__announcement__'
print('✅ 3. Tag constant defined')

# Test 4: Expiration field
ann_exp = SystemAnnouncement(
    message='Expires soon',
    expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
)
print('✅ 4. Expiration field works')

print('\\n🎉 Phase 1 Complete!')
"
```

---

# Phase 2: Orchestrator API (Publishing)

**Goal:** Implement `Flock.post_announcement()` method.

---

## Task 2.1: Refactor `_persist_and_schedule` Method

**File:** `src/flock/orchestrator.py`

**Current code** (line 839-842):
```python
async def _persist_and_schedule(self, artifact: Artifact) -> None:
    await self.store.publish(artifact)
    self.metrics["artifacts_published"] += 1
    await self._schedule_artifact(artifact)
```

**What to do:** Replace with this:
```python
async def _persist_and_schedule(self, artifact: Artifact) -> None:
    """Persist artifact and schedule matching agents (default behavior)."""
    await self._persist(artifact, schedule=True)

async def _persist(self, artifact: Artifact, *, schedule: bool = True) -> None:
    """Persist artifact to store, optionally scheduling agents.

    Args:
        artifact: The artifact to persist
        schedule: If True, trigger agent subscriptions. If False, only persist.
    """
    await self.store.publish(artifact)
    self.metrics["artifacts_published"] += 1

    if schedule:
        await self._schedule_artifact(artifact)
```

**Why we're doing this:**
- Separates persistence from scheduling (announcements need persistence only)
- Maintains backward compatibility (`_persist_and_schedule` unchanged externally)
- Follows single responsibility principle

**Where to put it:** Insert `_persist()` right after `_persist_and_schedule()` (around line 843)

**Test it:**
```bash
# This should still work (existing behavior)
uv run python -c "
import asyncio
from flock import Flock
from pydantic import BaseModel

class TestInput(BaseModel):
    value: str

async def test():
    flock = Flock('openai/gpt-4.1')

    # Old method still works
    from flock.artifacts import Artifact
    from flock.visibility import PublicVisibility
    from uuid import uuid4

    artifact = Artifact(
        type='TestInput',
        payload={'value': 'test'},
        produced_by='test',
        visibility=PublicVisibility()
    )

    # Should work as before
    await flock._persist_and_schedule(artifact)
    print('✅ _persist_and_schedule still works')

    # New method should work
    await flock._persist(artifact, schedule=False)
    print('✅ _persist with schedule=False works')

asyncio.run(test())
"
```

**Acceptance Criteria:**
- [ ] `_persist()` method exists with `schedule` parameter
- [ ] `_persist_and_schedule()` calls `_persist(artifact, schedule=True)`
- [ ] Both methods work without errors
- [ ] Metrics counter still increments

---

## Task 2.2: Add Announcement Metrics Counter

**File:** `src/flock/orchestrator.py`

**Current code** (line 122):
```python
self.metrics: dict[str, float] = {"artifacts_published": 0, "agent_runs": 0}
```

**What to do:** Add announcement counter:
```python
self.metrics: dict[str, float] = {
    "artifacts_published": 0,
    "agent_runs": 0,
    "announcements_posted": 0,  # Add this
}
```

**Why we're doing this:**
- Enables observability (dashboard can show announcement count)
- Follows existing pattern (see `artifacts_published`, `agent_runs`)

**Acceptance Criteria:**
- [ ] Metrics dict includes `"announcements_posted": 0`

---

## Task 2.3: Implement `post_announcement()` Method

**File:** `src/flock/orchestrator.py`

**Where to put it:** After the `publish_many()` method (around line 728), before the "Direct Invocation API" comment (line 730)

**What to do:** Add this complete method:

```python
async def post_announcement(
    self,
    ann: SystemAnnouncement | str,
    *,
    level: Literal["info", "warning", "critical"] | None = None,
    topics: set[str] | None = None,
    visibility: Visibility | None = None,
    correlation_id: str | None = None,
    partition_key: str | None = None,
    tags: set[str] | None = None,
) -> Artifact:
    """Publish a system-level announcement visible to all agents.

    Announcements are broadcast messages that appear in agent context
    but do NOT trigger agent subscriptions. Use for global policy updates,
    system-wide guidelines, and runtime steering.

    Args:
        ann: SystemAnnouncement instance or plain string (auto-wrapped)
        level: Override announcement severity (info/warning/critical)
        topics: Topic tags for categorization
        visibility: Access control (defaults to PublicVisibility)
        correlation_id: Optional correlation ID
        partition_key: Optional partition key
        tags: Additional tags (ANNOUNCEMENT_TAG is added automatically)

    Returns:
        The published Artifact

    Examples:
        >>> # Simple string announcement
        >>> await flock.post_announcement("Always validate user input")

        >>> # Structured announcement with expiration
        >>> ann = SystemAnnouncement(
        ...     message="Cost controls active",
        ...     level="warning",
        ...     expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        ... )
        >>> await flock.post_announcement(ann)

        >>> # Private announcement for specific agents
        >>> await flock.post_announcement(
        ...     "Use defensive SQL",
        ...     level="warning",
        ...     visibility=PrivateVisibility(agents={"db_agent", "query_agent"})
        ... )

    Warning:
        Announcements are included in agent context by default. To prevent
        context overflow:
        - Keep messages concise
        - Use expires_at for time-bounded announcements
        - Let agents opt-out with .ignore_announcements()
        - Monitor via flock.metrics["announcements_posted"]
    """
    from flock.system_artifacts import ANNOUNCEMENT_TAG, SystemAnnouncement
    from flock.visibility import PublicVisibility

    # Convert string to SystemAnnouncement
    if isinstance(ann, str):
        ann = SystemAnnouncement(
            message=ann,
            level=level or "info",
            topics=topics or set(),
        )
    else:
        # Override fields if provided
        if level is not None:
            ann.level = level
        if topics is not None:
            ann.topics = topics

    # Build artifact with announcement tag
    combined_tags = (tags or set()) | {ANNOUNCEMENT_TAG}

    type_name = type_registry.name_for(SystemAnnouncement)
    artifact = Artifact(
        type=type_name,
        payload=ann.model_dump(),
        produced_by="system",
        visibility=visibility or PublicVisibility(),
        correlation_id=correlation_id,
        partition_key=partition_key,
        tags=combined_tags,
    )

    # Persist WITHOUT scheduling (announcements don't trigger agents)
    await self._persist(artifact, schedule=False)

    # Update announcement counter
    self.metrics["announcements_posted"] += 1

    return artifact
```

**Add imports at top of file** (around line 1-35):
```python
from typing import TYPE_CHECKING, Any, AsyncGenerator, Literal  # Add Literal
```

**Why we're doing this:**
- Accepts both string and model (great DX)
- Automatically adds `ANNOUNCEMENT_TAG`
- Uses `schedule=False` to prevent consumption
- Increments dedicated counter
- Comprehensive docstring with warnings

**Test it:**
```bash
uv run python -c "
import asyncio
from flock import Flock, SystemAnnouncement
from datetime import datetime, timezone, timedelta

async def test():
    flock = Flock('openai/gpt-4.1')

    # Test 1: String announcement
    artifact1 = await flock.post_announcement('Test message')
    print(f'✅ String announcement: {artifact1.id}')
    assert '__announcement__' in artifact1.tags

    # Test 2: Model announcement
    ann = SystemAnnouncement(
        message='Warning message',
        level='warning',
        topics={'security'}
    )
    artifact2 = await flock.post_announcement(ann)
    print(f'✅ Model announcement: {artifact2.id}')

    # Test 3: Metrics counter
    assert flock.metrics['announcements_posted'] == 2
    print(f'✅ Metrics: {flock.metrics[\"announcements_posted\"]}')

    # Test 4: Check it's in store
    stored = await flock.store.get(artifact1.id)
    assert stored is not None
    print('✅ Stored in blackboard')

asyncio.run(test())
"
```

**Acceptance Criteria:**
- [ ] Method accepts string and `SystemAnnouncement`
- [ ] `ANNOUNCEMENT_TAG` is always added
- [ ] Metrics counter increments
- [ ] Artifact is stored but agents not scheduled
- [ ] All tests pass

---

## Task 2.4: Add BoardHandle Method

**File:** `src/flock/orchestrator.py`

**Current code** (line 40-54 defines `BoardHandle` class)

**What to do:** Add method to `BoardHandle` class:

```python
class BoardHandle:
    """Handle exposed to components for publishing and inspection."""

    def __init__(self, orchestrator: Flock) -> None:
        self._orchestrator = orchestrator

    async def publish(self, artifact: Artifact) -> None:
        await self._orchestrator._persist_and_schedule(artifact)

    async def get(self, artifact_id) -> Artifact | None:
        return await self._orchestrator.store.get(artifact_id)

    async def list(self) -> builtins.list[Artifact]:
        return await self._orchestrator.store.list()

    # Add this method:
    async def post_announcement(
        self,
        ann: "SystemAnnouncement | str",  # Use string quote for forward ref
        **kwargs,
    ) -> Artifact:
        """Publish system announcement via board handle.

        Delegates to orchestrator.post_announcement(). See Flock.post_announcement()
        for full documentation.
        """
        return await self._orchestrator.post_announcement(ann, **kwargs)
```

**Why we're doing this:**
- Components can post announcements without orchestrator reference
- Consistent API across orchestrator and board handle
- Enables middleware use cases

**Test it:**
```bash
uv run python -c "
import asyncio
from flock import Flock
from flock.orchestrator import BoardHandle

async def test():
    flock = Flock('openai/gpt-4.1')
    board = BoardHandle(flock)

    # Test posting via board handle
    artifact = await board.post_announcement('Test via board')
    print(f'✅ BoardHandle.post_announcement works: {artifact.id}')

    assert flock.metrics['announcements_posted'] == 1
    print('✅ Metrics updated correctly')

asyncio.run(test())
"
```

**Acceptance Criteria:**
- [ ] `BoardHandle.post_announcement()` method exists
- [ ] Delegates to orchestrator correctly
- [ ] Test passes

---

## Phase 2 Checkpoint ✅

**Verify Phase 2 is complete:**
```bash
uv run python -c "
import asyncio
from flock import Flock, SystemAnnouncement
from flock.orchestrator import BoardHandle
from datetime import datetime, timezone, timedelta

async def test():
    flock = Flock('openai/gpt-4.1')

    # Test 1: String announcement
    a1 = await flock.post_announcement('String test')
    print('✅ 1. String announcement works')

    # Test 2: Model announcement
    ann = SystemAnnouncement(message='Model test', level='warning')
    a2 = await flock.post_announcement(ann)
    print('✅ 2. Model announcement works')

    # Test 3: Tags applied
    assert '__announcement__' in a1.tags
    assert '__announcement__' in a2.tags
    print('✅ 3. ANNOUNCEMENT_TAG applied')

    # Test 4: Metrics
    assert flock.metrics['announcements_posted'] == 2
    print('✅ 4. Metrics counter works')

    # Test 5: BoardHandle
    board = BoardHandle(flock)
    a3 = await board.post_announcement('Via board')
    assert flock.metrics['announcements_posted'] == 3
    print('✅ 5. BoardHandle delegation works')

    print('\\n🎉 Phase 2 Complete!')

asyncio.run(test())
"
```

---

# Phase 3: Scheduler Guardrail (Prevent Consumption)

**Goal:** Ensure announcements never trigger agent subscriptions.

---

## Task 3.1: Add Scheduler Guard

**File:** `src/flock/orchestrator.py`

**Current code** (line 844-867 is `_schedule_artifact` method):
```python
async def _schedule_artifact(self, artifact: Artifact) -> None:
    for agent in self.agents:
        identity = agent.identity
        for subscription in agent.subscriptions:
            if not subscription.accepts_events():
                continue
            # ... rest of logic ...
```

**What to do:** Add guard at the very top of the method:

```python
async def _schedule_artifact(self, artifact: Artifact) -> None:
    """Schedule agents that match artifact subscriptions.

    Announcements (artifacts tagged with ANNOUNCEMENT_TAG) are skipped
    to prevent unintended agent triggers.
    """
    from flock.system_artifacts import ANNOUNCEMENT_TAG

    # Guard: Skip announcements (defensive programming)
    if ANNOUNCEMENT_TAG in artifact.tags:
        return

    # Existing scheduling logic continues...
    for agent in self.agents:
        identity = agent.identity
        for subscription in agent.subscriptions:
            # ... rest unchanged ...
```

**Why we're doing this:**
- Defensive: prevents scheduling even if someone calls `_persist(artifact, schedule=True)` with announcement
- Explicit: code documents "announcements never schedule"
- Early return: efficient (no iteration if it's an announcement)

**Where exactly:** Right after the method signature (line 844), before the `for agent in self.agents:` loop

**Test it:**
```bash
uv run python -c "
import asyncio
from flock import Flock, SystemAnnouncement
from pydantic import BaseModel

class Task(BaseModel):
    name: str

class Result(BaseModel):
    output: str

async def test():
    flock = Flock('openai/gpt-4.1')

    # Create an agent that would normally consume anything
    agent = (
        flock.agent('test_agent')
        .consumes(Task)
        .publishes(Result)
    )

    # Post announcement
    await flock.post_announcement('Test message')

    # Try to schedule manually (should be skipped)
    artifacts = await flock.store.list()
    announcement = [a for a in artifacts if '__announcement__' in a.tags][0]

    # This should NOT schedule the agent
    await flock._schedule_artifact(announcement)

    # Verify no tasks were created
    assert len(flock._tasks) == 0
    print('✅ Scheduler guard works: no tasks created')

    print('\\n🎉 Phase 3 Complete!')

asyncio.run(test())
"
```

**Acceptance Criteria:**
- [ ] Guard is first line in `_schedule_artifact()`
- [ ] Returns early if `ANNOUNCEMENT_TAG` in tags
- [ ] Test shows no tasks scheduled
- [ ] Docstring mentions announcement skip

---

## Phase 3 Checkpoint ✅

**Verify Phase 3 is complete:**
```bash
# Run test from Task 3.1
# Should print: ✅ Scheduler guard works: no tasks created
```

---

# Phase 4: Agent Opt-Out (Builder API)

**Goal:** Let agents ignore announcements via `.ignore_announcements()`.

---

## Task 4.1: Add Agent Property

**File:** `src/flock/agent.py`

**Current code** (line 92-115 defines `Agent.__init__`):
```python
def __init__(self, name: str, *, orchestrator: Flock) -> None:
    self.name = name
    self.description: str | None = None
    # ... other properties ...
    self.prevent_self_trigger: bool = True  # T065: Prevent infinite feedback loops
```

**What to do:** Add property after `prevent_self_trigger` (around line 109):

```python
    self.prevent_self_trigger: bool = True  # T065: Prevent infinite feedback loops
    self.ignore_announcements: bool = False  # System announcements opt-out
    # MCP integration
    self.mcp_server_names: set[str] = set()
```

**Why we're doing this:**
- Simple boolean flag (no complex configuration needed)
- Default `False` means announcements included (opt-in by default)
- Follows pattern of `prevent_self_trigger`

**Acceptance Criteria:**
- [ ] `self.ignore_announcements: bool = False` added
- [ ] Placed after `prevent_self_trigger` line

---

## Task 4.2: Add Builder Method

**File:** `src/flock/agent.py`

**Where to put it:** After the `prevent_self_trigger()` method (around line 886), before "Runtime helpers" comment (line 888)

**What to do:** Add this method:

```python
def ignore_announcements(self, enabled: bool = True) -> AgentBuilder:
    """Exclude system announcements from agent context.

    By default, agents receive system announcements in their context
    (via EngineComponent.fetch_conversation_context). Use this method
    to opt-out for agents that:
    - Have tight context budgets
    - Need deterministic behavior
    - Should be isolated from steering

    Args:
        enabled: True to ignore announcements (default),
                False to include them (reset to default)

    Returns:
        AgentBuilder for method chaining

    Examples:
        >>> # Agent with announcements (default)
        >>> agent = flock.agent("my_agent").consumes(Task).publishes(Result)

        >>> # Agent without announcements (opt-out)
        >>> tight_agent = (
        ...     flock.agent("tight_context")
        ...     .consumes(LargeDoc)
        ...     .publishes(Summary)
        ...     .ignore_announcements()  # Needs every token for the doc
        ... )

        >>> # Reset to default (include announcements)
        >>> agent.ignore_announcements(False)

    See Also:
        - Flock.post_announcement(): Publishing announcements
        - EngineComponent.fetch_conversation_context(): Context assembly
    """
    self._agent.ignore_announcements = enabled
    return self
```

**Why we're doing this:**
- Fluent API consistent with existing methods
- Comprehensive docstring with examples
- Mentions related methods (good DX)

**Test it:**
```bash
uv run python -c "
from flock import Flock
from pydantic import BaseModel

class Task(BaseModel):
    name: str

class Result(BaseModel):
    output: str

flock = Flock('openai/gpt-4.1')

# Test 1: Default (announcements included)
agent1 = flock.agent('agent1').consumes(Task).publishes(Result)
assert agent1.agent.ignore_announcements == False
print('✅ Default: announcements included')

# Test 2: Opt-out
agent2 = (
    flock.agent('agent2')
    .consumes(Task)
    .publishes(Result)
    .ignore_announcements()
)
assert agent2.agent.ignore_announcements == True
print('✅ Opt-out works')

# Test 3: Reset
agent3 = (
    flock.agent('agent3')
    .consumes(Task)
    .publishes(Result)
    .ignore_announcements(False)
)
assert agent3.agent.ignore_announcements == False
print('✅ Reset works')

print('\\n🎉 Phase 4 Complete!')
"
```

**Acceptance Criteria:**
- [ ] Method exists in `AgentBuilder`
- [ ] Sets `self._agent.ignore_announcements`
- [ ] Returns `self` for chaining
- [ ] Default parameter is `True`
- [ ] All tests pass

---

## Phase 4 Checkpoint ✅

**Verify Phase 4 is complete:**
```bash
# Run test from Task 4.2
# Should print all three ✅ checks
```

---

# Phase 5: Context Integration (Engine Changes)

**Goal:** Include announcements in agent context automatically.

---

## Task 5.1: Add Helper Method to EngineComponent

**File:** `src/flock/components.py`

**Where to put it:** After `get_latest_artifact_of_type()` method (around line 172), before `should_use_context()` (line 174)

**What to do:** Add this helper method:

```python
async def _fetch_announcements(
    self,
    ctx: Context,
    agent: Agent,
) -> list[dict[str, Any]]:
    """Fetch active system announcements for inclusion in context.

    Args:
        ctx: Execution context with board access
        agent: Agent requesting context (for visibility checks)

    Returns:
        List of announcement payloads formatted for context
    """
    from datetime import datetime, timezone
    from flock.system_artifacts import ANNOUNCEMENT_TAG

    try:
        all_artifacts = await ctx.board.list()

        # Filter to announcements
        announcements = [
            a for a in all_artifacts
            if ANNOUNCEMENT_TAG in a.tags
        ]

        # Check visibility (reuse orchestrator's method)
        orchestrator = getattr(ctx, "orchestrator", None)
        if orchestrator:
            visible_announcements = [
                a for a in announcements
                if orchestrator._check_visibility(a, agent.identity)
            ]
        else:
            visible_announcements = announcements

        # Filter expired announcements
        now = datetime.now(timezone.utc)
        active_announcements = []
        for artifact in visible_announcements:
            payload = artifact.payload
            expires_at = payload.get("expires_at")

            # Skip if expired
            if expires_at:
                # Parse ISO format datetime
                if isinstance(expires_at, str):
                    from datetime import datetime
                    try:
                        exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        if now > exp_dt:
                            continue  # Expired, skip
                    except Exception:
                        pass  # Can't parse, include it

            active_announcements.append(artifact)

        # Sort by creation time (oldest first)
        active_announcements.sort(key=lambda a: a.created_at)

        # Format for context
        formatted = []
        for artifact in active_announcements:
            formatted.append({
                "type": "system_announcement",
                "level": artifact.payload.get("level", "info"),
                "message": artifact.payload.get("message", ""),
                "topics": list(artifact.payload.get("topics", [])),
            })

        return formatted

    except Exception:
        # Fail gracefully - don't break agent execution
        return []

def should_use_context(self, inputs: EvalInputs) -> bool:
```

**Add type hints at top of file** (around line 5-10):
```python
if TYPE_CHECKING:  # pragma: no cover - type checking only
    from uuid import UUID

    from flock.agent import Agent  # Add this import
    from flock.artifacts import Artifact
    from flock.runtime import Context, EvalInputs, EvalResult
```

**Why we're doing this:**
- Encapsulates announcement logic (clean separation)
- Handles visibility checks (respects access control)
- Filters expired announcements (automatic cleanup)
- Fails gracefully (won't break agent if something goes wrong)

**Acceptance Criteria:**
- [ ] Method exists in `EngineComponent`
- [ ] Returns list of formatted announcements
- [ ] Filters by visibility
- [ ] Filters by expiration
- [ ] Handles errors gracefully

---

## Task 5.2: Modify `fetch_conversation_context()` to Include Announcements

**File:** `src/flock/components.py`

**Current code** (lines 112-161):
```python
async def fetch_conversation_context(
    self,
    ctx: Context,
    correlation_id: UUID | None = None,
    max_artifacts: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch all artifacts with the same correlation_id for conversation context."""
    if not self.enable_context or not ctx:
        return []

    target_correlation_id = correlation_id or getattr(ctx, "correlation_id", None)
    if not target_correlation_id:
        return []

    try:
        all_artifacts = await ctx.board.list()

        context_artifacts = [
            a for a in all_artifacts
            if (
                a.correlation_id == target_correlation_id
                and a.type not in self.context_exclude_types
            )
        ]

        # ... rest of method ...
```

**What to do:** Modify to include announcements. Replace the entire method with:

```python
async def fetch_conversation_context(
    self,
    ctx: Context,
    correlation_id: UUID | None = None,
    max_artifacts: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch conversation context including announcements.

    Context includes:
    1. System announcements (if agent allows)
    2. Conversation artifacts (filtered by correlation_id)

    Announcements appear FIRST in context (system message position).
    """
    if not self.enable_context or not ctx:
        return []

    target_correlation_id = correlation_id or getattr(ctx, "correlation_id", None)
    if not target_correlation_id:
        return []

    try:
        all_artifacts = await ctx.board.list()

        # 1. Fetch conversation artifacts (existing logic)
        context_artifacts = [
            a for a in all_artifacts
            if (
                a.correlation_id == target_correlation_id
                and a.type not in self.context_exclude_types
            )
        ]

        context_artifacts.sort(key=lambda a: a.created_at)

        max_limit = max_artifacts if max_artifacts is not None else self.context_max_artifacts
        if max_limit is not None and max_limit > 0:
            context_artifacts = context_artifacts[-max_limit:]

        # Format conversation context
        conversation_context = []
        for i, artifact in enumerate(context_artifacts):
            conversation_context.append({
                "type": artifact.type,
                "payload": artifact.payload,
                "produced_by": artifact.produced_by,
                "event_number": i,
            })

        # 2. Fetch announcements (new logic)
        # Check if agent opted out
        # We need agent reference - it's not passed to this method currently!
        # We'll need to modify the signature OR access via context
        # For now, let's access via context.orchestrator to get current agent

        announcement_context = []

        # Try to get agent from context (we'll need to track this)
        # For now, we'll assume context has an agent_name attribute
        agent = None
        orchestrator = getattr(ctx, "orchestrator", None)
        if orchestrator and hasattr(ctx, "agent_name"):
            try:
                agent = orchestrator.get_agent(ctx.agent_name)
            except Exception:
                pass

        # If we have agent, check opt-out
        if agent is None or not getattr(agent, "ignore_announcements", False):
            announcement_context = await self._fetch_announcements(ctx, agent or None)

        # 3. Combine: announcements FIRST (system message position)
        return announcement_context + conversation_context

    except Exception:
        return []
```

**Wait! Problem:** We need agent reference but don't have it. Let's fix this properly.

**Better approach:** Pass agent to the method. Let's update the signature:

**What to do (REVISED):** Add `agent` parameter to the method:

```python
async def fetch_conversation_context(
    self,
    ctx: Context,
    agent: Agent | None = None,  # Add this parameter
    correlation_id: UUID | None = None,
    max_artifacts: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch conversation context including announcements.

    Context includes:
    1. System announcements (if agent allows)
    2. Conversation artifacts (filtered by correlation_id)

    Announcements appear FIRST in context (system message position).

    Args:
        ctx: Execution context
        agent: Agent requesting context (for announcement opt-out check)
        correlation_id: Optional correlation ID override
        max_artifacts: Optional max artifacts override
    """
    if not self.enable_context or not ctx:
        return []

    target_correlation_id = correlation_id or getattr(ctx, "correlation_id", None)
    if not target_correlation_id:
        return []

    try:
        all_artifacts = await ctx.board.list()

        # 1. Fetch conversation artifacts (existing logic)
        context_artifacts = [
            a for a in all_artifacts
            if (
                a.correlation_id == target_correlation_id
                and a.type not in self.context_exclude_types
            )
        ]

        context_artifacts.sort(key=lambda a: a.created_at)

        max_limit = max_artifacts if max_artifacts is not None else self.context_max_artifacts
        if max_limit is not None and max_limit > 0:
            context_artifacts = context_artifacts[-max_limit:]

        # Format conversation context
        conversation_context = []
        for i, artifact in enumerate(context_artifacts):
            conversation_context.append({
                "type": artifact.type,
                "payload": artifact.payload,
                "produced_by": artifact.produced_by,
                "event_number": i,
            })

        # 2. Fetch announcements (new logic)
        announcement_context = []
        if agent is None or not getattr(agent, "ignore_announcements", False):
            announcement_context = await self._fetch_announcements(ctx, agent)

        # 3. Combine: announcements FIRST (system message position)
        return announcement_context + conversation_context

    except Exception:
        return []
```

**Also update** the `get_latest_artifact_of_type()` call (line 170):
```python
async def get_latest_artifact_of_type(
    self,
    ctx: Context,
    artifact_type: str,
    agent: Agent | None = None,  # Add this
    correlation_id: UUID | None = None,
) -> dict[str, Any] | None:
    """Get the most recent artifact of a specific type in the conversation."""
    context = await self.fetch_conversation_context(ctx, agent, correlation_id)  # Pass agent
    matching = [a for a in context if a["type"].endswith(artifact_type)]
    return matching[-1] if matching else None
```

**Why we're doing this:**
- Announcements included by default (unless agent opts out)
- Announcements appear FIRST (prime LLM attention)
- Backward compatible (agent parameter is optional)

**Acceptance Criteria:**
- [ ] Method signature includes `agent` parameter
- [ ] Announcements fetched if agent allows
- [ ] Announcements placed before conversation context
- [ ] Returns empty list on error (graceful failure)

---

## Task 5.3: Update DSPy Engine to Pass Agent

**File:** `src/flock/engines/dspy_engine.py`

**Current code** (line 176):
```python
# Fetch conversation context from blackboard
context_history = await self.fetch_conversation_context(ctx)
```

**What to do:** Pass the agent parameter:

```python
# Fetch conversation context from blackboard
context_history = await self.fetch_conversation_context(ctx, agent)
```

**That's it!** Just add the `agent` parameter.

**Why we're doing this:**
- Enables announcement opt-out check
- Agent is already available in this scope (it's a parameter to `evaluate()`)

**Where:** Line 176 in `dspy_engine.py`

**Acceptance Criteria:**
- [ ] `agent` parameter passed to `fetch_conversation_context()`

---

## Task 5.4: Add Agent to Runtime Context

**File:** `src/flock/runtime.py`

This task is **optional** but recommended for future extensibility.

**Current code** (check what `Context` dataclass looks like):

If `Context` doesn't have an `agent_name` field, you could add it, but for now we're passing agent explicitly so this is **SKIPPED**.

---

## Phase 5 Checkpoint ✅

**Verify Phase 5 is complete:**

```bash
uv run python -c "
import asyncio
from flock import Flock, SystemAnnouncement
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

class Task(BaseModel):
    name: str

class Result(BaseModel):
    output: str

async def test():
    flock = Flock('openai/gpt-4.1')

    # Post an announcement
    await flock.post_announcement(
        'Test announcement',
        topics={'test'}
    )

    # Post an expired announcement (should be filtered)
    await flock.post_announcement(
        SystemAnnouncement(
            message='Expired',
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
    )

    # Create test agent
    agent = flock.agent('test_agent').consumes(Task).publishes(Result)

    # Simulate context fetch
    from flock.components import EngineComponent
    from flock.runtime import Context, EvalInputs
    from flock.orchestrator import BoardHandle
    from uuid import uuid4

    ctx = Context(
        board=BoardHandle(flock),
        orchestrator=flock,
        task_id=str(uuid4()),
        correlation_id=uuid4()
    )

    engine = EngineComponent()
    context = await engine.fetch_conversation_context(ctx, agent.agent, ctx.correlation_id)

    # Should have announcement but not expired one
    announcements = [c for c in context if c.get('type') == 'system_announcement']
    assert len(announcements) == 1
    assert announcements[0]['message'] == 'Test announcement'
    print('✅ Announcements included in context')

    # Test opt-out
    agent2 = (
        flock.agent('opt_out_agent')
        .consumes(Task)
        .publishes(Result)
        .ignore_announcements()
    )

    context2 = await engine.fetch_conversation_context(ctx, agent2.agent, ctx.correlation_id)
    announcements2 = [c for c in context2 if c.get('type') == 'system_announcement']
    assert len(announcements2) == 0
    print('✅ Opt-out works')

    print('\\n🎉 Phase 5 Complete!')

asyncio.run(test())
"
```

**Acceptance Criteria:**
- [ ] Active announcements appear in context
- [ ] Expired announcements are filtered
- [ ] Opt-out agents don't receive announcements
- [ ] Test passes

---

# Phase 6: Testing (Unit + Integration)

**Goal:** Comprehensive test coverage for all announcement functionality.

---

## Task 6.1: Add Orchestrator Tests

**File:** Create or modify `tests/test_orchestrator.py`

**What to do:** Add these test functions:

```python
import pytest
from datetime import datetime, timezone, timedelta
from flock import Flock, SystemAnnouncement
from flock.system_artifacts import ANNOUNCEMENT_TAG
from pydantic import BaseModel


class TestTask(BaseModel):
    name: str


class TestResult(BaseModel):
    output: str


@pytest.mark.asyncio
async def test_post_announcement_string():
    """Test posting announcement as string."""
    flock = Flock("openai/gpt-4.1")

    artifact = await flock.post_announcement("Test message")

    assert ANNOUNCEMENT_TAG in artifact.tags
    assert artifact.produced_by == "system"
    assert artifact.type == "flock.SystemAnnouncement"
    assert artifact.payload["message"] == "Test message"
    assert artifact.payload["level"] == "info"


@pytest.mark.asyncio
async def test_post_announcement_model():
    """Test posting announcement as SystemAnnouncement model."""
    flock = Flock("openai/gpt-4.1")

    ann = SystemAnnouncement(
        message="Warning message",
        level="warning",
        topics={"security", "database"}
    )
    artifact = await flock.post_announcement(ann)

    assert ANNOUNCEMENT_TAG in artifact.tags
    assert artifact.payload["level"] == "warning"
    assert "security" in artifact.payload["topics"]


@pytest.mark.asyncio
async def test_post_announcement_metrics():
    """Test announcement metrics counter."""
    flock = Flock("openai/gpt-4.1")

    assert flock.metrics["announcements_posted"] == 0

    await flock.post_announcement("Test 1")
    assert flock.metrics["announcements_posted"] == 1

    await flock.post_announcement("Test 2")
    assert flock.metrics["announcements_posted"] == 2


@pytest.mark.asyncio
async def test_announcement_not_scheduled():
    """Test that announcements don't trigger agent subscriptions."""
    flock = Flock("openai/gpt-4.1")

    # Create agent that would consume if scheduled
    agent = (
        flock.agent("test_agent")
        .consumes(TestTask)
        .publishes(TestResult)
    )

    # Post announcement
    await flock.post_announcement("Should not trigger agent")

    # Verify no tasks scheduled
    assert len(flock._tasks) == 0


@pytest.mark.asyncio
async def test_announcement_persisted():
    """Test that announcements are stored in blackboard."""
    flock = Flock("openai/gpt-4.1")

    artifact = await flock.post_announcement("Persisted message")

    # Retrieve from store
    stored = await flock.store.get(artifact.id)
    assert stored is not None
    assert ANNOUNCEMENT_TAG in stored.tags


@pytest.mark.asyncio
async def test_board_handle_post_announcement():
    """Test posting announcement via BoardHandle."""
    from flock.orchestrator import BoardHandle

    flock = Flock("openai/gpt-4.1")
    board = BoardHandle(flock)

    artifact = await board.post_announcement("Via board")

    assert ANNOUNCEMENT_TAG in artifact.tags
    assert flock.metrics["announcements_posted"] == 1
```

**Where to put it:** Add to existing `tests/test_orchestrator.py` or create new file if it doesn't exist

**Run tests:**
```bash
uv run pytest tests/test_orchestrator.py -v -k announcement
```

**Acceptance Criteria:**
- [ ] All 6 tests pass
- [ ] Tests cover: string, model, metrics, scheduling, persistence, board handle

---

## Task 6.2: Add Component Tests

**File:** Modify `tests/test_components.py`

**What to do:** Add these test functions at the end:

```python
@pytest.mark.asyncio
async def test_fetch_announcements():
    """Test fetching announcements in context."""
    from flock import Flock, SystemAnnouncement
    from flock.components import EngineComponent
    from flock.orchestrator import BoardHandle
    from flock.runtime import Context
    from uuid import uuid4
    from pydantic import BaseModel

    class TestTask(BaseModel):
        name: str

    class TestResult(BaseModel):
        output: str

    flock = Flock("openai/gpt-4.1")

    # Post announcement
    await flock.post_announcement("Test announcement")

    # Create agent
    agent = flock.agent("test").consumes(TestTask).publishes(TestResult)

    # Create context
    ctx = Context(
        board=BoardHandle(flock),
        orchestrator=flock,
        task_id=str(uuid4()),
        correlation_id=uuid4()
    )

    # Fetch context
    engine = EngineComponent()
    context = await engine.fetch_conversation_context(ctx, agent.agent, ctx.correlation_id)

    # Should have announcement
    announcements = [c for c in context if c.get("type") == "system_announcement"]
    assert len(announcements) == 1
    assert announcements[0]["message"] == "Test announcement"


@pytest.mark.asyncio
async def test_announcement_opt_out():
    """Test agent opt-out of announcements."""
    from flock import Flock
    from flock.components import EngineComponent
    from flock.orchestrator import BoardHandle
    from flock.runtime import Context
    from uuid import uuid4
    from pydantic import BaseModel

    class TestTask(BaseModel):
        name: str

    class TestResult(BaseModel):
        output: str

    flock = Flock("openai/gpt-4.1")

    # Post announcement
    await flock.post_announcement("Should be filtered")

    # Create agent with opt-out
    agent = (
        flock.agent("opt_out")
        .consumes(TestTask)
        .publishes(TestResult)
        .ignore_announcements()
    )

    # Create context
    ctx = Context(
        board=BoardHandle(flock),
        orchestrator=flock,
        task_id=str(uuid4()),
        correlation_id=uuid4()
    )

    # Fetch context
    engine = EngineComponent()
    context = await engine.fetch_conversation_context(ctx, agent.agent, ctx.correlation_id)

    # Should NOT have announcements
    announcements = [c for c in context if c.get("type") == "system_announcement"]
    assert len(announcements) == 0


@pytest.mark.asyncio
async def test_expired_announcements_filtered():
    """Test that expired announcements are filtered from context."""
    from flock import Flock, SystemAnnouncement
    from flock.components import EngineComponent
    from flock.orchestrator import BoardHandle
    from flock.runtime import Context
    from datetime import datetime, timezone, timedelta
    from uuid import uuid4
    from pydantic import BaseModel

    class TestTask(BaseModel):
        name: str

    class TestResult(BaseModel):
        output: str

    flock = Flock("openai/gpt-4.1")

    # Post active announcement
    await flock.post_announcement("Active")

    # Post expired announcement
    expired = SystemAnnouncement(
        message="Expired",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    await flock.post_announcement(expired)

    # Create agent
    agent = flock.agent("test").consumes(TestTask).publishes(TestResult)

    # Create context
    ctx = Context(
        board=BoardHandle(flock),
        orchestrator=flock,
        task_id=str(uuid4()),
        correlation_id=uuid4()
    )

    # Fetch context
    engine = EngineComponent()
    context = await engine.fetch_conversation_context(ctx, agent.agent, ctx.correlation_id)

    # Should only have active announcement
    announcements = [c for c in context if c.get("type") == "system_announcement"]
    assert len(announcements) == 1
    assert announcements[0]["message"] == "Active"
```

**Run tests:**
```bash
uv run pytest tests/test_components.py -v -k announcement
```

**Acceptance Criteria:**
- [ ] All 3 tests pass
- [ ] Tests cover: fetching, opt-out, expiration

---

## Task 6.3: Add Agent Builder Tests

**File:** Modify or create `tests/test_agent.py`

**What to do:** Add test function:

```python
def test_ignore_announcements_builder():
    """Test AgentBuilder.ignore_announcements() method."""
    from flock import Flock
    from pydantic import BaseModel

    class TestTask(BaseModel):
        name: str

    class TestResult(BaseModel):
        output: str

    flock = Flock("openai/gpt-4.1")

    # Default: announcements included
    agent1 = flock.agent("default").consumes(TestTask).publishes(TestResult)
    assert agent1.agent.ignore_announcements is False

    # Opt-out: announcements ignored
    agent2 = (
        flock.agent("opt_out")
        .consumes(TestTask)
        .publishes(TestResult)
        .ignore_announcements()
    )
    assert agent2.agent.ignore_announcements is True

    # Explicit opt-in: announcements included
    agent3 = (
        flock.agent("explicit_opt_in")
        .consumes(TestTask)
        .publishes(TestResult)
        .ignore_announcements(False)
    )
    assert agent3.agent.ignore_announcements is False
```

**Run tests:**
```bash
uv run pytest tests/test_agent.py -v -k announcement
```

**Acceptance Criteria:**
- [ ] Test passes
- [ ] Tests default, opt-out, and reset behavior

---

## Task 6.4: Add Integration Test

**File:** Create new file `tests/test_announcements_integration.py`

**What to do:** Add comprehensive end-to-end test:

```python
"""Integration tests for system announcements feature."""

import pytest
from datetime import datetime, timezone, timedelta
from flock import Flock, SystemAnnouncement
from flock.system_artifacts import ANNOUNCEMENT_TAG
from pydantic import BaseModel


class MovieIdea(BaseModel):
    """Input: movie concept."""
    topic: str


class Movie(BaseModel):
    """Output: structured movie."""
    title: str
    plot: str


@pytest.mark.asyncio
async def test_announcement_full_workflow():
    """Test complete announcement workflow: publish → context → opt-out."""
    flock = Flock("openai/gpt-4.1")

    # Step 1: Post announcements
    ann1 = await flock.post_announcement(
        "Always make plots kid-friendly",
        level="info",
        topics={"content_policy"}
    )

    ann2 = await flock.post_announcement(
        SystemAnnouncement(
            message="Avoid political themes",
            level="warning",
            topics={"content_policy"},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
    )

    # Verify stored
    assert ann1.id is not None
    assert ANNOUNCEMENT_TAG in ann1.tags
    assert flock.metrics["announcements_posted"] == 2

    # Step 2: Create agent that receives announcements
    agent_with_context = (
        flock.agent("movie_writer")
        .description("Write movie scripts")
        .consumes(MovieIdea)
        .publishes(Movie)
    )

    # Step 3: Create agent that ignores announcements
    agent_without_context = (
        flock.agent("tight_context_writer")
        .description("Write movies with limited context")
        .consumes(MovieIdea)
        .publishes(Movie)
        .ignore_announcements()
    )

    # Step 4: Simulate context fetch for agent WITH announcements
    from flock.components import EngineComponent
    from flock.orchestrator import BoardHandle
    from flock.runtime import Context
    from uuid import uuid4

    ctx = Context(
        board=BoardHandle(flock),
        orchestrator=flock,
        task_id=str(uuid4()),
        correlation_id=uuid4()
    )

    engine = EngineComponent()
    context_with = await engine.fetch_conversation_context(
        ctx,
        agent_with_context.agent,
        ctx.correlation_id
    )

    # Should have 2 announcements
    announcements_with = [
        c for c in context_with if c.get("type") == "system_announcement"
    ]
    assert len(announcements_with) == 2
    assert announcements_with[0]["message"] == "Always make plots kid-friendly"

    # Step 5: Simulate context fetch for agent WITHOUT announcements
    context_without = await engine.fetch_conversation_context(
        ctx,
        agent_without_context.agent,
        ctx.correlation_id
    )

    # Should have 0 announcements
    announcements_without = [
        c for c in context_without if c.get("type") == "system_announcement"
    ]
    assert len(announcements_without) == 0


@pytest.mark.asyncio
async def test_announcement_does_not_trigger_cascade():
    """Test that announcements don't trigger agent execution."""
    flock = Flock("openai/gpt-4.1")

    # Create agent
    agent = (
        flock.agent("movie_writer")
        .consumes(MovieIdea)
        .publishes(Movie)
    )

    # Post announcement
    await flock.post_announcement("Test steering")

    # Wait for any potential triggers
    await flock.run_until_idle()

    # Verify agent never ran
    assert flock.metrics["agent_runs"] == 0

    # Verify announcement was posted
    assert flock.metrics["announcements_posted"] == 1


@pytest.mark.asyncio
async def test_announcement_visibility():
    """Test that announcements respect visibility controls."""
    from flock.visibility import PrivateVisibility

    flock = Flock("openai/gpt-4.1")

    # Post private announcement
    await flock.post_announcement(
        "Secret announcement",
        visibility=PrivateVisibility(agents={"admin_agent"})
    )

    # Create admin agent (should see it)
    admin_agent = (
        flock.agent("admin_agent")
        .consumes(MovieIdea)
        .publishes(Movie)
    )

    # Create regular agent (should NOT see it)
    regular_agent = (
        flock.agent("regular_agent")
        .consumes(MovieIdea)
        .publishes(Movie)
    )

    # Simulate context fetch
    from flock.components import EngineComponent
    from flock.orchestrator import BoardHandle
    from flock.runtime import Context
    from uuid import uuid4

    ctx = Context(
        board=BoardHandle(flock),
        orchestrator=flock,
        task_id=str(uuid4()),
        correlation_id=uuid4()
    )

    engine = EngineComponent()

    # Admin sees it
    admin_context = await engine.fetch_conversation_context(
        ctx,
        admin_agent.agent,
        ctx.correlation_id
    )
    admin_announcements = [
        c for c in admin_context if c.get("type") == "system_announcement"
    ]
    assert len(admin_announcements) == 1

    # Regular agent doesn't see it
    regular_context = await engine.fetch_conversation_context(
        ctx,
        regular_agent.agent,
        ctx.correlation_id
    )
    regular_announcements = [
        c for c in regular_context if c.get("type") == "system_announcement"
    ]
    assert len(regular_announcements) == 0
```

**Run tests:**
```bash
uv run pytest tests/test_announcements_integration.py -v
```

**Acceptance Criteria:**
- [ ] All 3 integration tests pass
- [ ] Tests cover: full workflow, non-triggering, visibility

---

## Task 6.5: Run Full Test Suite

**What to do:** Run all tests to ensure nothing broke:

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test files
uv run pytest tests/test_orchestrator.py tests/test_components.py tests/test_agent.py tests/test_announcements_integration.py -v
```

**Fix any failures:** If existing tests break, it's likely because:
1. `fetch_conversation_context()` signature changed (added `agent` parameter)
2. Need to update test calls to pass `agent` or `None`

**Example fix:**
```python
# If test fails like: TypeError: fetch_conversation_context() missing 1 required positional argument: 'agent'

# Old call:
context = await engine.fetch_conversation_context(ctx, correlation_id)

# New call:
context = await engine.fetch_conversation_context(ctx, None, correlation_id)
```

**Acceptance Criteria:**
- [ ] All existing tests pass
- [ ] All new announcement tests pass
- [ ] No regressions in core functionality

---

## Phase 6 Checkpoint ✅

**Verify Phase 6 is complete:**
```bash
# Run all tests
uv run pytest tests/ -v --tb=short

# Should see:
# - test_post_announcement_* (6 tests)
# - test_fetch_announcements (1 test)
# - test_announcement_opt_out (1 test)
# - test_expired_announcements_filtered (1 test)
# - test_ignore_announcements_builder (1 test)
# - test_announcement_full_workflow (1 test)
# - test_announcement_does_not_trigger_cascade (1 test)
# - test_announcement_visibility (1 test)
# Total: ~12+ new tests
```

---

# Phase 7: Documentation + Examples

**Goal:** Complete user-facing documentation and working examples.

---

## Task 7.1: Add Example Script

**File:** Create new file `examples/02-the-blackboard/02_announcements.py`

**What to do:** Create comprehensive example showing announcement usage:

```python
"""
🔔 SYSTEM ANNOUNCEMENTS
=======================

Learn how to use system announcements for runtime steering and global policy.

Announcements are broadcast messages that:
- Appear in agent context (like system messages)
- DON'T trigger agent subscriptions
- Respect visibility controls
- Support expiration for time-bounded steering

⏱️  TIME: 5 minutes
💡 DIFFICULTY: ⭐⭐ Intermediate
"""

import asyncio
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from flock import Flock, SystemAnnouncement


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📦 Define Your Artifacts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MovieIdea(BaseModel):
    """Input: A movie concept."""

    topic: str


class Movie(BaseModel):
    """Output: A structured movie script."""

    title: str
    plot: str
    target_audience: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🤖 Create Orchestrator and Agents
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock("openai/gpt-4.1")

# Agent that receives announcements (default)
movie_writer = (
    flock.agent("movie_writer")
    .description("Write creative movie scripts based on ideas")
    .consumes(MovieIdea)
    .publishes(Movie)
)

# Agent that ignores announcements (needs tight context)
deterministic_writer = (
    flock.agent("deterministic_writer")
    .description("Write predictable movie scripts")
    .consumes(MovieIdea)
    .publishes(Movie)
    .ignore_announcements()  # Opt-out of steering
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📢 Publish Announcements
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    print("📢 SYSTEM ANNOUNCEMENTS DEMO\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Example 1: Simple String Announcement
    # ──────────────────────────────────────────────────────────────────────────
    print("1️⃣ Simple string announcement:")
    ann1 = await flock.post_announcement("Always make movies kid-friendly")
    print(f"   ✅ Posted: {ann1.id}")
    print(f"   📦 Type: {ann1.type}")
    print(f"   🏷️ Tags: {ann1.tags}\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Example 2: Structured Announcement with Levels
    # ──────────────────────────────────────────────────────────────────────────
    print("2️⃣ Warning-level announcement:")
    ann2 = await flock.post_announcement(
        "Avoid political themes in all scripts",
        level="warning",
        topics={"content_policy", "safety"},
    )
    print(f"   ⚠️ Level: {ann2.payload['level']}")
    print(f"   🏷️ Topics: {ann2.payload['topics']}\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Example 3: Expiring Announcement
    # ──────────────────────────────────────────────────────────────────────────
    print("3️⃣ Time-bounded announcement (expires in 1 hour):")
    ann3 = await flock.post_announcement(
        SystemAnnouncement(
            message="Special promotion: sci-fi movies get priority",
            level="info",
            topics={"promotion"},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    print(f"   ⏰ Expires: {ann3.payload['expires_at']}\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Example 4: Check Metrics
    # ──────────────────────────────────────────────────────────────────────────
    print("4️⃣ Check announcement metrics:")
    print(f"   📊 Announcements posted: {flock.metrics['announcements_posted']}")
    print(f"   📦 Artifacts published: {flock.metrics['artifacts_published']}")
    print(f"   🤖 Agent runs: {flock.metrics['agent_runs']}\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Example 5: Verify Announcements Don't Trigger Agents
    # ──────────────────────────────────────────────────────────────────────────
    print("5️⃣ Verify announcements don't trigger cascades:")
    await flock.run_until_idle()
    print(f"   ✅ Agent runs after announcements: {flock.metrics['agent_runs']}")
    print("   (Should still be 0 - announcements don't trigger agents)\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Example 6: Inspect Context (What Agents See)
    # ──────────────────────────────────────────────────────────────────────────
    print("6️⃣ What agents see in context:")
    from uuid import uuid4

    from flock.components import EngineComponent
    from flock.orchestrator import BoardHandle
    from flock.runtime import Context

    ctx = Context(
        board=BoardHandle(flock),
        orchestrator=flock,
        task_id=str(uuid4()),
        correlation_id=uuid4(),
    )

    engine = EngineComponent()

    # Agent WITH announcements
    context_with = await engine.fetch_conversation_context(
        ctx, movie_writer.agent, ctx.correlation_id
    )
    announcements_with = [c for c in context_with if c.get("type") == "system_announcement"]
    print(f"   movie_writer sees {len(announcements_with)} announcements:")
    for ann in announcements_with:
        print(f"     - [{ann['level'].upper()}] {ann['message']}")

    # Agent WITHOUT announcements
    context_without = await engine.fetch_conversation_context(
        ctx, deterministic_writer.agent, ctx.correlation_id
    )
    announcements_without = [
        c for c in context_without if c.get("type") == "system_announcement"
    ]
    print(f"\n   deterministic_writer sees {len(announcements_without)} announcements")
    print("   (opted out with .ignore_announcements())\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Example 7: Private Announcements
    # ──────────────────────────────────────────────────────────────────────────
    print("7️⃣ Private announcement (visibility-controlled):")
    from flock.visibility import PrivateVisibility

    private_ann = await flock.post_announcement(
        "Internal note: review all movie_writer outputs",
        visibility=PrivateVisibility(agents={"admin_agent", "reviewer"}),
    )
    print(f"   🔒 Visible only to: {private_ann.visibility.agents}\n")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 KEY TAKEAWAYS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ✅ Announcements are system-level steering (not triggers)
# ✅ They appear in agent context automatically (unless opted out)
# ✅ Use expires_at for time-bounded policies
# ✅ Levels (info/warning/critical) help dashboard filtering
# ✅ Topics enable categorization
# ✅ Visibility controls enable tenant isolation
# ✅ Opt-out with .ignore_announcements() for tight contexts
#
# 🚀 NEXT: See examples/03-the-dashboard/ for announcement visualization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main(), debug=True)
```

**Test it:**
```bash
uv run python examples/02-the-blackboard/02_announcements.py
```

**Acceptance Criteria:**
- [ ] Example runs without errors
- [ ] All 7 examples demonstrate different features
- [ ] Output is clear and educational
- [ ] Comments explain the "why"

---

## Task 7.2: Update AGENTS.md Documentation

**File:** `AGENTS.md`

**Where to add:** In the "CRITICAL PATTERNS" section (after line 235), add new section:

**What to do:** Add this section:

```markdown
---

### 📢 System Announcements - Runtime Steering Without Triggers

**Production teams needed global policy updates without modifying every agent—now you can broadcast steering via the blackboard.**

#### Why this matters
- **Runtime steering**: Update agent behavior without redeployment
- **Global policies**: Company rules, API guidelines, domain knowledge
- **No cascade risk**: Announcements don't trigger subscriptions
- **Visibility-aware**: Tenant isolation and access control work automatically
- **Auto-expiration**: Time-bounded announcements clean themselves up

#### Quick start
```python
from flock import Flock, SystemAnnouncement
from datetime import datetime, timezone, timedelta

flock = Flock("openai/gpt-4.1")

# Simple string announcement
await flock.post_announcement("Always validate user input")

# Structured announcement with expiration
await flock.post_announcement(
    SystemAnnouncement(
        message="Cost controls active",
        level="warning",
        topics={"budget", "operations"},
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
)
```

#### Key behavior

**Announcements are artifacts** (stored on blackboard) but **NOT consumable** (won't trigger agents):

```python
# ✅ Announcement stored: yes
# ❌ Agents triggered: no
await flock.post_announcement("Important policy")
await flock.run_until_idle()  # No agents run
```

**Agents see them in context** (unless opted out):

```python
# Default: announcements included
agent = (
    flock.agent("writer")
    .consumes(Task)
    .publishes(Result)
)

# Opt-out: announcements excluded (for tight contexts)
tight_agent = (
    flock.agent("tight_context")
    .consumes(LargeDoc)
    .publishes(Summary)
    .ignore_announcements()  # Needs every token for the doc
)
```

#### Expiration & cleanup

Announcements with `expires_at` are **automatically filtered** from context:

```python
# Will be ignored after 24 hours
await flock.post_announcement(
    SystemAnnouncement(
        message="Temporary guidance",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
)
```

#### Visibility & access control

Announcements respect visibility like any artifact:

```python
from flock.visibility import PrivateVisibility, TenantVisibility

# Private (specific agents only)
await flock.post_announcement(
    "Admin note: review all outputs",
    visibility=PrivateVisibility(agents={"admin", "reviewer"})
)

# Tenant-scoped (multi-tenant isolation)
await flock.post_announcement(
    "Your company policy here",
    visibility=TenantVisibility(tenant_id="acme_corp")
)
```

#### Components can post too

The `BoardHandle` exposes `post_announcement()`, enabling middleware use cases:

```python
from flock.components import AgentComponent

class AdaptiveTemperature(AgentComponent):
    async def on_post_evaluate(self, agent, ctx, inputs, result):
        if result.confidence < 0.5:
            await ctx.board.post_announcement(
                "Low confidence detected - consider increasing temperature",
                topics={"adaptation"}
            )
        return result
```

#### Best practices

**✅ DO:**
- Keep messages concise (they appear in every agent's context)
- Use `expires_at` for time-bounded steering
- Use topics for categorization (`{"security", "performance"}`)
- Let agents opt-out with `.ignore_announcements()` if needed
- Monitor via `flock.metrics["announcements_posted"]`

**❌ DON'T:**
- Post hundreds of announcements (you'll overflow context)
- Use announcements for agent-to-agent communication (use regular artifacts)
- Forget expiration for temporary policies
- Assume announcements trigger agents (they don't!)

#### Monitoring

Announcements have dedicated metrics:

```python
print(f"Announcements: {flock.metrics['announcements_posted']}")
print(f"Regular artifacts: {flock.metrics['artifacts_published']}")
```

Run the example: `uv run python examples/02-the-blackboard/02_announcements.py`

> **Heads-up:** Announcements are included in agent context by default. If you have tight context budgets, use `.ignore_announcements()` or keep announcement messages brief.

---
```

**Acceptance Criteria:**
- [ ] New section added to AGENTS.md
- [ ] Placed in "CRITICAL PATTERNS" section
- [ ] Includes code examples
- [ ] Links to example file

---

## Task 7.3: Update Pattern Documentation

**File:** Create or update `docs/guides/patterns.md`

**Where to add:** Add new section "System Announcements Pattern"

**What to do:** Add this section:

```markdown
## System Announcements Pattern

### Problem

You need to update agent behavior globally without:
- Redeploying agents
- Modifying every agent's configuration
- Triggering agent cascades
- Breaking tenant isolation

**Example scenarios:**
- "Remind all agents to validate user input"
- "Enable cost controls for the next 24 hours"
- "Apply new content policy across the fleet"

### Solution

Use `flock.post_announcement()` to broadcast system-level guidance that appears in agent context but doesn't trigger subscriptions.

### Implementation

```python
from flock import Flock, SystemAnnouncement
from datetime import datetime, timezone, timedelta

flock = Flock("openai/gpt-4.1")

# Post global policy
await flock.post_announcement(
    "Always sanitize SQL inputs",
    level="warning",
    topics={"security", "database"}
)

# Post time-bounded steering
await flock.post_announcement(
    SystemAnnouncement(
        message="Cost optimization mode active",
        level="critical",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12)
    )
)
```

### When to use

**✅ Use announcements for:**
- Global policies (security, compliance, style guides)
- Runtime steering (A/B testing system prompts)
- Emergency overrides (rate limiting, cost controls)
- Multi-tenant policies (company-specific rules)

**❌ Don't use announcements for:**
- Agent-to-agent communication (use regular artifacts)
- Triggering agent execution (use `publish()` instead)
- Data flow (announcements are static context, not events)

### Tradeoffs

**Advantages:**
- No code changes needed (runtime configuration)
- Respects visibility (tenant isolation preserved)
- Auto-expiration (no manual cleanup)
- Auditable (stored on blackboard like artifacts)

**Disadvantages:**
- Consumes context tokens (every agent sees them)
- Not per-agent (use agent config for that)
- Eventually consistent (new agents see immediately, running agents see on next execution)

### See also

- [AGENTS.md - System Announcements](../../AGENTS.md#-system-announcements---runtime-steering-without-triggers)
- [Example code](../../examples/02-the-blackboard/02_announcements.py)
```

**Acceptance Criteria:**
- [ ] Pattern documented in `docs/guides/patterns.md`
- [ ] Includes problem/solution/implementation
- [ ] Links to AGENTS.md and examples

---

## Task 7.4: Update API Reference

**File:** Create or update `docs/reference/api.md`

**What to add:** API documentation for new methods

**What to do:** Add this section:

```markdown
## System Announcements

### Flock.post_announcement()

```python
async def post_announcement(
    self,
    ann: SystemAnnouncement | str,
    *,
    level: Literal["info", "warning", "critical"] | None = None,
    topics: set[str] | None = None,
    visibility: Visibility | None = None,
    correlation_id: str | None = None,
    partition_key: str | None = None,
    tags: set[str] | None = None,
) -> Artifact
```

Publish a system-level announcement visible to all agents.

**Arguments:**
- `ann`: SystemAnnouncement instance or plain string (auto-wrapped)
- `level`: Override severity (info/warning/critical)
- `topics`: Topic tags for categorization
- `visibility`: Access control (defaults to PublicVisibility)
- `correlation_id`: Optional correlation ID
- `partition_key`: Optional partition key
- `tags`: Additional tags (ANNOUNCEMENT_TAG added automatically)

**Returns:** The published Artifact

**Examples:**
```python
# Simple string
await flock.post_announcement("Validate all inputs")

# Structured with expiration
ann = SystemAnnouncement(
    message="Cost controls active",
    level="warning",
    expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
)
await flock.post_announcement(ann)
```

---

### AgentBuilder.ignore_announcements()

```python
def ignore_announcements(self, enabled: bool = True) -> AgentBuilder
```

Exclude system announcements from agent context.

**Arguments:**
- `enabled`: True to ignore (default), False to include

**Returns:** AgentBuilder for method chaining

**Examples:**
```python
# Opt-out of announcements
agent = (
    flock.agent("tight_context")
    .consumes(Task)
    .publishes(Result)
    .ignore_announcements()
)

# Reset to default (include)
agent.ignore_announcements(False)
```

---

### SystemAnnouncement

```python
class SystemAnnouncement(BaseModel):
    message: str
    level: Literal["info", "warning", "critical"] = "info"
    topics: set[str] = Field(default_factory=set)
    expires_at: datetime | None = None
```

System-level announcement data model.

**Fields:**
- `message`: The announcement text
- `level`: Severity for filtering (info/warning/critical)
- `topics`: Category tags (e.g., {"security", "performance"})
- `expires_at`: Optional expiration timestamp (UTC)

**Example:**
```python
from flock import SystemAnnouncement
from datetime import datetime, timezone, timedelta

ann = SystemAnnouncement(
    message="New policy active",
    level="warning",
    topics={"compliance"},
    expires_at=datetime.now(timezone.utc) + timedelta(days=7)
)
```
```

**Acceptance Criteria:**
- [ ] API reference includes all three items
- [ ] Signatures match implementation
- [ ] Examples are runnable

---

## Task 7.5: Update Version Numbers

**CRITICAL:** Must bump versions per project policy!

**Files:**
- `pyproject.toml` (backend version)
- `src/flock/frontend/package.json` (frontend version if dashboard changes)

**What to do:**

1. **Backend version** (`pyproject.toml`):
```toml
[project]
version = "0.5.0b64"  # Increment from current version (0.5.0b63 → 0.5.0b64)
```

2. **Frontend version** (only if you added dashboard features):
```json
{
  "version": "0.1.5"  // Increment from 0.1.4 if needed
}
```

**Why:** See AGENTS.md lines 308-415 for versioning policy

**Acceptance Criteria:**
- [ ] Backend version incremented in `pyproject.toml`
- [ ] Frontend version incremented if dashboard changed
- [ ] Version numbers follow semantic versioning pattern

---

## Phase 7 Checkpoint ✅

**Verify Phase 7 is complete:**

```bash
# Test example
uv run python examples/02-the-blackboard/02_announcements.py

# Check documentation files exist
ls docs/guides/patterns.md
ls docs/reference/api.md

# Verify version bumped
grep "version = " pyproject.toml
```

**Acceptance Criteria:**
- [ ] Example runs successfully
- [ ] AGENTS.md updated with new section
- [ ] Pattern guide includes announcements
- [ ] API reference complete
- [ ] Versions bumped

---

# 🎉 FINAL CHECKLIST

Before creating PR, verify ALL of these:

## Code
- [ ] `src/flock/system_artifacts.py` created with `SystemAnnouncement` model
- [ ] `ANNOUNCEMENT_TAG` constant defined and exported
- [ ] `Flock.post_announcement()` method implemented
- [ ] `Flock._persist()` refactored with `schedule` parameter
- [ ] `Flock._schedule_artifact()` has announcement guard
- [ ] `BoardHandle.post_announcement()` delegates to orchestrator
- [ ] `Agent.ignore_announcements` property added
- [ ] `AgentBuilder.ignore_announcements()` method added
- [ ] `EngineComponent._fetch_announcements()` helper added
- [ ] `EngineComponent.fetch_conversation_context()` includes announcements
- [ ] `DSPyEngine` passes `agent` to `fetch_conversation_context()`

## Tests
- [ ] All Phase 6 tests written and passing
- [ ] Integration tests cover full workflow
- [ ] Existing tests still pass (no regressions)
- [ ] Test coverage includes: string/model, metrics, scheduling, persistence, opt-out, expiration, visibility

## Documentation
- [ ] Example `examples/02-the-blackboard/02_announcements.py` created
- [ ] AGENTS.md updated with announcements section
- [ ] Pattern guide includes announcements pattern
- [ ] API reference documents new methods
- [ ] Docstrings include warnings about context usage

## Version
- [ ] Backend version bumped in `pyproject.toml`
- [ ] Frontend version bumped if needed
- [ ] Commit message follows convention: `feat: add system announcements`

## Run Final Validation
```bash
# 1. All tests pass
uv run pytest tests/ -v

# 2. Example runs
uv run python examples/02-the-blackboard/02_announcements.py

# 3. Linting passes
poe lint

# 4. Type checking passes
poe type-check

# 5. No uncommitted changes
git status
```

---

# 📤 Creating the Pull Request

## PR Title
```
feat: Add system announcements for runtime steering
```

## PR Description Template

```markdown
## Summary
Implements system announcements - a mechanism for broadcasting steering guidance that appears in agent context but doesn't trigger subscriptions.

Closes #XXX (if there's an issue)

## Changes
- ✨ New `SystemAnnouncement` model with expiration, topics, and levels
- ✨ `Flock.post_announcement()` API for publishing announcements
- ✨ `Agent.ignore_announcements()` builder method for opt-out
- 🔧 Modified `EngineComponent.fetch_conversation_context()` to include announcements
- 🛡️ Scheduler guard prevents announcements from triggering agents
- 📝 Comprehensive documentation in AGENTS.md and pattern guides
- ✅ 12+ new tests covering all features

## Testing
```bash
# Run announcement-specific tests
uv run pytest tests/ -v -k announcement

# Run example
uv run python examples/02-the-blackboard/02_announcements.py
```

## Breaking Changes
⚠️ **Signature change:** `EngineComponent.fetch_conversation_context()` now accepts `agent` parameter as second argument. Existing calls need update:

```python
# Old
context = await engine.fetch_conversation_context(ctx, correlation_id)

# New
context = await engine.fetch_conversation_context(ctx, agent, correlation_id)
# Or pass None if agent not available
context = await engine.fetch_conversation_context(ctx, None, correlation_id)
```

## Checklist
- [x] Tests pass locally
- [x] Documentation updated
- [x] Example code added
- [x] Version bumped
- [x] Pre-commit hooks pass
- [x] No merge conflicts with `0.5.0b` branch

## Screenshots (if applicable)
_Add dashboard screenshots showing announcement badge/UI if implemented_
```

## Target Branch
```bash
# ⚠️ CRITICAL: Target 0.5.0b, NOT main!
gh pr create --base 0.5.0b --title "feat: Add system announcements" --body "..."
```

---

# 🆘 Troubleshooting Guide

## Common Issues

### Issue: Tests fail with "missing 1 required positional argument: 'agent'"
**Cause:** Old test calls don't pass `agent` to `fetch_conversation_context()`

**Fix:**
```python
# Find failing test
# Change from:
context = await engine.fetch_conversation_context(ctx, correlation_id)

# To:
context = await engine.fetch_conversation_context(ctx, None, correlation_id)
```

---

### Issue: Import error "cannot import name SystemAnnouncement"
**Cause:** Type not exported from main package

**Fix:** Verify `src/flock/__init__.py` includes:
```python
from flock.system_artifacts import SystemAnnouncement, ANNOUNCEMENT_TAG

__all__ = [
    # ... existing ...
    "SystemAnnouncement",
    "ANNOUNCEMENT_TAG",
]
```

---

### Issue: Announcements appearing twice in context
**Cause:** Announcement tag not filtered correctly in `fetch_conversation_context()`

**Fix:** Ensure ANNOUNCEMENT_TAG is imported at top of method:
```python
from flock.system_artifacts import ANNOUNCEMENT_TAG
```

---

### Issue: Expired announcements still showing
**Cause:** Expiration parsing failing in `_fetch_announcements()`

**Fix:** Check datetime parsing logic (line in `_fetch_announcements`):
```python
exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
```

---

## Getting Help

**If stuck:**
1. Re-read the relevant background docs (listed at top of plan)
2. Check existing similar code (e.g., how `publish()` works)
3. Run tests in isolation: `uv run pytest tests/test_file.py::test_name -v`
4. Check tracing docs if debugging context issues: `docs/UNIFIED_TRACING.md`

**Ask for help with:**
- Exact error message
- Test output
- What you've tried
- Which task you're on

---

# 📚 Reference Links

- **Spec:** [`my_amazing_steering_implementation.md`](./my_amazing_steering_implementation.md)
- **Architecture Guide:** [AGENTS.md](../../AGENTS.md)
- **Contributing:** [CONTRIBUTING.md](../../CONTRIBUTING.md)
- **Tracing:** [docs/UNIFIED_TRACING.md](../UNIFIED_TRACING.md)
- **Store Implementation:** [src/flock/store.py](../../src/flock/store.py)

---

**Good luck! This feature will be awesome. 🚀**
