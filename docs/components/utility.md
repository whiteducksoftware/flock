# Utility Components 🧰

Utility components provide cross‑cutting behavior for agents without changing their core logic. Common examples include:

- Output formatting (pretty printing, theming, streaming)
- Metrics/latency tracking and alerts
- Memory or context injection

These components inherit from `AgentComponent` and typically implement lifecycle hooks.

## Built‑in Examples

- `OutputUtilityComponent`
  - Formats and prints results; can render tables and control verbosity.
- `MetricsUtilityComponent`
  - Tracks latency/cost thresholds and emits warnings.

## Adding a Utility Component

```python
from pydantic import BaseModel, Field
from flock.core.registry import flock_component
from flock.core.component.agent_component_base import AgentComponent, AgentComponentConfig

class MyOutputConfig(AgentComponentConfig):
    shout: bool = Field(default=False)

@flock_component(name="my_output", config_class=MyOutputConfig)
class MyOutput(AgentComponent):
    config: MyOutputConfig

    async def on_post_evaluate(self, agent, inputs, context, result):
        if self.config.shout and isinstance(result, dict) and "text" in result:
            result["text"] = result["text"].upper()
        return result
```

Registering with `@flock_component` makes the component discoverable via the registry and serializable.

## When To Use Utility Components

- You want consistent output across many agents.
- You need metrics/telemetry without coupling it to evaluation logic.
- You need to adjust inputs/outputs around evaluation in a reusable way.
