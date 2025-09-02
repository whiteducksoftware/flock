---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Evaluation Components 🧠

Evaluation components implement the agent’s core logic. The default option uses DSPy for structured prompting and tool use.

## DeclarativeEvaluationComponent (default)

Created when you construct a `DefaultAgent`, it converts your contracts into a DSPy signature and runs a suitable program (`Predict`, `ReAct`, or `ChainOfThought`).

### Highlights
- Honors `description`, `input`, and `output` (string or Pydantic) contracts
- Supports streaming output and optional reasoning/trajectory fields
- Integrates native Python tools and MCP tools

### Example
```python
from flock.core import DefaultAgent

agent = DefaultAgent(
    name="summarizer",
    description="Summarize the provided text",
    input="text: str",
    output="summary: str | A concise abstract"
)
```

## Custom Evaluation Components

Subclass `EvaluationComponent` and implement `evaluate_core`.

```python
from flock.core.component.evaluation_component import EvaluationComponent
from flock.core.registry import flock_component

@flock_component
class MyEvaluator(EvaluationComponent):
    async def evaluate_core(self, agent, inputs, context=None, tools=None, mcp_tools=None):
        return {"result": inputs.get("text", "").upper()}
```

Register via `@flock_component` for discovery and serialization.

## Best Practices

- Respect the agent’s `model` unless you have a strong reason to override.
- Validate inputs early; raise errors to trigger `on_error` hooks.
- Make network calls async.
- Return only declared output fields; keep responses compact and structured.
