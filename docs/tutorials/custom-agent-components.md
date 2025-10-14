# Custom Agent Components: Foreshadow & Hype

Agent components let you bend an agent’s behaviour without touching its core engine. In this tutorial you’ll meet two companions:

- **ForeshadowingComponent** – slips clues into state before the engine runs.
- **CheerMeterComponent** – keeps track of crowd energy after each pitch.

Both examples live in `examples/06-agent-components/` so you can run and remix them immediately.

---

## 1. Foreshadowing before the punchline

Run the example:

```bash
uv run python examples/06-agent-components/plot_twist_component.py
```

Walkthrough:

1. `ForeshadowingComponent` extends `AgentComponent` and overrides `on_pre_evaluate`.
2. The component inspects the incoming `StoryIdea`, chooses a genre-specific clue, and saves it into `inputs.state`.
3. `CampfireStoryEngine` pulls that hint from `inputs.state` to sprinkle foreshadowing into the final `StoryBeat`.

Snippet:

```python
class ForeshadowingComponent(AgentComponent):
    async def on_pre_evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalInputs:
        idea = StoryIdea(**inputs.artifacts[0].payload)
        clue = self._choose_clue(idea.genre.lower())

        self.sprinkle_count += 1
        inputs.state["foreshadow"] = clue
        inputs.state["sprinkle_count"] = self.sprinkle_count
        return inputs
```

Why it works:

- Components mutate `EvalInputs` before the engine executes.
- State keys survive the call chain, enabling lightweight coordination tricks.
- You can keep private counters (`sprinkle_count`) on the component instance for running totals.

Try it yourself:

1. Add a new genre (e.g., “sci-fi”) to the clue table.
2. Modify the engine to branch on `sprinkle_count` for escalating twists.
3. Log the clue to `ctx` for tracing-friendly observability.

---

## 2. Measuring crowd energy after each pitch

Run the example:

```bash
uv run python examples/06-agent-components/cheer_meter_component.py
```

Walkthrough:

1. `CheerMeterComponent` overrides `on_post_evaluate` and `on_post_publish`.
2. After each engine run it increments an `applause_level`, stores a normalized `crowd_energy` metric, and appends a log entry.
3. The engine then uses `ctx.state["crowd_energy"]` to switch between mellow and high-energy closing lines.

Snippet:

```python
class CheerMeterComponent(AgentComponent):
    async def on_post_evaluate(
        self, agent, ctx, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        self.applause_level += 1
        crowd_energy = min(1.0, self.applause_level / 5)

        result.metrics["crowd_energy"] = crowd_energy
        result.logs.append(f"Crowd energy surged to {crowd_energy:.2f}")
        result.state["crowd_energy"] = crowd_energy
        return result
```

Why it works:

- Post-evaluate hooks can modify metrics, logs, or state before outputs reach the blackboard.
- `on_post_publish` is perfect for side-channel effects (printing, instrumentation, telemetry).
- Metrics added here surface automatically in tracing dashboards.

Try it yourself:

1. Replace the print in `on_post_publish` with a Slack webhook call.
2. Reset `applause_level` whenever `crowd_energy` hits 1.0 to simulate encore cycles.
3. Attach the component to multiple agents to compare how each pitch deck performs.

---

## Choosing the right hook

| Hook | When it runs | Great for |
|------|--------------|-----------|
| `on_pre_consume` | Before subscription filtering | Mutating incoming artifacts |
| `on_pre_evaluate` | Before engine logic | Setting up state, caching, guardrails |
| `on_post_evaluate` | After engine returns | Metrics, logs, result shaping |
| `on_post_publish` | After artifacts hit the board | Notifications, analytics |
| `on_error` | When an exception bubbles up | Cleanup, fallbacks, telemetry |

Remember that components are regular Pydantic models, so you can inject configuration fields, defaults, and type validation effortlessly.

Next steps:

- Pair these components with tracing (`FLOCK_AUTO_TRACE=true`) to watch state flow through every hook.
- Mix and match multiple components on a single agent to build rich behaviours without touching engine code.
- Dive deeper into lifecycle hooks in the [Agent Components Guide](../guides/components.md).
