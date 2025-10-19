---
title: Quick Start Guide
description: Build your first Flock agent in 5 minutes with zero prompts and zero graph wiring
tags:
  - getting started
  - tutorial
  - beginner
  - quick start
search:
  boost: 3
---

# Quick Start

Build your first Flock agent in 5 minutes. **Zero prompts. Zero graph wiring. Just type contracts.**

---

## Installation (30 Seconds)

```bash
pip install flock-core

# Set your API key
export OPENAI_API_KEY="sk-..."

# Optional: Set default model (defaults to gpt-4.1 if unset)
export DEFAULT_MODEL="openai/gpt-4.1"
```

**That's it.** Flock works with any LiteLLM-supported model (OpenAI, Anthropic, Azure, local models, etc.).

---

## Your First Agent (60 Seconds)

**Create `pizza_master.py`:**

```python
import asyncio
from pydantic import BaseModel
from flock import Flock, flock_type

# 1. Define input and output types
@flock_type
class PizzaIdea(BaseModel):
    description: str

@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    instructions: list[str]

# 2. Create orchestrator and agent
flock = Flock("openai/gpt-4.1")

pizza_master = (
    flock.agent("pizza_master")
    .consumes(PizzaIdea)
    .publishes(Pizza)
)

# 3. Run it
async def main():
    await flock.publish(PizzaIdea(description="truffle pizza"))
    await flock.run_until_idle()

    # Get results
    pizzas = await flock.store.get_by_type(Pizza)
    print(f"✅ Pizza created: {pizzas[0].ingredients[:3]}...")

asyncio.run(main())
```

**Run it:**
```bash
python pizza_master.py
```

**Expected output:**
```
✅ Pizza created: ['truffle oil', 'mozzarella cheese', 'parmesan']...
```

---

## What Just Happened?

**No prompts written.** The `Pizza` schema defined the output structure:
```python
class Pizza(BaseModel):
    ingredients: list[str]  # LLM knows to list ingredients
    size: str              # LLM picks appropriate size
    crust_type: str        # LLM chooses crust style
    instructions: list[str] # LLM generates step-by-step
```

**How it works:**
1. You published `PizzaIdea` to the blackboard
2. `pizza_master` subscribed to `PizzaIdea`, so it activated
3. LLM transformed input → output based on schemas alone
4. Pydantic validated the output (type-safe!)
5. Result stored on blackboard

**The schema IS the instruction.** No 500-line prompt. No "You are a helpful assistant...". Just clean type contracts.

---

## Add Multi-Agent Workflow (2 Minutes)

Agents coordinate automatically through type subscriptions:

```python
# Agent 1: Generate pizza idea
idea_generator = (
    flock.agent("idea_generator")
    .consumes(Topic)
    .publishes(PizzaIdea)
)

# Agent 2: Create pizza from idea (from previous example)
pizza_master = (
    flock.agent("pizza_master")
    .consumes(PizzaIdea)
    .publishes(Pizza)
)

# Agent 3: Quality check the pizza
critic = (
    flock.agent("critic")
    .consumes(Pizza)
    .publishes(PizzaReview)
)

# Publish once, agents cascade automatically
await flock.publish(Topic(name="Italian cuisine"))
await flock.run_until_idle()
```

**What happens:**
```
Time 0: Publish Topic("Italian cuisine")
Time 1: idea_generator executes → publishes PizzaIdea
Time 2: pizza_master executes → publishes Pizza
Time 3: critic executes → publishes PizzaReview
Time 4: Done!
```

**No edges defined.** Workflow emerged from type subscriptions:
- `idea_generator` subscribed to `Topic`
- `pizza_master` subscribed to `PizzaIdea`
- `critic` subscribed to `Pizza`

---

## Parallel Execution (1 Minute)

Multiple agents processing the same type run concurrently:

```python
# Both analyze the same pizza
nutrition_analyzer = (
    flock.agent("nutrition")
    .consumes(Pizza)
    .publishes(NutritionInfo)
)

allergy_checker = (
    flock.agent("allergies")
    .consumes(Pizza)
    .publishes(AllergyWarnings)
)

# Aggregator waits for both
safety_report = (
    flock.agent("safety")
    .consumes(NutritionInfo, AllergyWarnings)
    .publishes(SafetyReport)
)

# Publish pizza, agents execute in parallel!
await flock.publish(pizza)
await flock.run_until_idle()
```

**Timeline:**
```
Time 0: Publish Pizza
Time 1: nutrition_analyzer + allergy_checker run IN PARALLEL ⚡
Time 2: safety_report waits for both...
Time 3: safety_report executes when both complete ✅
```

**Automatic parallelism.** Both agents subscribed to `Pizza`, so Flock ran them concurrently.

**Automatic dependencies.** `safety_report` needs both inputs, so Flock waited for both.

---

## Real-Time Dashboard (30 Seconds)

Watch agents execute live:

```python
async def main():
    # Start dashboard instead of manual execution
    await flock.serve(dashboard=True)
```

**What you get:**
- Real-time agent visualization
- Watch status change: idle → running → idle
- See data flow on blackboard
- Publish artifacts from UI (no code needed!)
- Live streaming LLM output

<p align="center">
  <img alt="Flock Dashboard" src="../img/flock_ui_agent_view.png" width="800">
  <i>Agent View: See communication patterns in real-time</i>
</p>

**Keyboard shortcuts:**
- `Ctrl+M` - Toggle Agent View ↔ Blackboard View
- `Ctrl+F` - Focus filter search
- `Ctrl+P` - Publish artifact from UI

[**👉 Full dashboard guide**](../guides/dashboard.md)

---

## Advanced Features (1 Minute Each)

### Conditional Consumption

Agents can filter artifacts:

```python
# Only process highly-rated pizzas
premium_service = (
    flock.agent("premium")
    .consumes(Pizza, where=lambda p: p.rating >= 9)
    .publishes(PremiumPackaging)
)
```

### Batch Processing

Wait for multiple artifacts:

```python
from datetime import timedelta
from flock.specs import BatchSpec

# Analyze 10 reviews at once
trend_analyzer = (
    flock.agent("trends")
    .consumes(
        PizzaReview,
        batch=BatchSpec(size=10, timeout=timedelta(seconds=30))
    )
    .publishes(TrendReport)
)
```

### Visibility Controls (Security)

Control who sees what:

```python
from flock.core.visibility import PrivateVisibility

# Only specific agents can see this
sensitive_data = (
    flock.agent("processor")
    .publishes(
        SensitiveInfo,
        visibility=PrivateVisibility(agents={"authorized_agent"})
    )
)
```

### Production Safety

Prevent infinite loops:

```python
# Circuit breaker: Stop after 1000 executions
flock = Flock("openai/gpt-4.1", max_agent_iterations=1000)

# Prevent self-triggering
critic = (
    flock.agent("critic")
    .consumes(Essay)
    .publishes(Critique)
    .prevent_self_trigger(True)  # Won't consume its own output
)
```

---

## Enable Tracing (30 Seconds)

Production-grade observability:

```bash
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true  # Store in .flock/traces.duckdb
```

```python
# Wrap workflows for unified traces
async with flock.traced_run("pizza_workflow"):
    await flock.publish(pizza_idea)
    await flock.run_until_idle()
```

**Open dashboard → Trace Viewer tab:**
- Timeline view (waterfall visualization)
- Statistics (duration, errors)
- RED Metrics (rate, errors, duration)
- Dependencies (agent communication graph)
- SQL queries (DuckDB analytics)

[**👉 Full tracing guide**](../guides/tracing/index.md)

---

## Complete Working Example

**Save as `pizza_workflow.py`:**

```python
import asyncio
from pydantic import BaseModel, Field
from flock import Flock, flock_type

@flock_type
class PizzaIdea(BaseModel):
    description: str

@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    instructions: list[str]

@flock_type
class Review(BaseModel):
    score: int = Field(ge=1, le=10)
    comments: str

flock = Flock("openai/gpt-4.1")

# Agent 1: Create pizza from idea
pizza_master = (
    flock.agent("pizza_master")
    .description("Expert pizza chef creating recipes")
    .consumes(PizzaIdea)
    .publishes(Pizza)
)

# Agent 2: Review the pizza
critic = (
    flock.agent("critic")
    .description("Harsh food critic reviewing pizzas")
    .consumes(Pizza)
    .publishes(Review)
)

async def main():
    # Method 1: Run with dashboard (interactive)
    await flock.serve(dashboard=True)

    # Method 2: Run programmatically
    # await flock.publish(PizzaIdea(description="spicy Hawaiian"))
    # await flock.run_until_idle()
    #
    # reviews = await flock.store.get_by_type(Review)
    # print(f"✅ Score: {reviews[0].score}/10")
    # print(f"💬 Comments: {reviews[0].comments}")

asyncio.run(main())
```

**Run with dashboard:**
```bash
python pizza_workflow.py
# Browser opens to http://localhost:8344
# Click "Publish" → Select PizzaIdea → Enter "truffle pizza" → Publish
# Watch agents execute in real-time!
```

**Run programmatically:**
```bash
# Uncomment Method 2 in the code above
python pizza_workflow.py
```

**Expected output:**
```
✅ Score: 9/10
💬 Comments: Excellent use of truffle oil, perfectly balanced with fresh mozzarella...
```

---

## Common Patterns

### Sequential Pipeline (A → B → C)

```python
writer = flock.agent("writer").consumes(Topic).publishes(Draft)
editor = flock.agent("editor").consumes(Draft).publishes(EditedDraft)
publisher = flock.agent("publisher").consumes(EditedDraft).publishes(Article)

# Workflow: Topic → Draft → EditedDraft → Article
```

### Parallel-Then-Join (A+B → C)

```python
bug_detector = flock.agent("bugs").consumes(Code).publishes(BugReport)
security = flock.agent("security").consumes(Code).publishes(SecurityReport)
reviewer = flock.agent("reviewer").consumes(BugReport, SecurityReport).publishes(FinalReview)

# Both bug_detector and security run in parallel
# reviewer waits for both, then executes
```

### Fan-Out (A → B1, B2, ..., Bn)

```python
editor = flock.agent("editor").consumes(Topic).publishes(StoryIdea)

# 8 journalists process StoryIdeas in parallel
for i in range(8):
    journalist = flock.agent(f"journalist_{i}").consumes(StoryIdea).publishes(Article)

# editor produces multiple StoryIdeas
# All journalists process them concurrently
```

### Conditional Routing

```python
urgent_handler = flock.agent("urgent").consumes(
    BugReport,
    where=lambda bug: bug.severity in ["Critical", "High"]
).publishes(UrgentResponse)

normal_handler = flock.agent("normal").consumes(
    BugReport,
    where=lambda bug: bug.severity in ["Medium", "Low"]
).publishes(StandardResponse)

# Different handlers based on severity
```

---

## Testing Your Agents

### Unit Test (Isolated)

```python
# Test agent without cascade
result = await flock.invoke(
    pizza_master,
    PizzaIdea(description="margherita"),
    publish_outputs=False  # Don't trigger downstream agents
)

assert isinstance(result, Pizza)
assert "mozzarella" in result.ingredients
```

### Integration Test (Full Cascade)

```python
# Test complete workflow
await flock.publish(PizzaIdea(description="pepperoni"))
await flock.run_until_idle()

reviews = await flock.store.get_by_type(Review)
assert len(reviews) > 0
assert reviews[0].score >= 1
```

---

## Batch Processing Pattern

**Efficient parallel execution:**

```python
# ✅ GOOD: Batch publish, then run in parallel
for i in range(100):
    await flock.publish(PizzaIdea(description=f"pizza {i}"))

await flock.run_until_idle()  # All 100 process concurrently!

# Get all results
pizzas = await flock.store.get_by_type(Pizza)
print(f"✅ Created {len(pizzas)} pizzas in parallel")
```

**Why this separation matters:**
- `publish()` just queues work (fast)
- `run_until_idle()` executes everything in parallel
- 100 pizzas complete in ~1x single pizza time!

**❌ BAD: Don't do this:**
```python
# This would run sequentially (100x slower!)
for i in range(100):
    await flock.publish(PizzaIdea(description=f"pizza {i}"))
    await flock.run_until_idle()  # Waits each time!
```

---

## Next Steps

### Core Concepts

**[Core Concepts](concepts.md)** ⭐ **Read this next**
- Understand Flock, Agent, Artifact, Blackboard
- Mental model: Blackboard vs traditional graphs
- When to use Flock
- **Time:** 15 minutes

### Comprehensive Guides

**[Agent Guide](../guides/agents.md)**
- Advanced subscriptions (batch, join, conditional)
- Production features (circuit breakers, best-of-N)
- Common agent patterns
- **Time:** 20 minutes

**[Blackboard Guide](../guides/blackboard.md)**
- Historical context (Hearsay-II, BB1)
- Artifact flow patterns
- Comparison to graphs, message queues, actors
- **Time:** 15 minutes

**[Dashboard Guide](../guides/dashboard.md)**
- Dual visualization modes
- Interactive graph features
- Real-time monitoring
- **Time:** 15 minutes

**[Tracing Guide](../guides/tracing/index.md)**
- OpenTelemetry auto-instrumentation
- Seven trace viewer modes
- Production debugging scenarios
- **Time:** 20 minutes

**[Visibility Guide](../guides/visibility.md)**
- Zero-trust security
- Multi-tenancy with TenantVisibility
- RBAC with LabelledVisibility
- **Time:** 15 minutes

### Examples Repository

**[Browse Examples](https://github.com/whiteducksoftware/flock/tree/main/examples)**
- `examples/README.md` - Complete 12-step learning path documentation
- `01-cli/` - CLI examples with detailed console output (01-12)
- `02-dashboard/` - Dashboard examples with interactive visualization (01-12)

---

## Summary

**You just learned:**

✅ **Install** - `pip install flock-core`
✅ **Define types** - Pydantic models with `@flock_type`
✅ **Create agents** - `.consumes()` and `.publishes()`
✅ **Run workflows** - `publish()` + `run_until_idle()`
✅ **Get results** - `flock.store.get_by_type()`
✅ **Dashboard** - `flock.serve(dashboard=True)`
✅ **Tracing** - `export FLOCK_AUTO_TRACE=true`

**Key insights:**
- Schemas replace prompts (declarative > imperative)
- Workflows emerge from subscriptions (no graph wiring)
- Parallel execution by default (automatic dependencies)
- Type-safe outputs (Pydantic validation)

**Ready to build?** Copy the [complete working example](#complete-working-example) and start experimenting!

**Questions?** Read [Core Concepts](concepts.md) for deeper understanding.
