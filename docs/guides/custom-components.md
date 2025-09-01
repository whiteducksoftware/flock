# Writing Custom Components ⚙️

This guide shows how to implement your own Evaluation, Routing, or Utility components and register them with Flock.

## Evaluation Component

```python
from flock.core.component.evaluation_component import EvaluationComponent
from flock.core.registry import flock_component

@flock_component
class MyEvaluator(EvaluationComponent):
    async def evaluate_core(self, agent, inputs, context=None, tools=None, mcp_tools=None):
        # do work here
        return {"result": inputs.get("text", "").upper()}
```

## Routing Component

```python
from flock.core.component.routing_component import RoutingComponent
from flock.core.registry import flock_component

@flock_component
class ThresholdRouter(RoutingComponent):
    async def determine_next_step(self, agent, result, context=None):
        score = result.get("score", 0)
        return "high_score_agent" if score > 0.8 else None
```

## Utility Component

```python
from pydantic import Field
from flock.core.component.agent_component_base import AgentComponent, AgentComponentConfig
from flock.core.registry import flock_component

class CapsConfig(AgentComponentConfig):
    enable: bool = Field(default=True)

@flock_component(config_class=CapsConfig)
class CapsUtility(AgentComponent):
    config: CapsConfig
    async def on_post_evaluate(self, agent, inputs, context, result):
        if self.config.enable and isinstance(result, dict) and "text" in result:
            result["text"] = result["text"].upper()
        return result
```

## Registering Types and Tools

- Use `@flock_type` on Pydantic models to register schemas used in contracts.
- Use `@flock_tool` to register callables the evaluator can call.

## Tips

- Keep components focused (single responsibility).
- Prefer Pydantic configs for tunable behavior.
- Make external calls async.
