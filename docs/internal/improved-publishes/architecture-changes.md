# Architecture Changes: Multiple `.publishes()` = Multiple Engine Calls

**Making `.publishes()` symmetric with `.consumes()` for better DX**

**Date**: 2025-10-15
**Status**: Proposed Design
**Priority**: HIGH - Fixes fundamental DX confusion

---

## 🎯 The Problem

### Current Behavior (Confusing!)

```python
# Multiple .consumes() = OR logic (works great!)
agent.consumes(A).consumes(B).consumes(C)
# Agent reacts to A OR B OR C ✅

# Multiple .publishes() = ??? (confusing!)
agent.publishes(A).publishes(A).publishes(A)
# What happens? Engine called once → 3 duplicate artifacts ❌
```

**DX Issue**: Asymmetry! Users expect symmetry between `.consumes()` and `.publishes()`.

### Why This Caused V1 Mistakes

From `v1_mistakes_and_fixes.md`:

```python
# V1 Mistake: Multiple types in one .publishes()
specify_orchestrator = (
    flock.agent("specify_orchestrator")
    .publishes(
        SpecificationMetadata,    # ❌ TOO MANY!
        ResearchTask,
        PRDSection,
        # ... 7 types total!
    )
)
```

**Why this happened**: I (Claude) didn't understand the architecture. If `.publishes()` worked like `.consumes()`, this would have been fine!

---

## ✅ The Solution: Multiple Publish Groups

### Desired Behavior

```python
# Single .publishes() call = ONE engine call
.publishes(A, B, C)
# Engine called once: "Generate A, B, and C"
# Result: 1 of each type

# Multiple .publishes() calls = MULTIPLE engine calls
.publishes(A).publishes(A).publishes(A)
# Engine called THREE times: "Generate A" (each time)
# Result: 3 independent A's (might differ!)

# Mixed: fan_out within a single call
.publishes(A, A, A)  # or .publishes(A, fan_out=3)
# Engine called ONCE: "Generate 3 A's"
# Result: 3 related A's (LLM sees them together)
```

**Perfect symmetry with `.consumes()`!** ✨

---

## 🏗️ Architecture Changes

### Change 1: Track Publish Groups

**Current**:
```python
class Agent:
    outputs: list[AgentOutput] = []  # Flat list
```

**New**:
```python
class Agent:
    output_groups: list[list[AgentOutput]] = []  # Groups!

    # Each .publishes() call creates ONE group
    # Each group = one engine call
```

### Change 2: Track Call Semantics

```python
@dataclass
class OutputGroup:
    """Represents one .publishes() call."""
    outputs: list[AgentOutput]  # Types to generate
    shared_visibility: Visibility  # Default visibility

    def is_single_call(self) -> bool:
        """True if this is one engine call generating multiple artifacts."""
        return True  # All outputs in group generated together
```

### Change 3: Multiple Engine Calls in `Agent.execute()`

**Current** (agent.py:92-112):
```python
async def execute(self, ctx, artifacts):
    # ...
    result = await self._run_engines(ctx, eval_inputs)  # ← Called ONCE
    outputs = await self._make_outputs(ctx, result)
    # ...
```

**New**:
```python
async def execute(self, ctx, artifacts):
    # ...
    all_outputs = []

    # Call engine ONCE PER PUBLISH GROUP
    for group_idx, output_group in enumerate(self.output_groups):
        # Prepare context for this group
        group_ctx = self._prepare_group_context(ctx, group_idx, output_group)

        # Run engines for THIS group
        result = await self._run_engines(group_ctx, eval_inputs)

        # Extract outputs for THIS group only
        group_outputs = await self._make_outputs_for_group(
            group_ctx, result, output_group
        )

        all_outputs.extend(group_outputs)

    await self._run_post_publish(ctx, all_outputs)
    # ...
    return all_outputs
```

### Change 4: Update `AgentBuilder.publishes()`

**Current** (agent.py:646-699):
```python
def publishes(self, *types, visibility=None):
    outputs = []
    for model in types:
        spec = ArtifactSpec.from_model(model)
        output = AgentOutput(spec=spec, ...)
        self._agent.outputs.append(output)  # ← Flat append
        outputs.append(output)
    return PublishBuilder(self, outputs)
```

**New**:
```python
def publishes(self, *types, visibility=None, fan_out=None):
    outputs = []

    # Handle fan_out (duplicate types)
    if fan_out is not None:
        # Single call, generate N of each type
        from collections import Counter
        for type_ in set(types):  # Unique types
            for _ in range(fan_out):
                spec = ArtifactSpec.from_model(type_)
                output = AgentOutput(spec=spec, default_visibility=...)
                outputs.append(output)
    else:
        # Count duplicates
        from collections import Counter
        type_counts = Counter(types)
        for type_, count in type_counts.items():
            for _ in range(count):
                spec = ArtifactSpec.from_model(type_)
                output = AgentOutput(spec=spec, default_visibility=...)
                outputs.append(output)

    # Create a NEW group for this .publishes() call
    output_group = OutputGroup(
        outputs=outputs,
        shared_visibility=ensure_visibility(visibility)
    )
    self._agent.output_groups.append(output_group)  # ← Group append!

    return PublishBuilder(self, outputs)
```

### Change 5: System Prompt Per Group

```python
def _prepare_group_context(self, ctx, group_idx, output_group):
    """Prepare context for specific publish group."""
    # Clone context
    group_ctx = ctx.clone()

    # Add group-specific instructions to system prompt
    group_ctx.group_outputs = output_group.outputs
    group_ctx.group_description = self._build_group_prompt(output_group)

    return group_ctx

def _build_group_prompt(self, output_group):
    """Build system prompt for this output group."""
    prompt = f"You must generate the following artifacts:\n\n"

    for output in output_group.outputs:
        count = output_group.outputs.count(output)
        if count > 1:
            prompt += f"- {count}x {output.spec.type_name}\n"
        else:
            prompt += f"- {output.spec.type_name}\n"

    if len(output_group.outputs) > 1:
        prompt += "\nUse EvalResult.from_objects() to return all artifacts together.\n"

    return prompt
```

---

## 📊 Comparison: Before vs After

### Example: 3 Independent Tasks

**Before** (doesn't work correctly):
```python
.publishes(Task).publishes(Task).publishes(Task)

# What happened:
# 1. Created 3 AgentOutput objects (all Task)
# 2. Engine called ONCE
# 3. LLM generates 1 Task
# 4. _make_outputs finds same Task 3 times
# Result: 3 DUPLICATE artifacts ❌
```

**After** (works correctly):
```python
.publishes(Task).publishes(Task).publishes(Task)

# What happens:
# 1. Creates 3 output groups (1 Task each)
# 2. Engine called 3 TIMES
#    - Call 1: "Generate Task" → Task A
#    - Call 2: "Generate Task" → Task B
#    - Call 3: "Generate Task" → Task C
# 3. _make_outputs for each call
# Result: 3 INDEPENDENT artifacts ✅
```

### Example: 3 Related Tasks

**Before** (required fan_out):
```python
.publishes(Task, fan_out=3)

# What happened:
# 1. Created 1 AgentOutput with count=3
# 2. Engine called ONCE: "Generate 3 tasks"
# 3. LLM generates 3 Tasks (sees them together)
# Result: 3 RELATED artifacts ✅
```

**After** (same behavior, multiple syntax options):
```python
# Option 1: Sugar syntax (same as before)
.publishes(Task, fan_out=3)

# Option 2: Explicit duplicates (NEW!)
.publishes(Task, Task, Task)

# Both → ONE engine call: "Generate 3 tasks"
# Result: 3 RELATED artifacts ✅
```

---

## 🎨 Use Cases Enabled

### Use Case 1: Redundancy / Voting

```python
# Call LLM 3 times for same task, pick best result
solution_generator = (
    flock.agent("solution_generator")
    .consumes(Problem)
    .publishes(Solution)  # Call 1
    .publishes(Solution)  # Call 2
    .publishes(Solution)  # Call 3
)

# 3 independent LLM calls, 3 different solutions!
# Then: voter agent picks best one
```

### Use Case 2: Batch + Individual

```python
# Generate 5 ideas in one call, THEN generate summary separately
idea_generator = (
    flock.agent("idea_generator")
    .consumes(Prompt)
    .publishes(Idea, fan_out=5)  # Call 1: Generate 5 related ideas
    .publishes(IdeaSummary)      # Call 2: Summarize the ideas
)

# Call 1: LLM generates 5 ideas (knows about all of them)
# Call 2: LLM generates summary (separate call, fresh context)
```

### Use Case 3: Phased Generation

```python
# Generate draft, then refined version
content_creator = (
    flock.agent("content_creator")
    .consumes(ContentRequest)
    .publishes(DraftContent)    # Call 1: Quick draft
    .publishes(RefinedContent)  # Call 2: Polished version
)

# Two separate calls, different quality levels
```

### Use Case 4: Multiple Attempts with Fallback

```python
# Try complex solution, if fails try simple solution
solver = (
    flock.agent("solver")
    .consumes(Problem)
    .publishes(ComplexSolution)  # Call 1: Try advanced approach
    .publishes(SimpleSolution)   # Call 2: Fallback approach
)

# Downstream agents: consume either one
```

---

## 🔄 Backwards Compatibility

### Existing Code (Unchanged)

```python
# Single .publishes() with multiple types
.publishes(A, B, C)

# Before: 1 group, 1 call ✅
# After:  1 group, 1 call ✅
# No change!
```

### Migration Path

**Old pattern** (V1 mistake):
```python
# V1: Everything in one .publishes()
orchestrator.publishes(
    SpecMetadata,
    ResearchTask,
    PRDSection,
    SDDSection,
)
# Generates all 4 in ONE call (might fail, too much!)
```

**New pattern** (V2 correct):
```python
# V2: Separate agents
spec_init.publishes(SpecMetadata)
task_gen.publishes(ResearchTask, fan_out=4)
prd_writer.publishes(PRDSection)
sdd_writer.publishes(SDDSection)

# OR: Multiple calls in one agent
orchestrator.publishes(SpecMetadata)  # Call 1
orchestrator.publishes(ResearchTask)  # Call 2
orchestrator.publishes(PRDSection)    # Call 3
# Each call independent!
```

---

## ⚙️ Implementation Checklist

### Phase 1: Core Changes (Week 1)

- [ ] Add `OutputGroup` dataclass
- [ ] Change `Agent.outputs` → `Agent.output_groups: list[OutputGroup]`
- [ ] Update `AgentBuilder.publishes()` to create groups
- [ ] Modify `Agent.execute()` to loop over groups
- [ ] Update `_run_engines()` to accept group context
- [ ] Implement `_make_outputs_for_group()`

### Phase 2: Prompt Engineering (Week 1)

- [ ] Add group-specific system prompts
- [ ] Guide LLM to generate correct count per group
- [ ] Test with simple examples

### Phase 3: Advanced Features (Week 2)

- [ ] Add `fan_out=` parameter
- [ ] Support duplicate counting (`.publishes(A, A, A)`)
- [ ] Add visibility controls per group
- [ ] Add validation per group

### Phase 4: Testing (Week 2)

- [ ] Unit tests for group creation
- [ ] Integration tests for multiple calls
- [ ] Test backwards compatibility
- [ ] Test with spec-driven V2

---

## 🧪 Testing Strategy

### Test 1: Multiple Independent Calls

```python
def test_multiple_publishes_multiple_calls():
    """Test that multiple .publishes() = multiple engine calls."""

    call_count = 0

    # Mock engine that counts calls
    class CountingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            nonlocal call_count
            call_count += 1
            return EvalResult.from_object(Task(id=f"task-{call_count}"), agent=agent)

    agent = (
        flock.agent("test")
        .consumes(Request)
        .publishes(Task)  # Call 1
        .publishes(Task)  # Call 2
        .publishes(Task)  # Call 3
        .with_engines(CountingEngine())
    )

    await flock.publish(Request())
    await flock.run_until_idle()

    assert call_count == 3  # Engine called 3 times!

    tasks = await flock.store.get_by_type(Task)
    assert len(tasks) == 3
    assert tasks[0].id == "task-1"
    assert tasks[1].id == "task-2"
    assert tasks[2].id == "task-3"
```

### Test 2: Single Call with Multiple Types

```python
def test_single_publishes_single_call():
    """Test that single .publishes() = single engine call."""

    call_count = 0

    class CountingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            nonlocal call_count
            call_count += 1
            return EvalResult.from_objects(
                TaskA(id="a"),
                TaskB(id="b"),
                TaskC(id="c"),
                agent=agent
            )

    agent = (
        flock.agent("test")
        .consumes(Request)
        .publishes(TaskA, TaskB, TaskC)  # ONE call, 3 types
        .with_engines(CountingEngine())
    )

    await flock.publish(Request())
    await flock.run_until_idle()

    assert call_count == 1  # Engine called ONCE!

    assert len(await flock.store.get_by_type(TaskA)) == 1
    assert len(await flock.store.get_by_type(TaskB)) == 1
    assert len(await flock.store.get_by_type(TaskC)) == 1
```

### Test 3: Fan-Out in Single Call

```python
def test_fanout_single_call():
    """Test that fan_out in single .publishes() = single call."""

    call_count = 0

    agent = (
        flock.agent("test")
        .consumes(Request)
        .publishes(Task, fan_out=3)  # ONE call, 3 of same type
    )

    # ... assert call_count == 1, len(tasks) == 3
```

---

## 🎯 Performance Considerations

### Cost Implications

```python
# Multiple calls = higher cost
.publishes(Task).publishes(Task).publishes(Task)
# 3 LLM API calls = 3x cost

# Single call = lower cost
.publishes(Task, fan_out=3)
# 1 LLM API call (but generates 3 artifacts)
```

**Recommendation**: Document cost tradeoffs clearly in examples.

### Parallelization

**Option**: Run multiple publish groups in parallel?

```python
# Sequential (default)
for group in output_groups:
    result = await self._run_engines(ctx, group)

# Parallel (advanced)
async with asyncio.TaskGroup() as tg:
    tasks = [
        tg.create_task(self._run_engines(ctx, group))
        for group in output_groups
    ]
# Faster but uses more resources
```

**Recommendation**: Start sequential, add `parallel=True` option later if needed.

---

## 🎓 Documentation Updates

### Update AGENTS.md

Add section:

```markdown
## Multiple Publish Calls

When you call `.publishes()` multiple times, each call triggers a **separate engine execution**:

```python
# Three independent generations
agent.publishes(Task).publishes(Task).publishes(Task)
# Engine called 3 times, might generate different results

# One generation with multiple artifacts
agent.publishes(Task, Task, Task)  # or .publishes(Task, fan_out=3)
# Engine called once, generates 3 related tasks
```

**Use Cases**:
- **Multiple calls**: Redundancy, voting, independent attempts
- **Single call with duplicates**: Related items, batch generation, diversity
```

### Update Examples

Create `examples/showcase/08_multiple_publish_calls.py`:

```python
# Example 1: Voting pattern
solution_generator = (
    flock.agent("solution_generator")
    .publishes(Solution)  # Attempt 1
    .publishes(Solution)  # Attempt 2
    .publishes(Solution)  # Attempt 3
)

voter = (
    flock.agent("voter")
    .consumes(Solution, join=JoinSpec(by=lambda s: s.problem_id))
    .publishes(BestSolution)
)

# Example 2: Batch generation
task_generator = (
    flock.agent("task_generator")
    .publishes(Task, fan_out=10)  # ONE call, 10 related tasks
)
```

---

## 💡 Key Design Decisions

### Decision 1: Groups = Call Boundaries

**Why**: Clean semantics - each `.publishes()` is one LLM "conversation"

**Alternative**: Share context across groups?
- **Rejected**: Too complex, unclear semantics

### Decision 2: Count via Duplicates

```python
.publishes(A, A, A)  # Count = 3 via duplicates
.publishes(A, fan_out=3)  # Sugar syntax
```

**Why**: Consistent with how it "looks" - three A's!

**Alternative**: `.publishes(A, count=3)`
- **Rejected**: Less intuitive than duplicates or `fan_out`

### Decision 3: Sequential Execution (Default)

**Why**: Predictable, easier to debug, context can flow

**Future**: Add `parallel=True` option if needed

---

## ✅ Why This Design Wins

### 1. Perfect Symmetry

```python
# Consuming
.consumes(A).consumes(B).consumes(C)  # OR logic

# Publishing (NEW!)
.publishes(A).publishes(B).publishes(C)  # Multiple calls

# Both accumulate, both make sense! ✅
```

### 2. Fixes V1 Confusion

My mistake in V1 would have been FINE with this design:

```python
# What I tried in V1
.publishes(SpecMetadata)
.publishes(ResearchTask)
.publishes(PRDSection)

# With new design: 3 engine calls, perfect! ✅
```

### 3. Enables New Patterns

- Voting / redundancy
- Phased generation
- Fallback strategies
- Independent attempts

### 4. Backwards Compatible

Single `.publishes(A, B, C)` still works exactly as before!

---

## 🚀 Recommendation

**IMPLEMENT THIS!** It fixes the fundamental DX issue and enables powerful patterns.

**Priority**: HIGH - This is more important than fan_out alone

**Effort**: ~2-3 days of coding + testing

**Impact**:
- ✅ Fixes V1 confusion
- ✅ Enables voting/redundancy patterns
- ✅ Makes API consistent
- ✅ No breaking changes

**Next Steps**:
1. Implement OutputGroup and group tracking
2. Modify Agent.execute() to loop over groups
3. Test with multiple calls
4. Update documentation
5. Ship it! 🚀

---

**This is the right architecture! Let's make it happen!** 🔥
