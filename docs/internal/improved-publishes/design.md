# Improved `.publishes()` Design: Multi-Artifact Publishing

**Declarative fan-out through builder pattern syntax**

**Date**: 2025-10-15
**Status**: Proposed Design
**Replaces**: FanOutComponent approach

---

## 🎯 Executive Summary

This design proposes extending `.publishes()` to support multiple artifact publishing through **declarative builder syntax**, eliminating the need for FanOutComponent while maintaining symmetry with the existing `.consumes()` API.

**Core Innovation**: Use the same multiple-argument pattern that `.consumes()` already supports:

```python
# Symmetric API design
.consumes(A, B, C)      # ✅ Already works!
.publishes(A, B, C)     # ✅ NEW - publish 3 different types

.publishes(A, A, A)     # ✅ NEW - publish 3 of same type
.publishes(A, fan_out=3)  # ✅ Sugar syntax for above
```

**Key Benefits**:
- ✅ **Symmetry**: Mirrors existing `.consumes()` API
- ✅ **Simplicity**: No components, hooks, or infrastructure changes needed
- ✅ **Explicit**: Developer intent is crystal clear
- ✅ **Type-safe**: Works with existing Pydantic validation
- ✅ **Declarative**: Pure builder pattern configuration

---

## 🔥 The Problem (Without Fan-Out)

### Current Limitation

```python
# V1: Can only publish ONE artifact
task_creator = (
    flock.agent("task_creator")
    .consumes(ResearchPlan)
    .publishes(ResearchTask)  # ❌ Only creates ONE task!
)
```

**What happens**: LLM generates ONE `ResearchTask`, even if we need 4 parallel tasks.

### Workarounds (All Bad)

**Workaround 1**: Manual `flock.publish()` loops
```python
# ❌ Defeats emergent orchestration!
for task in tasks:
    await flock.publish(task)
```

**Workaround 2**: Wrapper types with component unwrapping
```python
# ❌ Complex, requires FanOutComponent
.publishes(ResearchTaskList)
.fan_out(list_field="tasks")
```

**Workaround 3**: Multiple agents
```python
# ❌ Verbose, doesn't scale
.publishes(ResearchTask1)
.publishes(ResearchTask2)
.publishes(ResearchTask3)
```

**All workarounds violate the Golden Rule: Blackboard should orchestrate, not us!**

---

## ✨ The Solution: Multi-Argument `.publishes()`

### Syntax Option 1: Multiple Arguments

```python
# Publish 3 artifacts of SAME type
task_creator = (
    flock.agent("task_creator")
    .consumes(ResearchPlan)
    .publishes(ResearchTask, ResearchTask, ResearchTask)
)
```

**What happens**: LLM generates 3 `ResearchTask` objects, all published as separate artifacts.

### Syntax Option 2: `fan_out=` Parameter (Sugar)

```python
# Cleaner syntax for same-type fan-out
task_creator = (
    flock.agent("task_creator")
    .consumes(ResearchPlan)
    .publishes(ResearchTask, fan_out=3)
)
```

**Equivalent to**: `.publishes(ResearchTask, ResearchTask, ResearchTask)`

### Syntax Option 3: Mixed Types

```python
# Publish DIFFERENT types in one execution
workflow_starter = (
    flock.agent("workflow_starter")
    .consumes(SpecifyRequest)
    .publishes(SpecMetadata, ResearchPlan, AuditLog)
)
```

**What happens**: LLM generates ONE of each type (3 total artifacts).

### Syntax Option 4: Mixed Types + Fan-Out

```python
# Combine different types with fan-out
complex_agent = (
    flock.agent("complex_agent")
    .consumes(Request)
    .publishes(
        Metadata,                    # 1 metadata
        Task, fan_out=4,            # 4 tasks
        LogEntry, fan_out=2         # 2 log entries
    )  # Total: 7 artifacts
)
```

---

## 🎨 Design Details

### 1. AgentOutput Enhancement

**Current**:
```python
@dataclass
class AgentOutput:
    spec: ArtifactSpec
    default_visibility: Visibility
```

**Proposed**:
```python
@dataclass
class AgentOutput:
    spec: ArtifactSpec
    default_visibility: Visibility
    count: int = 1  # NEW! Number of artifacts to publish

    def is_many(self) -> bool:
        """Check if this output expects multiple artifacts."""
        return self.count > 1
```

### 2. AgentBuilder API

**Current**:
```python
def publishes(
    self,
    *types: Type[BaseModel],
    visibility: Visibility = "private"
) -> AgentBuilder:
    # Only supports: .publishes(A, B, C) for different types
    for type_ in types:
        self._agent.outputs.append(
            AgentOutput(spec=..., default_visibility=visibility)
        )
```

**Proposed**:
```python
def publishes(
    self,
    *types: Type[BaseModel],
    visibility: Visibility = "private",
    fan_out: int | None = None  # NEW!
) -> AgentBuilder:
    """
    Declare artifact types this agent publishes.

    Args:
        *types: Artifact types to publish
        visibility: Default visibility for artifacts
        fan_out: Number of artifacts to publish (applies to ALL types)

    Examples:
        .publishes(A)               # Publish 1 A
        .publishes(A, B, C)         # Publish 1 of each (A, B, C)
        .publishes(A, A, A)         # Publish 3 As
        .publishes(A, fan_out=3)    # Sugar for above
        .publishes(A, B, fan_out=2) # Publish 2 As and 2 Bs
    """
    if fan_out is not None:
        # Apply fan_out to ALL types
        for type_ in types:
            self._agent.outputs.append(
                AgentOutput(
                    spec=...,
                    default_visibility=visibility,
                    count=fan_out
                )
            )
    else:
        # Count duplicates manually
        type_counts = {}
        for type_ in types:
            type_counts[type_] = type_counts.get(type_, 0) + 1

        for type_, count in type_counts.items():
            self._agent.outputs.append(
                AgentOutput(
                    spec=...,
                    default_visibility=visibility,
                    count=count
                )
            )

    return self
```

### 3. Agent Execution Changes

**Current** (`Agent._make_outputs()`):
```python
def _make_outputs(self, result: EvalResult) -> list[Artifact]:
    """Extract artifacts from EvalResult."""
    artifacts = []

    for output_decl in self.outputs:
        # Find ONE artifact matching type
        for artifact in result.artifacts:
            if artifact.type == output_decl.spec.type_name:
                artifacts.append(artifact)
                break

    return artifacts
```

**Proposed**:
```python
def _make_outputs(self, result: EvalResult) -> list[Artifact]:
    """
    Extract artifacts from EvalResult.

    If output declares count > 1, collect ALL artifacts of that type.
    """
    artifacts = []

    for output_decl in self.outputs:
        if output_decl.is_many():
            # Collect ALL artifacts of this type
            matching = [
                a for a in result.artifacts
                if a.type == output_decl.spec.type_name
            ]

            # Validate count
            if len(matching) != output_decl.count:
                raise ValueError(
                    f"Agent {self.name} declared {output_decl.count} "
                    f"artifacts of type {output_decl.spec.type_name}, "
                    f"but LLM generated {len(matching)}"
                )

            artifacts.extend(matching)
        else:
            # Find ONE artifact (current behavior)
            for artifact in result.artifacts:
                if artifact.type == output_decl.spec.type_name:
                    artifacts.append(artifact)
                    break

    return artifacts
```

### 4. Prompt Engineering

**System Prompt Addition**:
```python
# In agent system prompt
if any(output.is_many() for output in agent.outputs):
    prompt += """

IMPORTANT: This agent is configured to publish MULTIPLE artifacts.

"""

    for output in agent.outputs:
        if output.is_many():
            prompt += f"""
- You MUST generate EXACTLY {output.count} artifacts of type {output.spec.type_name}
- Use EvalResult.from_objects() to return multiple objects:

  return EvalResult.from_objects(
      {output.spec.type_name}(...),  # First
      {output.spec.type_name}(...),  # Second
      {output.spec.type_name}(...),  # Third
      # ... (total: {output.count})
      agent=self
  )
"""
```

### 5. LLM Tool Changes

**Update `publish_typed_artifact` tool**:
```python
@flock_tool
def publish_typed_artifact(
    *objects: BaseModel,  # Allow multiple objects!
) -> EvalResult:
    """
    Publish one or more typed artifacts.

    Use this when you need to publish multiple artifacts:

    return publish_typed_artifact(
        Task(id="1", ...),
        Task(id="2", ...),
        Task(id="3", ...),
    )
    """
    return EvalResult.from_objects(*objects, agent=current_agent)
```

---

## 🏗️ Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal**: Support fixed-count fan-out with multiple arguments

**Changes**:
1. Add `count: int` to `AgentOutput` dataclass
2. Update `AgentBuilder.publishes()` to count duplicates
3. Modify `Agent._make_outputs()` to collect multiple artifacts
4. Add validation (count mismatch = error)

**Test**:
```python
agent = (
    flock.agent("test")
    .consumes(Input)
    .publishes(Output, Output, Output)  # 3 outputs
)

# LLM should generate 3 Output objects
```

### Phase 2: Sugar Syntax (Week 1)

**Goal**: Add `fan_out=` parameter

**Changes**:
1. Add `fan_out: int | None` parameter to `.publishes()`
2. Apply `fan_out` to ALL types when specified
3. Update examples to use sugar syntax

**Test**:
```python
agent = (
    flock.agent("test")
    .consumes(Input)
    .publishes(Output, fan_out=3)  # Cleaner!
)
```

### Phase 3: Mixed Types (Week 2)

**Goal**: Support different types + fan-out combinations

**Changes**:
1. Support: `.publishes(A, B, fan_out=2)` → 2 As, 2 Bs
2. Support: `.publishes(A, B, B, C, fan_out=2)` → complex combinations
3. Add clear error messages for ambiguous cases

**Test**:
```python
agent = (
    flock.agent("test")
    .consumes(Input)
    .publishes(Metadata, Task, Task, Task, LogEntry)
    # 1 Metadata, 3 Tasks, 1 LogEntry
)
```

### Phase 4: Prompt Engineering (Week 2)

**Goal**: Guide LLM to generate correct number of artifacts

**Changes**:
1. Add system prompt instructions for multi-artifact agents
2. Update tool descriptions
3. Add examples to agent descriptions

**Test**: LLM consistently generates correct count without errors

### Phase 5: Documentation (Week 3)

**Goal**: Document the pattern and update examples

**Changes**:
1. Update AGENTS.md with fan-out section
2. Create showcase examples
3. Update spec-driven V2 plan
4. Add to dashboard examples

---

## 📊 Comparison: This vs FanOutComponent

| Aspect | `.publishes(A, A, A)` | `FanOutComponent` |
|--------|----------------------|-------------------|
| **Code to add** | ~50 lines | ~300 lines |
| **New concepts** | 0 (uses existing builder) | 1 (components) |
| **API symmetry** | ✅ Matches `.consumes()` | ❌ Different pattern |
| **Declarative** | ✅ Pure builder config | ⚠️ Requires hook logic |
| **Type safety** | ✅ At declaration time | ⚠️ At runtime |
| **Error clarity** | ✅ Count mismatch = clear error | ⚠️ List detection issues |
| **Learning curve** | ✅ Intuitive | ⚠️ Requires understanding components |
| **Flexibility** | ✅ Mixed types supported | ⚠️ One list field per agent |

**Winner**: `.publishes(A, A, A)` approach! 🏆

---

## 🎯 Use Cases

### Use Case 1: Research Task Generation

**Scenario**: Generate 4 parallel research tasks from one plan

```python
task_generator = (
    flock.agent("task_generator")
    .description(
        "Creates 4 research tasks: market, technical, security, and UX. "
        "Each task is a separate ResearchTask artifact for parallel execution."
    )
    .consumes(ResearchPlan)
    .publishes(ResearchTask, fan_out=4)  # ← Magic!
)
```

**Flow**:
1. User publishes `ResearchPlan`
2. `task_generator` creates 4 `ResearchTask` artifacts
3. 4 specialist agents react in parallel
4. Each publishes `ResearchFindings`
5. Aggregator waits with JoinSpec

### Use Case 2: Workflow Initialization

**Scenario**: One agent creates multiple setup artifacts

```python
workflow_starter = (
    flock.agent("workflow_starter")
    .description(
        "Initializes workflow with metadata, audit log, and notification."
    )
    .consumes(WorkflowRequest)
    .publishes(WorkflowMetadata, AuditLog, Notification)  # 3 different types
)
```

**Flow**:
1. User publishes `WorkflowRequest`
2. `workflow_starter` creates 3 artifacts at once
3. Different agents react to each:
   - Metadata → Progress tracker
   - AuditLog → Logger
   - Notification → Notifier

### Use Case 3: Test Case Generation

**Scenario**: Generate multiple test cases from one specification

```python
test_generator = (
    flock.agent("test_generator")
    .description(
        "Generates 10 test cases covering: happy path, edge cases, errors."
    )
    .consumes(TestSpecification)
    .publishes(TestCase, fan_out=10)
)
```

### Use Case 4: Data Processing Pipeline

**Scenario**: Split large dataset into chunks

```python
chunk_creator = (
    flock.agent("chunk_creator")
    .description(
        "Splits dataset into 5 chunks for parallel processing."
    )
    .consumes(Dataset)
    .publishes(DataChunk, fan_out=5)
)

# 5 parallel processors
chunk_processor = (
    flock.agent("chunk_processor")
    .consumes(DataChunk)
    .publishes(ProcessedChunk)
    .max_concurrency(5)  # All 5 run in parallel!
)

# Aggregator
result_aggregator = (
    flock.agent("result_aggregator")
    .consumes(
        ProcessedChunk,
        join=JoinSpec(by=lambda c: c.dataset_id, timeout=timedelta(minutes=10))
    )
    .publishes(FinalResult)
)
```

---

## 🔄 Integration with Spec-Driven V2

### V2 Flow With Fan-Out

```python
# Step 1: Initialize spec
spec_initializer = (
    flock.agent("spec_initializer")
    .consumes(SpecifyRequest)
    .publishes(SpecMetadata)
)

# Step 2: Plan research
research_planner = (
    flock.agent("research_planner")
    .consumes(SpecMetadata)
    .publishes(ResearchPlan)
)

# Step 3: Create 4 tasks (FAN-OUT!)
task_generator = (
    flock.agent("task_generator")
    .consumes(ResearchPlan)
    .publishes(ResearchTask, fan_out=4)  # ← Emergence enabled!
)

# Step 4: 4 specialists react in parallel
research_market = (
    flock.agent("research_market")
    .consumes(ResearchTask, where=lambda t: t.type == "market")
    .publishes(ResearchFindings)
)

research_technical = (
    flock.agent("research_technical")
    .consumes(ResearchTask, where=lambda t: t.type == "technical")
    .publishes(ResearchFindings)
)

# ... 2 more specialists

# Step 5: Aggregate (FAN-IN!)
findings_aggregator = (
    flock.agent("findings_aggregator")
    .consumes(
        ResearchFindings,
        join=JoinSpec(by=lambda f: f.spec_id, timeout=timedelta(minutes=10))
    )
    .publishes(AggregatedFindings)
)
```

**What Emerges**:
1. User publishes ONE `SpecifyRequest`
2. Chain reaction: `SpecMetadata` → `ResearchPlan` → 4 `ResearchTask`s
3. **Parallel execution**: All 4 research specialists fire simultaneously
4. **Automatic aggregation**: JoinSpec waits for all 4 findings
5. **Continued flow**: `AggregatedFindings` triggers next phase

**Zero manual orchestration! Pure emergence!** 🎉

---

## ⚠️ Edge Cases and Validation

### Edge Case 1: Count Mismatch

```python
agent.publishes(Task, fan_out=3)
# LLM generates 2 tasks

# Error raised:
# "Agent task_generator declared 3 artifacts of type Task, but LLM generated 2"
```

**Handling**: Fail fast with clear error message

### Edge Case 2: Zero Count

```python
agent.publishes(Task, fan_out=0)
# Invalid configuration

# Error at build time:
# "fan_out must be >= 1"
```

### Edge Case 3: Mixed Ambiguity

```python
agent.publishes(A, B, B, fan_out=2)
# Ambiguous: Does fan_out apply to all, or override count?

# Resolution: fan_out OVERRIDES manual counts
# Result: 2 As, 2 Bs (not 1 A, 4 Bs)
```

**Documentation**: Make this explicit in docstring

### Edge Case 4: No Artifacts Generated

```python
agent.publishes(Task, fan_out=3)
# LLM generates 0 tasks (empty result)

# Error raised:
# "Agent task_generator declared 3 artifacts of type Task, but LLM generated 0"
```

---

## 📈 Performance Considerations

### Memory Impact

**Scenario**: Agent publishes 1000 artifacts

```python
massive_generator = (
    flock.agent("massive_generator")
    .consumes(Request)
    .publishes(Item, fan_out=1000)
)
```

**Concerns**:
- LLM output size (1000 objects in one response)
- Blackboard memory (1000 artifacts stored)
- Subscription overhead (1000 potential triggers)

**Mitigations**:
1. Add `max_fan_out` safety limit (default: 100)
2. Warn when fan_out > threshold
3. Consider batching for extreme cases

### Token Usage

**Concern**: Large fan-out = large LLM output = high token cost

**Example**:
- 1 artifact = ~200 tokens
- 100 artifacts = ~20,000 tokens
- At $0.003/1k tokens = $0.06 per agent execution

**Mitigation**: Document cost implications, recommend JoinSpec for aggregation

### Concurrency

**Benefit**: Fan-out enables true parallel execution!

```python
# 100 tasks published
.publishes(Task, fan_out=100)

# 10 workers process in parallel
processor = (
    flock.agent("processor")
    .consumes(Task)
    .publishes(Result)
    .max_concurrency(10)  # ← Key for performance!
)

# 100 tasks / 10 workers = 10 waves
# vs 100 sequential executions
```

**Performance Win**: 10x speedup with proper concurrency!

---

## 🎓 Design Principles

### Principle 1: Symmetry

`.publishes()` should mirror `.consumes()` behavior:

```python
# Consume multiple types
.consumes(A, B, C)

# Publish multiple types
.publishes(A, B, C)

# Consume same type with AND logic
.consumes(A, A, A)  # Wait for 3 As

# Publish same type (fan-out)
.publishes(A, A, A)  # Generate 3 As
```

**Rationale**: Consistent API reduces cognitive load

### Principle 2: Explicit Over Implicit

```python
# ✅ GOOD - Explicit count
.publishes(Task, fan_out=4)

# ❌ BAD - Implicit unwrapping
.publishes(TaskList)  # Hidden fan-out behavior
```

**Rationale**: Developer intent should be visible in code

### Principle 3: Fail Fast

```python
# Count mismatch detected immediately after LLM execution
if len(artifacts) != expected_count:
    raise ValueError(...)  # ← Don't publish wrong artifacts!
```

**Rationale**: Errors should surface early with clear messages

### Principle 4: Pay-Per-Use Complexity

```python
# Simple case: No added complexity
.publishes(Task)

# Complex case: Opt-in via parameter
.publishes(Task, fan_out=3)
```

**Rationale**: Common cases should be simple; advanced features optional

---

## 🚀 Migration from V1

### Before (V1 - Wrong)

```python
# Agent tries to do everything
specify_orchestrator = (
    flock.agent("specify_orchestrator")
    .publishes(
        SpecMetadata,
        ResearchTask,
        PRDSection,
        # ... 7 types!
    )
)

# Workflow has manual loops
for task in tasks:
    await flock.publish(task)
```

### After (V2 - Correct)

```python
# Simple agent chain
spec_initializer = (
    flock.agent("spec_initializer")
    .consumes(SpecifyRequest)
    .publishes(SpecMetadata)
)

task_generator = (
    flock.agent("task_generator")
    .consumes(SpecMetadata)
    .publishes(ResearchTask, fan_out=4)  # ← Emergence!
)

# Workflow is just
await flock.serve(dashboard=True)
```

**Benefits**:
- ✅ Agents do ONE thing
- ✅ No manual orchestration
- ✅ Pure emergence
- ✅ < 50% of V1 code

---

## 📋 Implementation Checklist

### Code Changes
- [ ] Add `count: int` field to `AgentOutput` dataclass
- [ ] Add `is_many()` method to `AgentOutput`
- [ ] Update `AgentBuilder.publishes()` signature
- [ ] Implement duplicate counting in `.publishes()`
- [ ] Add `fan_out` parameter support
- [ ] Update `Agent._make_outputs()` to collect multiple artifacts
- [ ] Add count validation with clear error messages
- [ ] Update agent system prompt for multi-artifact generation
- [ ] Update `publish_typed_artifact` tool description
- [ ] Add `max_fan_out` safety limit (default: 100)

### Testing
- [ ] Test: `.publishes(A, A, A)` generates 3 artifacts
- [ ] Test: `.publishes(A, fan_out=3)` generates 3 artifacts
- [ ] Test: `.publishes(A, B, C)` generates 3 different types
- [ ] Test: Count mismatch raises clear error
- [ ] Test: `fan_out=0` raises error at build time
- [ ] Test: Mixed types + fan_out works correctly
- [ ] Test: Integration with JoinSpec (fan-out → fan-in)
- [ ] Test: Performance with fan_out=100
- [ ] Test: LLM prompt engineering (generates correct count)

### Documentation
- [ ] Update AGENTS.md with fan-out section
- [ ] Create showcase example: `07_fanout_parallel.py`
- [ ] Update spec-driven V2 plan with fan-out flow
- [ ] Document edge cases and validation rules
- [ ] Add to dashboard examples
- [ ] Update builder pattern docs
- [ ] Add performance considerations guide

### Examples
- [ ] Create research task fan-out example
- [ ] Create test case generation example
- [ ] Create data chunking example
- [ ] Update spec-driven V2 agents to use fan-out
- [ ] Add dashboard visualization example

---

## 🎯 Success Metrics

After implementation:

✅ **< 100 lines** of code changes (vs 300+ for FanOutComponent)
✅ **API symmetry** with `.consumes()` maintained
✅ **Zero breaking changes** to existing code
✅ **Clear error messages** for count mismatches
✅ **Works with JoinSpec** for fan-out → fan-in pattern
✅ **Dashboard visualization** shows parallel execution
✅ **Spec-driven V2** uses fan-out for emergent orchestration

---

## 🔥 Why This Design Wins

### Compared to FanOutComponent:
- ✅ **90% less code** (~50 lines vs ~300 lines)
- ✅ **No new concepts** (uses existing builder pattern)
- ✅ **Symmetric API** (matches `.consumes()`)
- ✅ **Type-safe at declaration** (not runtime)
- ✅ **Easier to learn** (no component lifecycle)

### Compared to Manual Loops:
- ✅ **Enables emergence** (no `flock.publish()` loops)
- ✅ **Declarative** (intent visible in agent definition)
- ✅ **Dashboard-friendly** (shows fan-out visually)

### Compared to Wrapper Types:
- ✅ **No type pollution** (no `TaskList` wrapper artifacts)
- ✅ **Direct routing** (no unwrapping logic)
- ✅ **Clearer semantics** (count is explicit)

### Compared to Automatic Detection:
- ✅ **Explicit intent** (no "magic" behavior)
- ✅ **No surprises** (developer controls count)
- ✅ **Easy migration** (opt-in via parameter)

---

## 🎊 Recommendation

**IMPLEMENT**: Multi-argument `.publishes()` with `fan_out=` sugar syntax

**WHY**:
1. ✅ Minimal code changes (~50 lines)
2. ✅ Perfect API symmetry with `.consumes()`
3. ✅ Enables emergent orchestration for spec-driven V2
4. ✅ No breaking changes
5. ✅ Intuitive and easy to learn
6. ✅ Type-safe and explicit

**NEXT STEP**: Start with Phase 1 (foundation) - add `count` field and basic support!

---

**Confidence Level**: VERY HIGH 🎯
**Implementation Complexity**: LOW (existing infrastructure ready!)
**Breaking Changes**: NONE
**Time to Ship**: 1-2 weeks

**This approach is pure gold! Let's ship it!** 🚀
