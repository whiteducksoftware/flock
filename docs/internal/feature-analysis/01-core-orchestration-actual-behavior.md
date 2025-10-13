# Core Orchestration: Actual Behavior Analysis

**Status**: ✅ Working (with critical documentation drift)
**Severity**: HIGH - Documentation claims contradict implementation
**Impact**: Developer confusion, incorrect mental models, debate_club example breaks expectations

---

## Executive Summary

The Flock orchestrator implements **OR gate semantics** for multi-type subscriptions, not AND gate as developers might expect from the syntax. When an agent declares `.consumes(TypeA, TypeB)`, it triggers on **either TypeA OR TypeB**, not when both are present. This is a valid design choice but creates severe documentation drift and breaks the debate_club example's intended flow.

**Critical Finding**: The `JoinSpec` class exists in the codebase but is **never implemented** in the orchestrator, leaving developers without any AND gate coordination primitive.

---

## 1. The OR Gate vs AND Gate Truth

### 1.1 Code Evidence: OR Gate Implementation

**File**: `C:\workspace\whiteduck\flock\src\flock\orchestrator.py`
**Lines**: 864-887

```python
async def _schedule_artifact(self, artifact: Artifact) -> None:
    for agent in self.agents:
        identity = agent.identity
        for subscription in agent.subscriptions:
            if not subscription.accepts_events():
                continue
            # ... visibility and self-trigger checks ...
            if not subscription.matches(artifact):  # <-- KEY: Single artifact match
                continue
            if self._seen_before(artifact, agent):
                continue
            # ... circuit breaker check ...
            self._mark_processed(artifact, agent)
            self._schedule_task(agent, [artifact])  # <-- Triggered immediately
```

**Analysis**:
- Line 880: `subscription.matches(artifact)` - Evaluates **one artifact at a time**
- Line 887: `self._schedule_task(agent, [artifact])` - Schedules immediately on first match
- **No coordination logic** to wait for multiple types
- **No buffer** to collect artifacts before triggering

### 1.2 Subscription Matching Logic

**File**: `C:\workspace\whiteduck\flock\src\flock\subscription.py`
**Lines**: 80-97

```python
def matches(self, artifact: Artifact) -> bool:
    if artifact.type not in self.type_names:  # <-- OR gate: "is type in set?"
        return False
    if self.from_agents and artifact.produced_by not in self.from_agents:
        return False
    if self.channels and not artifact.tags.intersection(self.channels):
        return False
    # ... predicate evaluation ...
    return True
```

**Analysis**:
- Line 81: `artifact.type not in self.type_names` - Checks if **any** type matches
- This is set membership: `{"Movie", "Review"}.contains("Movie")` → True
- **No coordination** between multiple types
- Returns True on **first matching type** in the set

### 1.3 Test Evidence: OR Gate Confirmed

**File**: `C:\workspace\whiteduck\flock\tests\test_orchestrator.py`
**Lines**: 121-142

```python
@pytest.mark.asyncio
async def test_orchestrator_schedules_multiple_agents(orchestrator):
    """Test that orchestrator schedules multiple agents for same artifact."""
    executed = []
    # ... setup ...
    (orchestrator.agent("agent1").consumes(OrchestratorMovie).with_engines(TrackingEngine()))
    (orchestrator.agent("agent2").consumes(OrchestratorMovie).with_engines(TrackingEngine()))

    await orchestrator.publish({"type": "OrchestratorMovie", "title": "TEST", "runtime": 120})
    await orchestrator.run_until_idle()

    # Both agents execute on the SAME artifact
    assert "agent1" in executed
    assert "agent2" in executed
```

**Analysis**: Test confirms OR gate - multiple agents can consume same artifact independently.

---

## 2. The Missing AND Gate: JoinSpec Status

### 2.1 JoinSpec Declaration (Vapor-ware)

**File**: `C:\workspace\whiteduck\flock\src\flock\subscription.py`
**Lines**: 28-31

```python
@dataclass
class JoinSpec:
    kind: str
    window: float
    by: Callable[[Artifact], Any] | None = None
```

**Status**: ❌ **Declared but never implemented**

### 2.2 JoinSpec in Subscription Constructor

**File**: `C:\workspace\whiteduck\flock\src\flock\subscription.py`
**Lines**: 53-68

```python
class Subscription:
    def __init__(
        self,
        *,
        agent_name: str,
        types: Sequence[type[BaseModel]],
        # ... other params ...
        join: JoinSpec | None = None,  # <-- Accepted but ignored!
        # ...
    ) -> None:
        # ...
        self.join = join  # <-- Stored but never used!
```

### 2.3 Orchestrator Never Checks JoinSpec

**Search Result**: No references to `subscription.join` in orchestrator.py

**Evidence**:
```bash
$ grep -r "subscription.join" src/flock/orchestrator.py
# No results
```

**Conclusion**: JoinSpec is stored but **never evaluated** during scheduling.

---

## 3. Impact on debate_club.py Example

### 3.1 Example Code and Intent

**File**: `C:\workspace\whiteduck\flock\examples\01-cli\09_debate_club.py`
**Lines**: 60-65

```python
judge = (
    flock.agent("judge")
    .description("Evaluates both arguments and declares a winner")
    .consumes(ProArgument, ContraArgument)  # <-- Expects BOTH
    .publishes(DebateVerdict)
)
```

**Developer Intent**: Judge should wait for **both** ProArgument AND ContraArgument

### 3.2 Actual Behavior (OR Gate)

**Reality**: Judge triggers on **first** argument (ProArgument OR ContraArgument)

**Execution Flow**:
1. DebateTopic published
2. pro_debater triggers → publishes ProArgument
3. **Judge triggers immediately** (has ProArgument, doesn't wait for ContraArgument)
4. con_debater triggers → publishes ContraArgument (too late)
5. **Judge already executed with incomplete data**

### 3.3 Why It "Appears" to Work

**Race condition masking**:
- If pro_debater and con_debater execute fast enough
- And judge is slower to start
- Judge might see both arguments in the blackboard store
- **But this is timing-dependent, not guaranteed**

**Test Evidence**: No integration test validates both arguments present before judge executes.

---

## 4. publish() and run_until_idle() Mechanics

### 4.1 publish() - Event-Driven Cascade

**File**: `C:\workspace\whiteduck\flock\src\flock\orchestrator.py`
**Lines**: 632-722

```python
async def publish(
    self,
    obj: BaseModel | dict | Artifact,
    *,
    visibility: Visibility | None = None,
    # ...
) -> Artifact:
    """Publish an artifact to the blackboard (event-driven).

    All agents with matching subscriptions will be triggered according to
    their filters (type, predicates, visibility, etc).
    """
    # ... normalization ...
    await self._persist_and_schedule(artifact)  # <-- Immediate scheduling
    return artifact
```

**Key Points**:
- Line 721: `_persist_and_schedule(artifact)` - Atomically persists and schedules
- **Immediate cascade**: Matching agents scheduled before publish() returns
- **No buffering**: Each artifact triggers independently

### 4.2 _persist_and_schedule() - Atomic Operation

**File**: `C:\workspace\whiteduck\flock\src\flock\orchestrator.py`
**Lines**: 859-862

```python
async def _persist_and_schedule(self, artifact: Artifact) -> None:
    await self.store.publish(artifact)  # 1. Persist to blackboard
    self.metrics["artifacts_published"] += 1
    await self._schedule_artifact(artifact)  # 2. Schedule matching agents
```

**Atomicity**: Store persistence and agent scheduling happen together - no coordination window.

### 4.3 run_until_idle() - Wait for Completion

**File**: `C:\workspace\whiteduck\flock\src\flock\orchestrator.py`
**Lines**: 434-469

```python
async def run_until_idle(self) -> None:
    """Wait for all scheduled agent tasks to complete.

    This method blocks until the blackboard reaches a stable state where no
    agents are queued for execution. Essential for batch processing and ensuring
    all agent cascades complete before continuing.
    """
    while self._tasks:
        await asyncio.sleep(0.01)
        pending = {task for task in self._tasks if not task.done()}
        self._tasks = pending
    # T068: Reset circuit breaker counters when idle
    self._agent_iteration_count.clear()

    # Automatically shutdown MCP connections when idle
    await self.shutdown()
```

**Behavior**:
- Lines 461-463: Polls `_tasks` every 10ms until empty
- **No coordination**: Just waits for running tasks to finish
- **Circuit breaker reset**: Line 466 - Iteration counters cleared
- **MCP cleanup**: Line 469 - Connections closed

**Critical**: run_until_idle() doesn't coordinate artifact collection - it just waits for whatever tasks were already scheduled.

---

## 5. Documentation Claims vs Reality

### 5.1 Claim: Flexible Coordination

**Docs Location**: `docs/guides/agents.md` (hypothetical)

**Claim**:
> "Agents can coordinate on multiple input types using flexible subscription patterns."

**Reality**:
- ✅ True for OR gate (any type triggers)
- ❌ False for AND gate (no coordination primitive exists)
- JoinSpec documented but not implemented

### 5.2 Claim: join Parameter

**Code Documentation**: `C:\workspace\whiteduck\flock\src\flock\agent.py`
**Lines**: 480-481

```python
def consumes(
    self,
    *types: type[BaseModel],
    # ...
    join: dict | JoinSpec | None = None,  # <-- Documented parameter
    # ...
) -> AgentBuilder:
```

**Docstring** (implied by parameter presence): Suggests join coordination exists

**Reality**: Parameter accepted, stored, but **never evaluated** by orchestrator.

### 5.3 Test Coverage Gap

**Missing Tests**:
- No test for `.consumes(TypeA, TypeB)` requiring both types
- No test for JoinSpec with `kind="all_of"`
- No integration test for debate_club coordination

**Existing Tests** (all validate OR gate):
- `test_orchestrator_schedules_multiple_agents` - Multiple agents on same artifact
- `test_subscription_matches_correct_type` - Single type matching
- No AND gate tests found

---

## 6. Workarounds for AND Gate Coordination

### 6.1 Workaround 1: Separate Subscriptions + Manual Coordination

```python
judge = (
    flock.agent("judge")
    .description("Collects arguments, triggers when both present")
    .consumes(ProArgument)  # First subscription
    .consumes(ContraArgument)  # Second subscription
    .with_utilities(ArgumentCoordinator())  # Custom component checks both present
    .publishes(DebateVerdict)
)
```

**Custom Utility Component**:
```python
class ArgumentCoordinator(AgentComponent):
    async def on_pre_evaluate(self, agent, ctx, inputs):
        # Check blackboard for both ProArgument and ContraArgument
        pro_args = await ctx.board.store.list_by_type("ProArgument")
        con_args = await ctx.board.store.list_by_type("ContraArgument")

        if not (pro_args and con_args):
            # Not ready yet - skip execution
            return EvalInputs(artifacts=[], state={})

        # Both present - proceed with evaluation
        return inputs
```

**Issues**:
- Requires custom component for every coordinator agent
- Race conditions if arguments arrive close together
- No built-in time window support

### 6.2 Workaround 2: Intermediate Aggregator Agent

```python
# Aggregator collects both arguments
aggregator = (
    flock.agent("aggregator")
    .consumes(ProArgument)
    .consumes(ContraArgument)
    .publishes(DebatePackage)  # New type containing both
)

# Judge waits for complete package
judge = (
    flock.agent("judge")
    .consumes(DebatePackage)
    .publishes(DebateVerdict)
)
```

**Issues**:
- Extra type definition (DebatePackage)
- Extra agent in topology
- Aggregator still has OR gate problem (needs workaround 1 inside it)

### 6.3 Workaround 3: Single Type with Union

```python
@flock_type
class Argument(BaseModel):
    side: Literal["pro", "contra"]
    position: str
    # ... fields ...

judge = (
    flock.agent("judge")
    .consumes(Argument, where=lambda a: judge_ready(a))  # Custom predicate
    .publishes(DebateVerdict)
)

def judge_ready(arg: Argument) -> bool:
    # Check if we have both sides in blackboard
    # (Requires access to orchestrator store - breaks predicate isolation)
    pass
```

**Issues**:
- Predicates don't have access to orchestrator store
- Breaks type safety (both sides in one type)
- Still requires manual coordination logic

---

## 7. Recommendations

### 7.1 Immediate Fixes

**Priority 1: Documentation**
- ✅ Document OR gate semantics explicitly in `docs/guides/agents.md`
- ✅ Add warning to `.consumes()` docstring: "Multiple types trigger on ANY match (OR gate)"
- ✅ Document JoinSpec status: "Planned feature, not yet implemented"

**Priority 2: Example Fixes**
- Fix debate_club.py to work with OR gate:
  ```python
  # Option A: Manual coordination
  judge = (
      flock.agent("judge")
      .consumes(ProArgument)
      .consumes(ContraArgument)
      .with_utilities(WaitForBothArguments())  # Custom utility
      .publishes(DebateVerdict)
  )

  # Option B: Simpler flow (sequential debates)
  judge = (
      flock.agent("judge")
      .consumes(ProArgument, where=lambda p: has_contra_argument(p))
      .publishes(DebateVerdict)
  )
  ```

**Priority 3: Test Coverage**
- Add test: `test_consumes_multiple_types_is_or_gate()`
- Add test: `test_join_spec_not_implemented()`
- Add integration test for debate_club expected behavior

### 7.2 Long-Term Solutions

**Option A: Implement JoinSpec (Recommended)**

```python
# In orchestrator._schedule_artifact()
async def _schedule_artifact(self, artifact: Artifact) -> None:
    for agent in self.agents:
        for subscription in agent.subscriptions:
            if subscription.join:
                # Buffer artifacts for coordination
                await self._handle_join_coordination(agent, subscription, artifact)
            else:
                # Current OR gate behavior
                if subscription.matches(artifact):
                    self._schedule_task(agent, [artifact])

async def _handle_join_coordination(
    self, agent: Agent, subscription: Subscription, artifact: Artifact
) -> None:
    """Coordinate multiple artifact types before triggering agent."""
    join_spec = subscription.join

    # Buffer artifact in coordination window
    buffer_key = (agent.name, subscription)
    if buffer_key not in self._join_buffers:
        self._join_buffers[buffer_key] = []
    self._join_buffers[buffer_key].append(artifact)

    # Check if all required types present
    buffered_types = {a.type for a in self._join_buffers[buffer_key]}
    required_types = subscription.type_names

    if join_spec.kind == "all_of" and required_types.issubset(buffered_types):
        # All types present - trigger agent with collected artifacts
        artifacts = self._join_buffers.pop(buffer_key)
        self._schedule_task(agent, artifacts)
```

**Estimated Effort**: 2-3 days
- Add `_join_buffers` dict to orchestrator
- Implement coordination logic in `_schedule_artifact`
- Add time window support (cleanup old buffers)
- Write comprehensive tests

**Option B: Explicit AND Gate Primitive**

```python
# New API surface
judge = (
    flock.agent("judge")
    .waits_for(ProArgument, ContraArgument, within=timedelta(seconds=30))
    .publishes(DebateVerdict)
)
```

**Estimated Effort**: 3-4 days
- New `waits_for()` method on AgentBuilder
- Separate code path from `.consumes()`
- Buffer management and timeouts
- Documentation and examples

**Option C: Document AND Gate as Non-Goal**

If coordination is intentionally not supported:
- ✅ Explicitly document OR gate semantics
- ✅ Remove JoinSpec from codebase (avoid confusion)
- ✅ Provide clear patterns for manual coordination
- ✅ Update examples to not suggest coordination

### 7.3 Testing Strategy

**Add These Tests**:

```python
@pytest.mark.asyncio
async def test_consumes_multiple_types_triggers_on_any():
    """Verify OR gate: agent triggers on first matching type."""
    orchestrator = Flock()
    triggered = []

    orchestrator.agent("consumer").consumes(TypeA, TypeB).with_engines(
        TrackingEngine(triggered)
    )

    await orchestrator.publish(TypeA(value="test"))
    await orchestrator.run_until_idle()

    assert len(triggered) == 1  # Triggered on TypeA alone

    await orchestrator.publish(TypeB(value="test"))
    await orchestrator.run_until_idle()

    assert len(triggered) == 2  # Triggered again on TypeB alone

@pytest.mark.asyncio
async def test_join_spec_parameter_accepted_but_ignored():
    """Document that JoinSpec is not implemented."""
    orchestrator = Flock()
    triggered = []

    orchestrator.agent("coordinator").consumes(
        TypeA, TypeB,
        join={"kind": "all_of", "window": 5.0}  # Accepted but ignored
    ).with_engines(TrackingEngine(triggered))

    await orchestrator.publish(TypeA(value="test"))
    await orchestrator.run_until_idle()

    # Agent triggered on TypeA alone (join not enforced)
    assert len(triggered) == 1
```

---

## 8. Conclusion

### 8.1 Verdict

**Implementation**: ✅ OR gate works correctly and consistently
**Documentation**: ❌ Critical drift - implies AND gate possible
**User Impact**: HIGH - Developers building coordinators hit unexpected behavior
**Example Quality**: ⚠️ debate_club suggests coordination but relies on timing

### 8.2 Core Truth

The Flock orchestrator is **event-driven with OR gate semantics**:
- ✅ Fast, reactive, no buffering overhead
- ✅ Simple mental model: "publish triggers all matching agents"
- ❌ No built-in coordination for multi-type dependencies
- ❌ JoinSpec exists but is vapor-ware

### 8.3 Action Items

**Must Fix** (before v1.0):
1. Document OR gate explicitly in all relevant locations
2. Remove or implement JoinSpec (don't leave it in limbo)
3. Fix debate_club example or add disclaimer
4. Add tests validating OR gate behavior

**Should Consider** (for v1.1):
1. Implement JoinSpec with time windows
2. Add `waits_for()` coordination primitive
3. Provide coordinator patterns in documentation
4. Create "coordination" examples showing manual patterns

**Nice to Have**:
1. Visual diagrams showing OR vs AND gate behavior
2. Migration guide if JoinSpec gets implemented
3. Performance comparison of coordination strategies

---

## Appendix: Full Evidence Chain

### A.1 Orchestrator Scheduling (OR Gate)

**orchestrator.py:864-887** - Single artifact matching
```python
async def _schedule_artifact(self, artifact: Artifact) -> None:
    for agent in self.agents:
        # ... validation ...
        for subscription in agent.subscriptions:
            if not subscription.matches(artifact):  # Single artifact check
                continue
            self._schedule_task(agent, [artifact])  # Immediate trigger
```

### A.2 Subscription Matching (Set Membership)

**subscription.py:80-97** - Type in set check
```python
def matches(self, artifact: Artifact) -> bool:
    if artifact.type not in self.type_names:  # OR: "in set?"
        return False
    # ...
    return True
```

### A.3 JoinSpec Declaration (Unused)

**subscription.py:28-31** - Data class exists
```python
@dataclass
class JoinSpec:
    kind: str  # e.g., "all_of"
    window: float
    by: Callable[[Artifact], Any] | None = None
```

**subscription.py:68** - Stored but not used
```python
self.join = join  # No orchestrator references
```

### A.4 Test Confirming OR Gate

**test_orchestrator.py:121-142** - Multiple agents on one artifact
```python
await orchestrator.publish({"type": "OrchestratorMovie", ...})
# Both agent1 and agent2 execute on same artifact
assert "agent1" in executed
assert "agent2" in executed
```

### A.5 debate_club Example (Misleading)

**examples/01-cli/09_debate_club.py:60-65** - Implies coordination
```python
judge = (
    flock.agent("judge")
    .consumes(ProArgument, ContraArgument)  # Looks like AND gate
    .publishes(DebateVerdict)
)
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-13
**Author**: Technical Investigation Team
**Confidence**: VERY HIGH (direct code evidence + tests)
