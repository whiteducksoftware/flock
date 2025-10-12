# Fan-Out Pattern Implementation in Flock

## Overview

The fan-out pattern enables an agent to publish a list of items that are automatically distributed as individual work units to downstream agents. This document describes the recommended approach for implementing fan-out in Flock's blackboard architecture.

## Current State

The framework currently supports list type declarations:
```python
.publishes(list[ResearchQueries])
```

However, this publishes a single artifact containing a list, not individual items. Downstream agents receive the entire list as one unit, limiting parallelism.

## Recommended Solution: Component-Based Fan-Out

### Architecture

Use a `FanOutComponent` that intercepts the `post_evaluate` hook to transform list artifacts into individual items:

```python
class FanOutComponent(AgentComponent):
    """Expands list outputs into individual artifacts for parallel processing."""

    name: str = "fan_out"
    list_field: str = Field(default="items", description="Field containing the list")
    preserve_correlation: bool = Field(default=True)
    add_sequence_metadata: bool = Field(default=True)

    async def on_post_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        """Transform single list artifact into multiple individual artifacts."""

        if not result.artifacts:
            return result

        expanded_artifacts = []

        for artifact in result.artifacts:
            # Check if artifact contains a list field
            if self.list_field in artifact.payload:
                items = artifact.payload[self.list_field]

                if isinstance(items, list):
                    # Create individual artifacts for each item
                    for idx, item in enumerate(items):
                        new_artifact = Artifact(
                            type=self._derive_item_type(artifact.type),
                            payload=self._create_item_payload(item),
                            produced_by=artifact.produced_by,
                            correlation_id=artifact.correlation_id if self.preserve_correlation else None,
                            visibility=artifact.visibility,
                            metadata={
                                **(artifact.metadata or {}),
                                "sequence_index": idx if self.add_sequence_metadata else None,
                                "sequence_total": len(items) if self.add_sequence_metadata else None,
                                "parent_artifact": artifact.id
                            }
                        )
                        expanded_artifacts.append(new_artifact)
                else:
                    # Not a list, pass through unchanged
                    expanded_artifacts.append(artifact)
            else:
                # No list field, pass through unchanged
                expanded_artifacts.append(artifact)

        # Replace artifacts in result
        result.artifacts = expanded_artifacts
        return result

    def _derive_item_type(self, list_type: str) -> str:
        """Derive individual item type from list type name."""
        # e.g., "List[ResearchQuery]" -> "ResearchQuery"
        if list_type.startswith("List[") and list_type.endswith("]"):
            return list_type[5:-1]
        return list_type

    def _create_item_payload(self, item: Any) -> dict:
        """Create payload for individual item."""
        if isinstance(item, dict):
            return item
        elif isinstance(item, str):
            return {"value": item}
        else:
            return {"item": item}
```

## Developer Experience (DX)

### Recommended API: Explicit `.fan_out()` Method

Add a builder method for clarity:

```python
# Clear and explicit
query_generator = (
    flock.agent("query_generator")
    .description("Generates multiple research queries")
    .consumes(ResearchTask)
    .publishes(ResearchQueries)  # Still publishes the wrapper type
    .fan_out()  # Explicit fan-out behavior
)

# Implementation in AgentBuilder
def fan_out(self, **config) -> Self:
    """Enable fan-out for list outputs."""
    component = FanOutComponent(config=FanOutConfig(**config))
    return self.with_utilities(component)
```

### Alternative Patterns Considered

1. **Implicit List Detection** - Automatic but can be surprising
2. **Type Wrapper** (`FanOut[Type]`) - Too complex, non-standard
3. **Orchestrator-Level** - Violates separation of concerns
4. **Engine-Level** - Not reusable across engines

## Benefits

1. **Clean Separation**: Engine remains unaware of fan-out semantics
2. **Parallel Processing**: Each item scheduled independently
3. **Type Safety**: Maintains strong typing throughout
4. **Flexibility**: Component can be configured or disabled
5. **Traceability**: Correlation IDs and metadata preserve relationships

## Integration Example

```python
import asyncio
from pydantic import BaseModel, Field
from flock.orchestrator import Flock
from flock.registry import flock_type

# Define types
@flock_type
class ResearchTask(BaseModel):
    topic: str

@flock_type
class ResearchQueries(BaseModel):
    queries: list[str]

@flock_type
class ResearchQuery(BaseModel):
    query: str

@flock_type
class QueryResult(BaseModel):
    query: str
    findings: str

# Create agents with fan-out
flock = Flock("openai/gpt-4")

query_generator = (
    flock.agent("query_generator")
    .description("Generates multiple research queries")
    .consumes(ResearchTask)
    .publishes(ResearchQueries)
    .fan_out(list_field="queries")  # Fan-out the queries list
)

query_processor = (
    flock.agent("query_processor")
    .description("Process individual query")
    .consumes(ResearchQuery)  # Consumes individual items
    .publishes(QueryResult)
    .max_concurrency(5)  # Process up to 5 queries in parallel
)

# Run
async def main():
    task = ResearchTask(topic="AI collaboration patterns")
    await flock.publish(task)
    await flock.run_until_idle()

    # Each query processed independently in parallel
    results = await flock.query(QueryResult)
    print(f"Processed {len(results)} queries")

asyncio.run(main())
```

## Error Handling

The component handles edge cases gracefully:

- Non-list artifacts pass through unchanged
- Empty lists produce no artifacts (intentional no-op)
- Missing fields are logged but don't fail
- Type derivation failures fall back to original type

## Testing

```python
async def test_fan_out_component():
    """Test that FanOutComponent correctly expands lists."""
    component = FanOutComponent(list_field="items")

    # Create test data
    list_artifact = Artifact(
        type="List[Task]",
        payload={"items": ["task1", "task2", "task3"]}
    )

    result = EvalResult(artifacts=[list_artifact])

    # Apply fan-out
    expanded = await component.on_post_evaluate(agent, ctx, inputs, result)

    # Verify expansion
    assert len(expanded.artifacts) == 3
    assert all(a.type == "Task" for a in expanded.artifacts)
    assert expanded.artifacts[0].payload == {"value": "task1"}
```

## Migration Path

For existing code using `list[Type]`:

1. Add `.fan_out()` to publishing agents
2. Update consuming agents to handle individual types
3. Test with small datasets first
4. Monitor performance with larger fan-outs

## Performance Considerations

- Set reasonable limits: `.fan_out(max_items=1000)`
- Use `.max_concurrency()` on consuming agents
- Consider batching for very large lists
- Monitor memory usage with many parallel tasks

## Future Enhancements

1. **Fan-In Component**: Aggregate results back into lists
2. **Dynamic Routing**: Route items based on content
3. **Progress Tracking**: Monitor fan-out completion
4. **Retry Policies**: Handle partial failures