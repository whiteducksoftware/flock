---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Evaluators 🧑‍⚖️

Evaluators are responsible for **turning an agent's declarative specification into actual work**.  They live inside the agent instance (`agent.evaluator`) and must implement the async method:

```python
async def evaluate(self, agent: FlockAgent, inputs: dict, tools: list[Callable]) -> dict:  ...
```

The returned dict is validated against the agent's `output` signature.

---

## 1. Built-in Evaluators

| Class | Location | Description |
| ----- | -------- | ----------- |
| `DeclarativeEvaluator` | `flock.evaluators.declarative` | Default.  Generates a prompt from the agent's signatures and calls `litellm`.
| `DSPyEvaluator` | `flock.evaluators.dspy` | Integrates with [DSPy](https://github.com/stanfordnlp/dspy) for structured prompting & optimisation.
| `RuleEvaluator` | `flock.evaluators.rule` | Pure-Python rules engine (no LLM). Useful for testing. |

---

## 2. Configuring Evaluators

All evaluators accept a `*Config` dataclass (Pydantic model) with relevant fields.  Example for Declarative:

```python
from flock.evaluators.declarative import DeclarativeEvaluator, DeclarativeEvaluatorConfig

config = DeclarativeEvaluatorConfig(
    model="anthropic/claude-3-opus",
    temperature=0.2,
    max_tokens=2048,
    stream=True,
    include_thought_process=False,
    use_cache=True,
)

evaluator = DeclarativeEvaluator(name="default", config=config)
```

You can then inject the evaluator when you instantiate the agent or replace it later:

```python
agent.evaluator = evaluator  # hot-swap!
```

---

## 3. Writing a Custom Evaluator

1. Subclass `FlockEvaluator` and optionally declare a `FlockEvaluatorConfig`.
2. Implement `async evaluate(self, agent, inputs, tools)`.
3. Register with the registry (optional) for serialization:

```python
from flock.core import flock_component

@flock_component
class MyCoolEvaluator(FlockEvaluator):
    async def evaluate(self, agent, inputs, tools):
        # do stuff…
        return {"answer": "42"}
```

---

## 4. Best Practices

* Respect the `model` selected on the agent unless your evaluator has a reason to override.
* Validate inputs early; raise `ValueError` to trigger `on_error` hooks.
* Make expensive network calls **async** to keep the event loop responsive.
* Return only the fields declared in the output signature (extra fields are dropped).

---

➡️ Continue to [Modules](modules.md) to see how to augment agent behaviour.
