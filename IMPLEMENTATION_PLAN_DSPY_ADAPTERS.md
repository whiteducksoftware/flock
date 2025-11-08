# Test-Driven Implementation Plan: DSPy Adapter Support

## Overview
Add support for configuring DSPy adapters in `DSPyEngine` to enable better structured output parsing, native function calling, and improved reliability.

## Test Plan

### Phase 1: Core Adapter Configuration (Tests First)

#### Test 1.1: Default Adapter Behavior
**File:** `tests/test_dspy_engine_adapter.py`

```python
@pytest.mark.asyncio
async def test_dspy_engine_defaults_to_chat_adapter():
    """DSPyEngine should default to ChatAdapter when no adapter specified."""
    engine = DSPyEngine(model="gpt-4")
    
    # Mock DSPy to capture adapter usage
    with patch('dspy.settings.adapter', None):
        # Verify ChatAdapter is used (via mock)
        # This ensures backward compatibility
        pass
```

#### Test 1.2: Custom Adapter Configuration
**File:** `tests/test_dspy_engine_adapter.py`

```python
@pytest.mark.asyncio
async def test_dspy_engine_accepts_custom_adapter():
    """DSPyEngine should accept and use custom adapter."""
    from dspy.adapters import JSONAdapter
    
    engine = DSPyEngine(model="gpt-4", adapter=JSONAdapter())
    assert engine.adapter is not None
    assert isinstance(engine.adapter, JSONAdapter)
```

#### Test 1.3: Adapter Passed to DSPy Context
**File:** `tests/test_dspy_engine_adapter.py`

```python
@pytest.mark.asyncio
async def test_adapter_passed_to_dspy_context(mocker):
    """Adapter should be passed to dspy.context() when executing."""
    mock_dspy = mocker.MagicMock()
    mock_context = mocker.MagicMock()
    mock_dspy.context.return_value.__enter__ = mocker.MagicMock(return_value=mock_context)
    mock_dspy.context.return_value.__exit__ = mocker.MagicMock(return_value=None)
    
    mocker.patch('flock.engines.dspy_engine.DSPyEngine._import_dspy', return_value=mock_dspy)
    
    from dspy.adapters import JSONAdapter
    engine = DSPyEngine(model="gpt-4", adapter=JSONAdapter())
    
    # Execute engine (mocked)
    # Verify dspy.context(adapter=JSONAdapter()) was called
```

### Phase 2: JSONAdapter Integration (Tests First)

#### Test 2.1: JSONAdapter Improves Parsing Reliability
**File:** `tests/test_dspy_engine_adapter.py`

```python
@pytest.mark.asyncio
async def test_json_adapter_improves_parsing(mocker):
    """JSONAdapter should provide more reliable parsing than ChatAdapter."""
    # Mock LLM response with malformed JSON
    # Verify JSONAdapter handles it better than ChatAdapter
    pass
```

#### Test 2.2: Native Function Calling Enabled
**File:** `tests/test_dspy_engine_adapter.py`

```python
@pytest.mark.asyncio
async def test_json_adapter_enables_native_function_calling(mocker):
    """JSONAdapter should enable native function calling by default."""
    from dspy.adapters import JSONAdapter
    
    engine = DSPyEngine(model="gpt-4", adapter=JSONAdapter())
    # Verify use_native_function_calling is True
    assert engine.adapter.use_native_function_calling is True
```

### Phase 3: Backward Compatibility (Tests First)

#### Test 3.1: Existing Code Works Without Changes
**File:** `tests/test_dspy_engine_adapter.py`

```python
@pytest.mark.asyncio
async def test_backward_compatibility_no_adapter_specified():
    """Existing code without adapter parameter should work unchanged."""
    engine = DSPyEngine(model="gpt-4")
    # Should default to ChatAdapter behavior
    assert engine.adapter is None  # Will use DSPy's default
```

#### Test 3.2: ChatAdapter Explicit Configuration
**File:** `tests/test_dspy_engine_adapter.py`

```python
@pytest.mark.asyncio
async def test_explicit_chat_adapter_configuration():
    """Users can explicitly set ChatAdapter if desired."""
    from dspy.adapters import ChatAdapter
    
    engine = DSPyEngine(model="gpt-4", adapter=ChatAdapter())
    assert isinstance(engine.adapter, ChatAdapter)
```

## Implementation Steps

### Step 1: Add Adapter Field to DSPyEngine
**File:** `src/flock/engines/dspy_engine.py`

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dspy.adapters import Adapter

class DSPyEngine(EngineComponent):
    # ... existing fields ...
    
    adapter: Adapter | None = Field(
        default=None,
        description=(
            "DSPy adapter to use for prompt formatting and response parsing. "
            "Defaults to ChatAdapter if not specified. "
            "Use JSONAdapter for better structured output reliability and native function calling."
        ),
    )
```

### Step 2: Pass Adapter to DSPy Context
**File:** `src/flock/engines/dspy_engine.py`

```python
async def _evaluate_internal(...):
    # ... existing code ...
    
    # Import adapter classes
    from dspy.adapters import ChatAdapter
    
    # Determine adapter to use
    adapter_to_use = self.adapter or ChatAdapter()
    
    with dspy_mod.context(lm=lm, adapter=adapter_to_use):
        program = self._choose_program(dspy_mod, signature, combined_tools)
        # ... rest of execution ...
```

### Step 3: Update Type Hints
**File:** `src/flock/engines/dspy_engine.py`

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dspy.adapters import Adapter
```

### Step 4: Add Tests
**File:** `tests/test_dspy_engine_adapter.py`

Create comprehensive test suite covering all test cases above.

### Step 5: Create Examples
**Files:** `examples/05-engines/`

#### Example 1: Adapter Comparison (`01_adapter_comparison.py`)
Demonstrate ChatAdapter vs JSONAdapter for structured output parsing:

```python
"""
DSPy Adapter Comparison: ChatAdapter vs JSONAdapter

This example demonstrates the difference between ChatAdapter (default)
and JSONAdapter for structured output parsing reliability.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from pydantic import BaseModel, Field
from flock import Flock, flock_type
from flock.engines import DSPyEngine
from dspy.adapters import ChatAdapter, JSONAdapter

USE_DASHBOARD = False

@flock_type
class AnalysisRequest(BaseModel):
    text: str = Field(description="Text to analyze")

@flock_type
class AnalysisResult(BaseModel):
    sentiment: str = Field(description="Sentiment: positive, negative, or neutral")
    confidence: float = Field(description="Confidence score 0.0-1.0")
    key_points: list[str] = Field(description="Key points extracted")

async def main():
    flock = Flock("openai/gpt-4o")
    
    # Agent with ChatAdapter (default)
    chat_agent = (
        flock.agent("chat_analyzer")
        .description("Analyze text using ChatAdapter")
        .consumes(AnalysisRequest)
        .publishes(AnalysisResult)
        .with_engines(
            DSPyEngine(
                model="openai/gpt-4o",
                adapter=ChatAdapter()  # Explicit ChatAdapter
            )
        )
    )
    
    # Agent with JSONAdapter (better parsing)
    json_agent = (
        flock.agent("json_analyzer")
        .description("Analyze text using JSONAdapter")
        .consumes(AnalysisRequest)
        .publishes(AnalysisResult)
        .with_engines(
            DSPyEngine(
                model="openai/gpt-4o",
                adapter=JSONAdapter()  # Better structured output parsing
            )
        )
    )
    
    request = AnalysisRequest(
        text="I love this product! It's amazing and works perfectly."
    )
    
    print("🔵 Testing ChatAdapter (default)...")
    await flock.publish(request, correlation_id="chat_test")
    await flock.run_until_idle()
    
    print("\n🟢 Testing JSONAdapter (structured outputs)...")
    await flock.publish(request, correlation_id="json_test")
    await flock.run_until_idle()
    
    print("\n✅ Both adapters completed! Check results above.")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Example 2: JSONAdapter with MCP Tools (`02_json_adapter_mcp_tools.py`)
Demonstrate JSONAdapter's native function calling with MCP tools:

```python
"""
DSPy JSONAdapter with MCP Tools: Native Function Calling

This example demonstrates JSONAdapter's native function calling feature
for better integration with MCP tools.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from pydantic import BaseModel, Field
from flock import Flock, flock_type
from flock.engines import DSPyEngine
from dspy.adapters import JSONAdapter

USE_DASHBOARD = False

@flock_type
class ResearchQuery(BaseModel):
    topic: str = Field(description="Research topic")
    depth: str = Field(default="medium", description="Research depth: shallow, medium, deep")

@flock_type
class ResearchReport(BaseModel):
    summary: str = Field(description="Research summary")
    sources: list[str] = Field(description="List of source URLs")
    findings: list[str] = Field(description="Key findings")

async def main():
    flock = Flock("openai/gpt-4o")
    
    # Register MCP servers (example: filesystem, github)
    # flock.add_mcp("filesystem", ...)
    # flock.add_mcp("github", ...)
    
    # Agent with JSONAdapter + MCP tools
    # JSONAdapter enables native function calling by default
    researcher = (
        flock.agent("researcher")
        .description("Research agent using JSONAdapter with native function calling")
        .consumes(ResearchQuery)
        .publishes(ResearchReport)
        .with_mcps(["filesystem", "github"])  # MCP tools available
        .with_engines(
            DSPyEngine(
                model="openai/gpt-4o",
                adapter=JSONAdapter()  # Native function calling enabled by default
            )
        )
    )
    
    query = ResearchQuery(
        topic="Python async/await best practices",
        depth="deep"
    )
    
    print("🔍 Researching with JSONAdapter + MCP tools...")
    await flock.publish(query)
    await flock.run_until_idle()
    
    print("\n✅ Research complete! JSONAdapter provides better tool integration.")

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 6: Update Documentation
**File:** `docs/guides/dspy-engine.md`

Add new section on adapter configuration:

```markdown
## DSPy Adapter Configuration

**DSPy adapters** control how prompts are formatted and responses are parsed. Flock's `DSPyEngine` supports configuring adapters for better reliability and features.

### Available Adapters

- **ChatAdapter** (default): Text-based parsing with `[[ ## field_name ## ]]` markers
- **JSONAdapter**: JSON-based parsing with structured outputs API support
- **XMLAdapter**: XML-based parsing
- **TwoStepAdapter**: Two-step generation process

### Using JSONAdapter

JSONAdapter provides several advantages:

- ✅ **Better Parsing Reliability**: Uses OpenAI's structured outputs API when supported
- ✅ **Native Function Calling**: Enabled by default for better MCP tool integration
- ✅ **More Robust**: Handles malformed JSON better than ChatAdapter

```python
from dspy.adapters import JSONAdapter
from flock.engines import DSPyEngine

agent = (
    flock.agent("analyst")
    .consumes(Data)
    .publishes(Report)
    .with_engines(
        DSPyEngine(
            model="openai/gpt-4o",
            adapter=JSONAdapter()  # Better structured output parsing
        )
    )
)
```

### Using ChatAdapter (Default)

ChatAdapter is the default adapter and works with any LLM:

```python
from dspy.adapters import ChatAdapter

agent = (
    flock.agent("analyst")
    .consumes(Data)
    .publishes(Report)
    .with_engines(
        DSPyEngine(
            model="openai/gpt-4o",
            adapter=ChatAdapter()  # Explicit default
        )
    )
)
```

### Adapter with MCP Tools

JSONAdapter's native function calling works seamlessly with MCP tools:

```python
from dspy.adapters import JSONAdapter

agent = (
    flock.agent("researcher")
    .consumes(Query)
    .publishes(Report)
    .with_mcps(["filesystem", "github"])
    .with_engines(
        DSPyEngine(
            model="openai/gpt-4o",
            adapter=JSONAdapter()  # Native function calling enabled
        )
    )
)
```

### When to Use Which Adapter

| Scenario | Recommended Adapter | Why |
|----------|-------------------|-----|
| Structured outputs needed | JSONAdapter | Better parsing reliability |
| MCP tools integration | JSONAdapter | Native function calling enabled |
| Any LLM compatibility | ChatAdapter | Works with all models |
| Simple use cases | ChatAdapter (default) | No configuration needed |

### Examples

- **[Adapter Comparison](../examples/05-engines/01_adapter_comparison.py)** - Compare ChatAdapter vs JSONAdapter
- **[JSONAdapter with MCP Tools](../examples/05-engines/02_json_adapter_mcp_tools.py)** - Native function calling example
```

**File:** `examples/05-engines/README.md`

Add entries for new adapter examples:

```markdown
### 01_adapter_comparison.py 🔄
**Pattern:** Compare ChatAdapter vs JSONAdapter for structured output parsing

Demonstrates the difference between adapters:
- **ChatAdapter**: Default adapter, text-based parsing
- **JSONAdapter**: Better structured output parsing, native function calling

```bash
uv run python examples/05-engines/01_adapter_comparison.py
```

**Use Cases:**
- Understanding adapter differences
- Choosing the right adapter for your use case
- Improving parsing reliability

### 02_json_adapter_mcp_tools.py 🔧
**Pattern:** JSONAdapter with MCP tools and native function calling

Demonstrates JSONAdapter's native function calling feature:
- **Native function calling**: Enabled by default in JSONAdapter
- **MCP tool integration**: Better tool calling with MCP servers
- **Structured outputs**: More reliable parsing

```bash
uv run python examples/05-engines/02_json_adapter_mcp_tools.py
```

**Use Cases:**
- MCP tool integration
- Research agents with tool calling
- Agents that need reliable structured outputs
```

## Success Criteria

1. ✅ `DSPyEngine` accepts optional `adapter` parameter
2. ✅ Adapter is passed to `dspy.context()` during execution
3. ✅ Default behavior unchanged (backward compatible)
4. ✅ JSONAdapter can be used for better structured outputs
5. ✅ All tests pass
6. ✅ Documentation updated with adapter section
7. ✅ Two examples created demonstrating adapter usage
8. ✅ Examples README updated

## Migration Path

**Phase 1:** Core implementation (adapter parameter + context passing)
**Phase 2:** Tests and validation
**Phase 3:** Documentation and examples
**Phase 4:** Consider making JSONAdapter default in future version

## Notes

- This is a **non-breaking change** - all existing code continues to work
- Adapter parameter is optional - defaults to DSPy's behavior (ChatAdapter)
- Users can opt-in to JSONAdapter for better reliability
- Future: Could consider making JSONAdapter the default in a future major version

