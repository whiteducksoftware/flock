---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# `FlockAgent` Class Reference

The canonical location of the class is `flock.core.flock_agent.FlockAgent`.

```python
class FlockAgent(BaseModel, Serializable, DSPyIntegrationMixin, ABC):
    name: str
    model: str | None = None
    description: str | Callable[..., str] | None = ""
    input: SignatureType
    output: SignatureType
    tools: list[Callable] | None = None
    write_to_file: bool = False
    wait_for_input: bool = False
    evaluator: FlockEvaluator | None = None
    handoff_router: FlockRouter | None = None
    modules: dict[str, FlockModule] = {}
    temporal_activity_config: TemporalActivityConfig | None = None
```

---

## 1. Constructor Arguments

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `str` | **required** | Unique ID for the agent and registry key. |
| `model` | `str \| None` | `None` | Overrides the Flock-level default model. |
| `description` | `str \| Callable` | `""` | High-level instructions injected into the prompt. |
| `input` | `SignatureType` | `None` | Contract for inputs (string DSL, Pydantic model, or callable). |
| `output` | `SignatureType` | `None` | Contract for outputs. |
| `tools` | `list[Callable]` | `None` | Additional capabilities accessible during evaluation. |
| `write_to_file` | `bool` | `False` | Persist result to `output/*` as JSON. |
| `wait_for_input` | `bool` | `False` | Pause execution and await user input in CLI mode. |
| `evaluator` | `FlockEvaluator` | `None` | Logic implementation (defaults to DeclarativeEvaluator in factories). |
| `handoff_router` | `FlockRouter` | `None` | Determines next agent, enabling dynamic flows. |
| `modules` | `dict[str, FlockModule]` | `{}` | Lifecycle extensions. |
| `temporal_activity_config` | `TemporalActivityConfig` | `None` | Override activity timeouts/retries when using Temporal.

---

## 2. Key Methods

| Method | Description |
| ------ | ----------- |
| `add_module(module)` | Attach a `FlockModule` after instantiation. |
| `remove_module(name)` | Detach a module by name. |
| `set_model(model)` | Change the LLM to use for future runs. |
| `async run_async(inputs, context=None)` | Convenience method to execute **this agent only**. |
| `to_dict()` / `from_dict()` | Lossless (de)serialization via `Serializable`. |

### Lifecycle Hooks (called by orchestrator)

* `async initialize(inputs, context)`
* `async evaluate(inputs, context)` – implemented by evaluator.
* `async terminate(result, context)`
* `async on_error(error, context)`

Modules can hook into each stage.

---

## 3. Serialization Guarantees

* All public fields are serialised via Pydantic.
* Callable components are stored as **path strings** (`module.ClassName`).
* Custom classes must be registered with `@flock_component` to round-trip.

---

## 4. Example

```python
from flock.core import Flock, FlockFactory

agent = FlockFactory.create_default_agent(
    name="title_case",
    input="text: str",
    output="title: str"
)

flock = Flock(agents=[agent])
print(flock.run(start_agent="title_case", input={"text": "hello world"}).title)
```

---

For conceptual background see [Agents](../core-concepts/agents.md).
