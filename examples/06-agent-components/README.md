# 🔧 Agent Components

Agent components add per-agent behavior through lifecycle hooks—perfect for validation, metrics, quality gates, retry logic, and cross-cutting concerns at the individual agent level.

## 🎯 What Are Agent Components?

**Agent Components** extend individual agents with custom behavior at specific lifecycle points:

- **Per-agent scope** - Each agent can have its own components
- **Lifecycle hooks** - Hook into initialization, consumption, evaluation, publishing
- **Stateful** - Components can maintain state across executions
- **Composable** - Multiple components can be attached to one agent

## 💡 Why Use Agent Components?

| Without Components | With Components |
|-------------------|-----------------|
| ❌ Scattered logic | ✅ Organized hooks |
| ❌ Duplicate code | ✅ Reusable patterns |
| ❌ Hard to test | ✅ Testable isolation |
| ❌ Limited observability | ✅ Built-in metrics/logs |

**Use components when:**
- You need per-agent quality gates
- Validating inputs before evaluation
- Tracking agent-specific metrics
- Implementing retry logic
- Adding logging/debugging
- Modifying agent state dynamically

## 📚 Examples

### cheer_meter_component.py 👏
**Pattern:** Track metrics and modify evaluation state dynamically

Build energy tracking that influences agent behavior:
- **State tracking** - Count successful executions
- **Dynamic metrics** - Calculate crowd energy
- **State injection** - Pass metrics to engine logic
- **Post-publish hooks** - React to artifact publication

```bash
uv run 06-agent-components/cheer_meter_component.py
```

**How It Works:**
```python
class CheerMeterComponent(AgentComponent):
    applause_level: int = 0

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        # Track successful pitches
        self.applause_level += 1
        crowd_energy = min(1.0, self.applause_level / 5)

        # Inject metrics into result
        result.metrics["crowd_energy"] = crowd_energy
        result.state["crowd_energy"] = crowd_energy  # ← Engine can access this!
        result.logs.append(f"Crowd energy surged to {crowd_energy:.2f}")

        return result

    async def on_post_publish(self, agent, ctx, artifact):
        print(f"👏 Crowd erupts for: {artifact.payload.get('tagline')}")

# Engine can read state set by component
class PepTalkEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs):
        crowd_energy = ctx.state.get("crowd_energy", 0.0)

        if crowd_energy >= 0.6:
            closer = "The standing ovation continues!"
        else:
            closer = "Imagine the applause..."

        return EvalResult.from_object(...)
```

**Lifecycle Hooks Used:**
1. `on_post_evaluate` - After evaluation, inject metrics
2. `on_post_publish` - After publishing, celebrate

**Use Cases:**
- **Confidence scoring** - Track quality over time
- **Dynamic prompting** - Adjust based on performance
- **Quality gates** - Block publishing if criteria not met
- **Metrics collection** - Track agent KPIs

---

### plot_twist_component.py 🌙
**Pattern:** Pre-evaluation state injection and contextual processing

Add foreshadowing hints before evaluation runs:
- **Pre-evaluation hooks** - Modify inputs before processing
- **Genre-based logic** - Context-aware behavior
- **Stateful counting** - Track how many times triggered
- **State passing** - Inject data for engine to use

```bash
uv run 06-agent-components/plot_twist_component.py
```

**How It Works:**
```python
class ForeshadowingComponent(AgentComponent):
    sprinkle_count: int = 0

    GENRE_CLUES = {
        "mystery": [
            "A pocket watch ticks backwards somewhere off-stage.",
            "Someone misplaced a single chess piece—intentionally.",
        ],
        "comedy": [
            "A banana peel in act one never goes unused.",
            "Someone swapped the hero's script with a karaoke playlist.",
        ],
        "fantasy": [
            "The moon blushes a shade deeper than usual.",
            "A prophecy scribbles in the margins on its own.",
        ],
    }

    async def on_pre_evaluate(self, agent, ctx, inputs):
        # Extract genre from input
        idea = StoryIdea(**inputs.artifacts[0].payload)
        clue = self._choose_clue(idea.genre.lower())

        # Inject foreshadowing hint into state
        self.sprinkle_count += 1
        inputs.state["foreshadow"] = clue
        inputs.state["sprinkle_count"] = self.sprinkle_count

        return inputs  # ← Modified inputs passed to engine

# Engine receives pre-injected state
class CampfireStoryEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs):
        idea = inputs.first_as(StoryIdea)

        # Access state set by component
        foreshadow = inputs.state.get("foreshadow")
        sprinkle_count = inputs.state.get("sprinkle_count", 0)

        # Use in processing
        beat = StoryBeat(
            synopsis=f"{idea.hero} pursues {idea.goal}...",
            foreshadowing=foreshadow,  # ← Injected by component!
            surprise=f"Twist #{sprinkle_count}: ..."
        )

        return EvalResult.from_object(beat, agent=agent)
```

**Lifecycle Hooks Used:**
1. `on_pre_evaluate` - Before evaluation, inject contextual hints

**Use Cases:**
- **Input enrichment** - Add context before processing
- **Dynamic prompting** - Modify prompts based on conditions
- **A/B testing** - Inject different variants
- **Context injection** - Add user preferences, history, etc.

---

## 🔑 Key Concepts

### Agent Component Lifecycle

Components can hook into these agent lifecycle events:

```python
class MyComponent(AgentComponent):
    async def on_initialize(self, agent, ctx):
        """Called when agent is initialized"""
        pass

    async def on_pre_consume(self, agent, ctx):
        """Called before agent checks for work"""
        pass

    async def on_pre_evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalInputs:
        """Called before evaluation - can modify inputs"""
        return inputs

    async def on_post_evaluate(self, agent, ctx, inputs, result: EvalResult) -> EvalResult:
        """Called after evaluation - can modify result"""
        return result

    async def on_post_publish(self, agent, ctx, artifact):
        """Called after artifact is published"""
        pass

    async def on_terminate(self, agent, ctx):
        """Called when agent is terminated"""
        pass
```

### Attaching Components to Agents

```python
from flock.components import AgentComponent

flock = Flock()

(
    flock.agent("my_agent")
    .consumes(Input)
    .publishes(Output)
    .with_utilities(
        MyComponent(),
        AnotherComponent()
    )
)
```

### Multiple Components

Agents can have multiple components - they execute in order:

```python
agent.with_utilities(
    ValidationComponent(),   # Runs first
    MetricsComponent(),      # Runs second
    LoggingComponent()       # Runs third
)
```

### Stateful Components

Components can maintain state across executions:

```python
class CounterComponent(AgentComponent):
    count: int = Field(default=0)

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        self.count += 1  # Persists across calls
        result.metrics["execution_count"] = self.count
        return result
```

## 🎓 Component Patterns

### Quality Gate Pattern
Block publishing if quality criteria not met:

```python
class QualityGateComponent(AgentComponent):
    async def on_post_evaluate(self, agent, ctx, inputs, result):
        if hasattr(result.value, 'confidence'):
            if result.value.confidence < 0.7:
                result.artifacts = []  # Block publishing
                result.logs.append("❌ Quality gate failed: low confidence")
        return result
```

### Retry Pattern
Retry on failure with exponential backoff:

```python
class RetryComponent(AgentComponent):
    max_retries: int = 3

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        if result.error and ctx.retry_count < self.max_retries:
            await asyncio.sleep(2 ** ctx.retry_count)
            # Trigger retry logic
        return result
```

### Validation Pattern
Validate inputs before processing:

```python
class ValidationComponent(AgentComponent):
    async def on_pre_evaluate(self, agent, ctx, inputs):
        # Validate inputs
        if not inputs.artifacts:
            raise ValueError("No input artifacts")

        # Add validation metadata
        inputs.state["validated_at"] = datetime.now()
        return inputs
```

### Metrics Collection Pattern
Track agent performance:

```python
class MetricsComponent(AgentComponent):
    execution_times: list[float] = Field(default_factory=list)

    async def on_pre_evaluate(self, agent, ctx, inputs):
        ctx.state["start_time"] = time.time()
        return inputs

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        duration = time.time() - ctx.state.get("start_time", 0)
        self.execution_times.append(duration)
        result.metrics["avg_duration"] = sum(self.execution_times) / len(self.execution_times)
        return result
```

## 🎯 When to Use Components vs Engines

| Feature | Agent Component | Engine Component |
|---------|----------------|------------------|
| **Scope** | Per-agent lifecycle | Evaluation only |
| **Purpose** | Cross-cutting concerns | Core business logic |
| **State** | Maintain across calls | Stateless processing |
| **Hooks** | Many lifecycle points | One (evaluate) |
| **Examples** | Validation, metrics, retry | Transformation, calculation |

**Rule of thumb:**
- Use **Engine** for "what to compute"
- Use **Agent Component** for "how to behave"

## 🚀 Advanced Patterns

### Conditional Behavior
```python
class ConditionalComponent(AgentComponent):
    async def on_pre_evaluate(self, agent, ctx, inputs):
        if ctx.environment == "production":
            inputs.state["strict_mode"] = True
        return inputs
```

### Dynamic Configuration
```python
class ConfigurableComponent(AgentComponent):
    threshold: float = Field(default=0.7)

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        if result.confidence < self.threshold:
            result.logs.append(f"⚠️ Below threshold {self.threshold}")
        return result

# Use with different thresholds
strict_agent.with_utilities(ConfigurableComponent(threshold=0.9))
lenient_agent.with_utilities(ConfigurableComponent(threshold=0.5))
```

### Chaining Components
```python
# Components execute in order, passing modified results
agent.with_utilities(
    ValidationComponent(),    # Validates inputs
    EnrichmentComponent(),    # Adds context
    MetricsComponent(),       # Tracks performance
    LoggingComponent()        # Logs everything
)
```

## 📖 Related Examples

- **03-claudes-workshop/lesson_12_confidence_booster.py** - Workshop lesson on agent components
- **05-engines/** - Custom processing logic (different scope)
- **07-orchestrator-components/** - Global coordination patterns

## 📚 Documentation

- [Agent Components Guide](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/guides/components.md)
- [Agent Guide](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/guides/agents.md)
- AGENTS.md - "Components" section

---

**Ready to extend your agents? Start with cheer_meter_component! 👏**
