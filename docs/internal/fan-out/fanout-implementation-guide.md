# Fan-Out Implementation Guide

## Quick Start

This guide shows how to implement the fan-out pattern in Flock using the recommended `FanOutComponent` approach.

## Implementation Code

### Step 1: Create the FanOutComponent

Create a new file `src/flock/components/fanout.py`:

```python
"""Fan-out component for expanding list artifacts into individual items."""

from typing import Any, Optional
from pydantic import BaseModel, Field
from flock.components import AgentComponent
from flock.artifacts import Artifact
from flock.runtime import Context, EvalInputs, EvalResult


class FanOutConfig(BaseModel):
    """Configuration for fan-out behavior."""

    enabled: bool = Field(default=True, description="Enable fan-out")
    list_field: str = Field(default="items", description="Field containing the list")
    preserve_correlation: bool = Field(default=True, description="Keep correlation IDs")
    add_sequence_metadata: bool = Field(default=True, description="Add position metadata")
    max_items: Optional[int] = Field(default=None, description="Maximum items to expand")
    item_type_suffix: str = Field(default="", description="Suffix to remove from list type")


class FanOutComponent(AgentComponent):
    """
    Expands list outputs into individual artifacts for parallel processing.

    This component intercepts the post_evaluate hook to transform artifacts
    containing lists into multiple individual artifacts, enabling parallel
    processing by downstream agents.

    Example:
        >>> # Agent publishes ResearchQueries with queries=["q1", "q2", "q3"]
        >>> # FanOutComponent transforms this into 3 individual ResearchQuery artifacts
        >>> agent = (
        ...     flock.agent("generator")
        ...     .publishes(ResearchQueries)
        ...     .with_utilities(FanOutComponent(list_field="queries"))
        ... )
    """

    name: str = "fan_out"
    config: FanOutConfig = Field(default_factory=FanOutConfig)

    async def on_post_evaluate(
        self, agent: "Agent", ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        """Transform list artifacts into individual item artifacts."""

        if not self.config.enabled or not result.artifacts:
            return result

        expanded_artifacts = []

        for artifact in result.artifacts:
            expanded = await self._try_expand_artifact(artifact, agent.name)
            if expanded:
                expanded_artifacts.extend(expanded)
            else:
                expanded_artifacts.append(artifact)

        # Log expansion if it occurred
        if len(expanded_artifacts) != len(result.artifacts):
            result.logs.append(
                f"Fan-out: Expanded {len(result.artifacts)} artifacts "
                f"into {len(expanded_artifacts)} items"
            )

        result.artifacts = expanded_artifacts
        return result

    async def _try_expand_artifact(
        self, artifact: Artifact, agent_name: str
    ) -> Optional[list[Artifact]]:
        """
        Try to expand an artifact if it contains a list field.

        Returns:
            List of expanded artifacts if successful, None otherwise
        """
        # Check if artifact has the configured list field
        if self.config.list_field not in artifact.payload:
            return None

        items = artifact.payload[self.config.list_field]
        if not isinstance(items, list):
            return None

        # Apply max_items limit if configured
        if self.config.max_items:
            items = items[:self.config.max_items]

        # Create individual artifacts
        expanded = []
        for idx, item in enumerate(items):
            new_artifact = self._create_item_artifact(
                artifact, item, idx, len(items), agent_name
            )
            expanded.append(new_artifact)

        return expanded

    def _create_item_artifact(
        self,
        parent: Artifact,
        item: Any,
        index: int,
        total: int,
        agent_name: str
    ) -> Artifact:
        """Create an individual artifact from a list item."""

        # Derive item type from parent type
        item_type = self._derive_item_type(parent.type)

        # Create item payload
        item_payload = self._create_item_payload(item, parent.payload)

        # Build metadata
        metadata = {**(parent.metadata or {})}
        if self.config.add_sequence_metadata:
            metadata.update({
                "fan_out_index": index,
                "fan_out_total": total,
                "fan_out_parent": str(parent.id),
                "fan_out_field": self.config.list_field
            })

        return Artifact(
            type=item_type,
            payload=item_payload,
            produced_by=agent_name,
            correlation_id=parent.correlation_id if self.config.preserve_correlation else None,
            visibility=parent.visibility,
            metadata=metadata,
            tags=parent.tags
        )

    def _derive_item_type(self, list_type: str) -> str:
        """
        Derive individual item type from list type name.

        Examples:
            "List[ResearchQuery]" -> "ResearchQuery"
            "ResearchQueries" -> "ResearchQuery" (with suffix="ies")
        """
        # Handle List[Type] pattern
        if list_type.startswith("List[") and list_type.endswith("]"):
            return list_type[5:-1]

        # Handle plural forms with configured suffix
        if self.config.item_type_suffix and list_type.endswith(self.config.item_type_suffix):
            return list_type[:-len(self.config.item_type_suffix)]

        # Try common plural patterns
        if list_type.endswith("ies"):
            return list_type[:-3] + "y"  # Queries -> Query
        elif list_type.endswith("es"):
            return list_type[:-2]  # Batches -> Batch
        elif list_type.endswith("s"):
            return list_type[:-1]  # Tasks -> Task

        # Default: use original type
        return list_type

    def _create_item_payload(self, item: Any, parent_payload: dict) -> dict:
        """
        Create payload for individual item.

        Preserves non-list fields from parent and adds item data.
        """
        # Start with parent fields (except the list field)
        item_payload = {
            k: v for k, v in parent_payload.items()
            if k != self.config.list_field
        }

        # Add item data
        if isinstance(item, dict):
            item_payload.update(item)
        elif isinstance(item, str):
            # For simple string items, use a standard field name
            item_payload[self.config.list_field[:-1]] = item  # e.g., "queries" -> "query"
        else:
            item_payload["item"] = item

        return item_payload
```

### Step 2: Add Builder Method to Agent

Update `src/flock/agent.py` to add the `.fan_out()` convenience method:

```python
# In AgentBuilder class, add this method:

def fan_out(
    self,
    list_field: str = "items",
    preserve_correlation: bool = True,
    max_items: Optional[int] = None,
    **kwargs
) -> Self:
    """
    Enable fan-out for list outputs.

    When this agent publishes artifacts containing lists, the FanOutComponent
    will automatically expand them into individual artifacts for parallel
    processing by downstream agents.

    Args:
        list_field: Name of the field containing the list (default: "items")
        preserve_correlation: Keep correlation IDs across expanded items
        max_items: Maximum number of items to expand (None = unlimited)
        **kwargs: Additional configuration for FanOutConfig

    Returns:
        Self for method chaining

    Example:
        >>> agent = (
        ...     flock.agent("generator")
        ...     .publishes(TaskList)
        ...     .fan_out(list_field="tasks", max_items=100)
        ... )
    """
    from flock.components.fanout import FanOutComponent, FanOutConfig

    config = FanOutConfig(
        list_field=list_field,
        preserve_correlation=preserve_correlation,
        max_items=max_items,
        **kwargs
    )

    return self.with_utilities(FanOutComponent(config=config))
```

### Step 3: Create Tests

Create `tests/test_fanout_component.py`:

```python
"""Tests for fan-out component."""

import pytest
from unittest.mock import Mock
from flock.components.fanout import FanOutComponent, FanOutConfig
from flock.artifacts import Artifact
from flock.runtime import EvalInputs, EvalResult, Context
from uuid import uuid4


@pytest.fixture
def mock_agent():
    agent = Mock()
    agent.name = "test_agent"
    return agent


@pytest.fixture
def mock_context():
    return Mock(spec=Context)


@pytest.mark.asyncio
async def test_fanout_expands_list(mock_agent, mock_context):
    """Test that FanOutComponent correctly expands list artifacts."""

    # Create component
    component = FanOutComponent(config=FanOutConfig(list_field="queries"))

    # Create test artifact with list
    list_artifact = Artifact(
        type="ResearchQueries",
        payload={"queries": ["query1", "query2", "query3"], "context": "test"},
        produced_by="generator"
    )

    # Create result with list artifact
    result = EvalResult(artifacts=[list_artifact])
    inputs = EvalInputs()

    # Apply fan-out
    expanded = await component.on_post_evaluate(mock_agent, mock_context, inputs, result)

    # Verify expansion
    assert len(expanded.artifacts) == 3

    # Check first expanded artifact
    first = expanded.artifacts[0]
    assert first.type == "ResearchQuery"  # Singular form
    assert first.payload["query"] == "query1"  # Individual item
    assert first.payload["context"] == "test"  # Parent field preserved
    assert first.metadata["fan_out_index"] == 0
    assert first.metadata["fan_out_total"] == 3


@pytest.mark.asyncio
async def test_fanout_preserves_correlation(mock_agent, mock_context):
    """Test that correlation IDs are preserved."""

    component = FanOutComponent(config=FanOutConfig(
        list_field="items",
        preserve_correlation=True
    ))

    correlation_id = uuid4()
    artifact = Artifact(
        type="TaskList",
        payload={"items": ["task1", "task2"]},
        correlation_id=correlation_id
    )

    result = EvalResult(artifacts=[artifact])
    expanded = await component.on_post_evaluate(
        mock_agent, mock_context, EvalInputs(), result
    )

    # All expanded artifacts should have same correlation ID
    assert all(a.correlation_id == correlation_id for a in expanded.artifacts)


@pytest.mark.asyncio
async def test_fanout_respects_max_items(mock_agent, mock_context):
    """Test that max_items limit is enforced."""

    component = FanOutComponent(config=FanOutConfig(
        list_field="items",
        max_items=2
    ))

    artifact = Artifact(
        type="TaskList",
        payload={"items": ["t1", "t2", "t3", "t4", "t5"]}
    )

    result = EvalResult(artifacts=[artifact])
    expanded = await component.on_post_evaluate(
        mock_agent, mock_context, EvalInputs(), result
    )

    # Should only expand first 2 items
    assert len(expanded.artifacts) == 2


@pytest.mark.asyncio
async def test_fanout_handles_non_list_gracefully(mock_agent, mock_context):
    """Test that non-list artifacts pass through unchanged."""

    component = FanOutComponent(config=FanOutConfig(list_field="items"))

    # Artifact without list field
    artifact = Artifact(
        type="SingleTask",
        payload={"task": "do something"}
    )

    result = EvalResult(artifacts=[artifact])
    expanded = await component.on_post_evaluate(
        mock_agent, mock_context, EvalInputs(), result
    )

    # Should pass through unchanged
    assert len(expanded.artifacts) == 1
    assert expanded.artifacts[0] == artifact


@pytest.mark.asyncio
async def test_fanout_disabled(mock_agent, mock_context):
    """Test that disabled component does nothing."""

    component = FanOutComponent(config=FanOutConfig(
        enabled=False,
        list_field="items"
    ))

    artifact = Artifact(
        type="TaskList",
        payload={"items": ["t1", "t2"]}
    )

    result = EvalResult(artifacts=[artifact])
    original_artifacts = result.artifacts.copy()

    expanded = await component.on_post_evaluate(
        mock_agent, mock_context, EvalInputs(), result
    )

    # Should return unchanged
    assert expanded.artifacts == original_artifacts


@pytest.mark.asyncio
async def test_type_derivation_patterns():
    """Test various type name derivation patterns."""

    component = FanOutComponent()

    # Test cases: (input_type, expected_output_type)
    test_cases = [
        ("List[Task]", "Task"),
        ("TaskList", "TaskList"),  # Can't derive without suffix
        ("Queries", "Query"),      # -ies -> -y
        ("Batches", "Batch"),      # -es -> -
        ("Tasks", "Task"),         # -s -> -
    ]

    for input_type, expected in test_cases:
        result = component._derive_item_type(input_type)
        assert result == expected, f"Failed for {input_type}"
```

### Step 4: Usage Example

Create `examples/showcase/07_fanout_advanced.py`:

```python
"""Advanced fan-out example with parallel processing."""

import asyncio
from pydantic import BaseModel, Field
from flock.orchestrator import Flock
from flock.registry import flock_type


# Define artifact types
@flock_type
class AnalysisRequest(BaseModel):
    topic: str
    depth: str = "detailed"


@flock_type
class AnalysisQuestions(BaseModel):
    """Multiple questions to analyze."""
    questions: list[str] = Field(description="List of analysis questions")
    topic: str
    depth: str


@flock_type
class AnalysisQuestion(BaseModel):
    """Single question to analyze."""
    question: str
    topic: str
    depth: str


@flock_type
class AnalysisResult(BaseModel):
    question: str
    analysis: str
    confidence: float


@flock_type
class FinalReport(BaseModel):
    topic: str
    total_questions: int
    analyses: list[dict]
    average_confidence: float


# Create orchestrator
flock = Flock("openai/gpt-4o-mini")

# Question generator with fan-out
question_generator = (
    flock.agent("question_generator")
    .description("Generate multiple analysis questions")
    .consumes(AnalysisRequest)
    .publishes(AnalysisQuestions)
    .fan_out(list_field="questions", max_items=10)  # Fan-out enabled!
)

# Individual question analyzer (parallel processing)
question_analyzer = (
    flock.agent("question_analyzer")
    .description("Analyze a single question in depth")
    .consumes(AnalysisQuestion)
    .publishes(AnalysisResult)
    .max_concurrency(5)  # Process up to 5 questions in parallel
)

# Report aggregator (fan-in pattern)
report_aggregator = (
    flock.agent("report_aggregator")
    .description("Aggregate all analyses into final report")
    .consumes(AnalysisResult, batch=True, batch_size=10, batch_timeout=5.0)
    .publishes(FinalReport)
)


async def main():
    print("🚀 Starting fan-out analysis workflow...")

    # Publish initial request
    request = AnalysisRequest(
        topic="Impact of AI on software development",
        depth="comprehensive"
    )

    await flock.publish(request)
    await flock.run_until_idle()

    # Query results
    questions = await flock.query(AnalysisQuestion)
    results = await flock.query(AnalysisResult)
    report = await flock.query(FinalReport)

    print(f"\n📊 Analysis complete!")
    print(f"   Generated questions: {len(questions)}")
    print(f"   Completed analyses: {len(results)}")
    print(f"   Final reports: {len(report)}")

    if report:
        print(f"\n📄 Final Report Summary:")
        print(f"   Topic: {report[0].topic}")
        print(f"   Questions analyzed: {report[0].total_questions}")
        print(f"   Average confidence: {report[0].average_confidence:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
```

## Integration Checklist

- [ ] Create `src/flock/components/fanout.py` with FanOutComponent
- [ ] Add `.fan_out()` method to AgentBuilder in `src/flock/agent.py`
- [ ] Create tests in `tests/test_fanout_component.py`
- [ ] Add example in `examples/showcase/`
- [ ] Update `__init__.py` exports if needed
- [ ] Document in README or AGENTS.md

## Performance Tuning

### For Large Lists (1000+ items)

```python
agent.fan_out(
    max_items=1000,  # Limit expansion
    add_sequence_metadata=False  # Reduce metadata overhead
)

# And limit downstream concurrency
consumer.max_concurrency(10)  # Process 10 at a time
```

### For Memory-Constrained Environments

```python
# Use batching on consumers instead of unlimited parallelism
consumer = (
    flock.agent("processor")
    .consumes(Item, batch=True, batch_size=50)
    .publishes(Result)
)
```

## Monitoring Fan-Out

Add logging to track fan-out behavior:

```python
from flock.utilities import LoggingUtility

agent = (
    flock.agent("generator")
    .publishes(ItemList)
    .fan_out()
    .with_utilities(LoggingUtility())  # Will show fan-out in logs
)
```

## Troubleshooting

### Items Not Being Expanded

1. Check field name matches: `.fan_out(list_field="correct_field_name")`
2. Verify artifact actually contains a list
3. Ensure component is enabled (default: True)
4. Check logs for fan-out messages

### Type Derivation Issues

If types aren't derived correctly:

```python
# Explicitly configure type suffix
.fan_out(item_type_suffix="List")  # TaskList -> Task
```

### Memory Issues with Large Fan-Out

Limit expansion and use batching:

```python
.fan_out(max_items=100)  # Limit fan-out
```

This completes the implementation guide for the fan-out pattern in Flock.