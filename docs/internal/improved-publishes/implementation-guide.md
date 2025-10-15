# Implementation Guide: Multi-Artifact `.publishes()`

**Step-by-step code changes to implement the improved publishes API**

---

## 📋 Overview

This guide provides the exact code changes needed to implement multi-artifact publishing through `.publishes(A, A, A)` and `.publishes(A, fan_out=3)` syntax.

**Files to Modify**:
1. `src/flock/agent.py` - AgentOutput and AgentBuilder changes
2. `src/flock/agent.py` - Agent._make_outputs() changes
3. System prompt updates for LLM guidance

**Estimated Effort**: 2-4 hours of coding + testing

---

## Step 1: Update AgentOutput Dataclass

**File**: `src/flock/agent.py` (around line 50-60)

**Current Code**:
```python
@dataclass
class AgentOutput:
    spec: ArtifactSpec
    default_visibility: Visibility
```

**New Code**:
```python
@dataclass
class AgentOutput:
    spec: ArtifactSpec
    default_visibility: Visibility
    count: int = 1  # NEW! Number of artifacts to publish

    def is_many(self) -> bool:
        """Check if this output expects multiple artifacts."""
        return self.count > 1

    def __repr__(self) -> str:
        if self.count > 1:
            return f"AgentOutput({self.spec.type_name} x{self.count})"
        return f"AgentOutput({self.spec.type_name})"
```

**Why**: Add count tracking to output declarations.

---

## Step 2: Update AgentBuilder.publishes()

**File**: `src/flock/agent.py` (around line 700-720)

**Current Signature**:
```python
def publishes(
    self,
    *types: Type[BaseModel],
    visibility: Visibility = "private"
) -> AgentBuilder:
```

**New Signature**:
```python
def publishes(
    self,
    *types: Type[BaseModel],
    visibility: Visibility = "private",
    fan_out: int | None = None  # NEW!
) -> AgentBuilder:
```

**Current Implementation**:
```python
def publishes(
    self,
    *types: Type[BaseModel],
    visibility: Visibility = "private"
) -> AgentBuilder:
    """Declare artifact types this agent publishes."""
    for type_ in types:
        spec = ArtifactSpec.from_type(type_)
        self._agent.outputs.append(
            AgentOutput(spec=spec, default_visibility=visibility)
        )
    return self
```

**New Implementation**:
```python
def publishes(
    self,
    *types: Type[BaseModel],
    visibility: Visibility = "private",
    fan_out: int | None = None
) -> AgentBuilder:
    """
    Declare artifact types this agent publishes.

    Args:
        *types: Artifact types to publish. Repeating a type declares
               multiple artifacts of that type.
        visibility: Default visibility for published artifacts
        fan_out: Number of artifacts to publish for ALL types.
                Overrides duplicate counting.

    Examples:
        .publishes(Task)                  # Publish 1 Task
        .publishes(Task, Task, Task)      # Publish 3 Tasks
        .publishes(Task, fan_out=3)       # Same as above (sugar syntax)
        .publishes(A, B, C)               # Publish 1 of each
        .publishes(A, B, fan_out=2)       # Publish 2 As and 2 Bs

    Returns:
        self for method chaining
    """
    # Validation
    if fan_out is not None and fan_out < 1:
        raise ValueError(f"fan_out must be >= 1, got {fan_out}")

    if fan_out is not None:
        # Apply fan_out to ALL types
        unique_types = set(types)  # Remove duplicates
        for type_ in unique_types:
            spec = ArtifactSpec.from_type(type_)
            self._agent.outputs.append(
                AgentOutput(
                    spec=spec,
                    default_visibility=visibility,
                    count=fan_out
                )
            )
    else:
        # Count duplicates manually
        from collections import Counter
        type_counts = Counter(types)

        for type_, count in type_counts.items():
            spec = ArtifactSpec.from_type(type_)
            self._agent.outputs.append(
                AgentOutput(
                    spec=spec,
                    default_visibility=visibility,
                    count=count
                )
            )

    return self
```

**Why**: Support both `.publishes(A, A, A)` and `.publishes(A, fan_out=3)` syntax.

---

## Step 3: Update Agent._make_outputs()

**File**: `src/flock/agent.py` (around line 450-480)

**Current Implementation**:
```python
def _make_outputs(self, result: EvalResult) -> list[Artifact]:
    """Extract artifacts from EvalResult matching declared outputs."""
    artifacts = []

    for output_decl in self.outputs:
        # Find first artifact matching type
        for artifact in result.artifacts:
            if artifact.type == output_decl.spec.type_name:
                # Apply visibility
                if artifact.visibility == "default":
                    artifact.visibility = output_decl.default_visibility
                artifacts.append(artifact)
                break

    return artifacts
```

**New Implementation**:
```python
def _make_outputs(self, result: EvalResult) -> list[Artifact]:
    """
    Extract artifacts from EvalResult matching declared outputs.

    For outputs with count > 1, collects ALL artifacts of that type
    and validates the count matches the declaration.
    """
    artifacts = []
    used_artifact_ids = set()  # Track which artifacts we've consumed

    for output_decl in self.outputs:
        if output_decl.is_many():
            # Collect ALL unused artifacts of this type
            matching = [
                a for a in result.artifacts
                if (a.type == output_decl.spec.type_name and
                    id(a) not in used_artifact_ids)
            ]

            # Validate count
            if len(matching) != output_decl.count:
                raise ValueError(
                    f"Agent '{self.name}' declared {output_decl.count} "
                    f"artifacts of type '{output_decl.spec.type_name}', "
                    f"but LLM generated {len(matching)}. "
                    f"\n\nHint: Use EvalResult.from_objects() to return multiple objects:\n"
                    f"  return EvalResult.from_objects(\n"
                    f"    {output_decl.spec.type_name}(...),\n"
                    f"    {output_decl.spec.type_name}(...),\n"
                    f"    # ... ({output_decl.count} total)\n"
                    f"    agent=self\n"
                    f"  )"
                )

            # Apply visibility and mark as used
            for artifact in matching:
                if artifact.visibility == "default":
                    artifact.visibility = output_decl.default_visibility
                used_artifact_ids.add(id(artifact))

            artifacts.extend(matching)
        else:
            # Find first unused artifact (current behavior)
            for artifact in result.artifacts:
                if (artifact.type == output_decl.spec.type_name and
                    id(artifact) not in used_artifact_ids):
                    # Apply visibility
                    if artifact.visibility == "default":
                        artifact.visibility = output_decl.default_visibility
                    artifacts.append(artifact)
                    used_artifact_ids.add(id(artifact))
                    break

    return artifacts
```

**Why**: Collect multiple artifacts when count > 1, validate count, provide helpful error messages.

---

## Step 4: Update System Prompt

**File**: `src/flock/agent.py` (in system prompt generation, around line 300-350)

**Add After Output Type Documentation**:
```python
def _build_system_prompt(self) -> str:
    """Build system prompt for agent."""
    prompt = f"You are {self.name}. {self.description}\n\n"

    # ... existing input documentation ...

    # Output documentation
    prompt += "**Outputs**:\n"
    for output in self.outputs:
        if output.is_many():
            prompt += f"- {output.spec.type_name} (x{output.count})\n"
        else:
            prompt += f"- {output.spec.type_name}\n"

    # NEW: Add multi-artifact guidance
    multi_outputs = [o for o in self.outputs if o.is_many()]
    if multi_outputs:
        prompt += "\n**IMPORTANT - Multiple Artifact Publishing**:\n"
        prompt += "This agent is configured to publish MULTIPLE artifacts. You MUST:\n\n"

        for output in multi_outputs:
            prompt += f"1. Generate EXACTLY {output.count} instances of {output.spec.type_name}\n"

        prompt += "\n2. Return ALL artifacts using EvalResult.from_objects():\n\n"
        prompt += "```python\n"
        prompt += "return EvalResult.from_objects(\n"
        for output in multi_outputs:
            for i in range(output.count):
                prompt += f"    {output.spec.type_name}(  # {i + 1}/{output.count}\n"
                prompt += f"        # ... fields ...\n"
                prompt += f"    ),\n"
        prompt += "    agent=self\n"
        prompt += ")\n```\n\n"
        prompt += f"The system will validate that you generated exactly the declared count. "
        prompt += f"Missing or extra artifacts will cause an error.\n\n"

    return prompt
```

**Why**: Guide LLM to generate correct number of artifacts with clear examples.

---

## Step 5: Add Safety Limit (Optional but Recommended)

**File**: `src/flock/agent.py` (in AgentBuilder.publishes())

**Add Validation**:
```python
# At the start of publishes() method
MAX_FAN_OUT = 100  # Safety limit

def publishes(
    self,
    *types: Type[BaseModel],
    visibility: Visibility = "private",
    fan_out: int | None = None
) -> AgentBuilder:
    # ... existing validation ...

    # NEW: Safety check
    if fan_out is not None and fan_out > MAX_FAN_OUT:
        import warnings
        warnings.warn(
            f"fan_out={fan_out} exceeds recommended limit of {MAX_FAN_OUT}. "
            f"This may cause performance issues and high LLM costs. "
            f"Consider using batch processing or chunking strategies instead.",
            UserWarning,
            stacklevel=2
        )

    # ... rest of implementation ...
```

**Why**: Prevent accidental huge fan-outs that could cause memory/cost issues.

---

## Step 6: Update Tool Description (Optional)

**File**: `src/flock/engine/tools.py` (or wherever publish tool is defined)

**Current**:
```python
@flock_tool
def publish_typed_artifact(obj: BaseModel) -> EvalResult:
    """Publish a typed artifact."""
    return EvalResult.from_objects(obj, agent=current_agent)
```

**New**:
```python
@flock_tool
def publish_typed_artifact(*objects: BaseModel) -> EvalResult:
    """
    Publish one or more typed artifacts.

    For single artifact:
        return publish_typed_artifact(Task(...))

    For multiple artifacts (when agent declares fan_out or multiple types):
        return publish_typed_artifact(
            Task(id="1", ...),
            Task(id="2", ...),
            Task(id="3", ...),
        )

    The agent configuration determines how many artifacts are expected.
    """
    return EvalResult.from_objects(*objects, agent=current_agent)
```

**Why**: Make it clear to LLM that multiple objects are supported.

---

## Testing Strategy

### Unit Tests

**File**: `tests/test_agent_builder.py`

```python
def test_publishes_with_duplicates():
    """Test that duplicate types are counted correctly."""
    agent = (
        Agent("test")
        .publishes(Task, Task, Task)
    )

    assert len(agent.outputs) == 1
    assert agent.outputs[0].count == 3


def test_publishes_with_fan_out():
    """Test fan_out parameter."""
    agent = (
        Agent("test")
        .publishes(Task, fan_out=5)
    )

    assert len(agent.outputs) == 1
    assert agent.outputs[0].count == 5


def test_publishes_mixed_types():
    """Test multiple different types."""
    agent = (
        Agent("test")
        .publishes(TaskA, TaskB, TaskB, TaskC)
    )

    assert len(agent.outputs) == 3
    # Find counts
    counts = {o.spec.type_name: o.count for o in agent.outputs}
    assert counts["TaskA"] == 1
    assert counts["TaskB"] == 2
    assert counts["TaskC"] == 1


def test_publishes_fan_out_validation():
    """Test that fan_out=0 raises error."""
    with pytest.raises(ValueError, match="fan_out must be >= 1"):
        Agent("test").publishes(Task, fan_out=0)
```

### Integration Tests

**File**: `tests/test_multi_artifact.py`

```python
import pytest
from pydantic import BaseModel
from flock import Flock, flock_type
from flock.runtime import EvalResult


@flock_type
class Request(BaseModel):
    task_count: int


@flock_type
class Task(BaseModel):
    task_id: str


@pytest.mark.asyncio
async def test_multi_artifact_generation():
    """Test that agent generates multiple artifacts."""
    flock = Flock()

    # Agent that publishes 3 tasks
    generator = (
        flock.agent("generator")
        .description(
            "Generates 3 tasks with IDs: task-1, task-2, task-3. "
            "Use EvalResult.from_objects() to return all 3 tasks."
        )
        .consumes(Request)
        .publishes(Task, fan_out=3)
    )

    # Collector agent
    collected_tasks = []

    collector = (
        flock.agent("collector")
        .consumes(Task)
        .publishes(None)  # Just collect, don't publish
    )

    @collector.on_post_consume
    async def collect(agent, ctx, inputs, result):
        collected_tasks.append(inputs.artifacts[0].payload["task_id"])
        return result

    # Trigger workflow
    request = Request(task_count=3)
    await flock.publish(request)
    await flock.run_until_idle()

    # Verify 3 tasks were created
    assert len(collected_tasks) == 3
    assert "task-1" in collected_tasks
    assert "task-2" in collected_tasks
    assert "task-3" in collected_tasks


@pytest.mark.asyncio
async def test_count_mismatch_error():
    """Test that wrong count raises clear error."""
    flock = Flock()

    # Agent declares 3 but might generate 2
    generator = (
        flock.agent("generator")
        .description("Generate 2 tasks (WRONG - should be 3)")
        .consumes(Request)
        .publishes(Task, fan_out=3)
    )

    request = Request(task_count=2)

    with pytest.raises(ValueError, match="declared 3.*generated 2"):
        await flock.publish(request)
        await flock.run_until_idle()
```

---

## Rollout Plan

### Phase 1: Foundation (Day 1-2)
- Implement Steps 1-3
- Add basic unit tests
- Test with simple examples

### Phase 2: Polish (Day 3)
- Add system prompt updates (Step 4)
- Add safety limits (Step 5)
- Enhance error messages

### Phase 3: Validation (Day 4)
- Write integration tests
- Test with spec-driven V2 scenarios
- Verify dashboard visualization

### Phase 4: Documentation (Day 5)
- Update AGENTS.md
- Create showcase examples
- Add migration guide

---

## Common Pitfalls

### Pitfall 1: Forgetting EvalResult.from_objects()

**Problem**: LLM uses old return style
```python
# ❌ WRONG
return result_obj  # Only returns 1 artifact
```

**Solution**: System prompt + tool description guide to correct usage
```python
# ✅ CORRECT
return EvalResult.from_objects(obj1, obj2, obj3, agent=self)
```

### Pitfall 2: Not Validating Count

**Problem**: Silent failures when count mismatches

**Solution**: Raise clear ValueError in `_make_outputs()` with helpful hint

### Pitfall 3: Ambiguous fan_out Semantics

**Problem**: Does `fan_out` override or multiply?

**Solution**: Document that `fan_out` OVERRIDES duplicate counting:
```python
.publishes(A, A, fan_out=3)  # = 3 As (not 6!)
```

---

## Success Criteria

✅ `.publishes(A, A, A)` creates 3 output declarations with count=3
✅ `.publishes(A, fan_out=3)` equivalent to above
✅ Count mismatch raises clear error with example code
✅ LLM generates correct count (validated with integration tests)
✅ Mixed types work: `.publishes(A, B, B, C)` → [A×1, B×2, C×1]
✅ Safety limit warns at fan_out > 100
✅ System prompt guides LLM to use EvalResult.from_objects()
✅ Dashboard shows fan-out visually
✅ Spec-driven V2 works with fan-out pattern

---

**Estimated Total Effort**: 8-16 hours (including testing)

**Ready to implement? Let's ship this!** 🚀
