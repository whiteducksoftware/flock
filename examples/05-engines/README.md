# ⚙️ Custom Engines

Custom engines let you implement deterministic logic without LLM calls—perfect for rule-based processing, pattern matching, calculations, and zero-cost operations.

## 🎯 What Are Engines?

**Engines** are custom processing components that replace LLM calls with your own logic:

- **Deterministic** - Same input always produces same output
- **Zero cost** - No LLM API calls required
- **Fast** - Direct code execution, no network latency
- **Hybrid architectures** - Mix LLM and rule-based agents

## 💡 Why Use Custom Engines?

| Without Engine (LLM) | With Engine (Code) |
|---------------------|-------------------|
| 💰 Costs per call | ✅ Free |
| 🌐 Network latency | ✅ Instant |
| 🎲 Non-deterministic | ✅ Deterministic |
| 🤷 May vary | ✅ Predictable |

**Use engines when:**
- Logic is deterministic (calculations, regex, lookups)
- Speed is critical
- Cost optimization needed
- Compliance requires deterministic behavior

## 📚 Examples

### emoji_mood_engine.py 😊
**Pattern:** Keyword-based mood detection with emoji mapping

Replace LLM calls with simple keyword matching for mood detection:
- **Pattern matching** - Check for mood keywords in text
- **Emoji mapping** - Deterministic mood → emoji conversion
- **Zero cost** - No API calls
- **Instant** - Sub-millisecond execution

```bash
uv run 05-engines/emoji_mood_engine.py
```

**How It Works:**
```python
class EmojiMoodEngine(EngineComponent):
    MOOD_KEYWORDS = {
        "celebratory": {"congrats", "celebrate", "party", "win"},
        "love-struck": {"love", "adore", "hearts", "romance"},
        "anxious": {"nervous", "worried", "deadline", "yikes"},
        # ...
    }

    async def evaluate(self, agent, ctx, inputs, output_group):
        prompt = inputs.first_as(MoodPrompt)
        mood, keywords = self._detect_mood(prompt.message)
        emoji = self.MOOD_EMOJI.get(mood, "🤔")

        return EvalResult.from_object(
            MoodEmoji(speaker=prompt.speaker, detected_mood=mood, emoji=emoji)
        )
```

**Input/Output:**
- **Input:** `MoodPrompt(speaker="Ava", message="Just landed my dream promotion!")`
- **Output:** `MoodEmoji(speaker="Ava", detected_mood="celebratory", emoji="🎉")`

**Use Cases:**
- Sentiment analysis
- Content filtering
- Category classification
- Simple NLP tasks

**Cost Savings:** 100% (no LLM calls!)

---

### potion_batch_engine.py 🧪
**Pattern:** Batch processing with deterministic business logic

Process multiple inputs in one operation with custom validation:
- **Batch operations** - Handle multiple artifacts at once
- **Business rules** - Apply deterministic validation
- **Quality gates** - Filter/reject based on criteria
- **Cost optimization** - Group processing for efficiency

```bash
uv run 05-engines/potion_batch_engine.py
```

**How It Works:**
```python
class PotionBatchEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Get all potion orders from batch
        orders = inputs.list_as(PotionOrder)

        validated = []
        for order in orders:
            # Apply business rules
            if self._validate_ingredients(order.ingredients):
                validated.append(
                    ValidatedPotion(
                        name=order.name,
                        ingredients=order.ingredients,
                        validation_status="approved"
                    )
                )

        return EvalResult.from_objects(validated, agent=agent)

    def _validate_ingredients(self, ingredients: list[str]) -> bool:
        # Deterministic validation logic
        forbidden = {"dragon_blood", "unicorn_tears"}
        return not any(ing in forbidden for ing in ingredients)
```

**Use Cases:**
- Payment processing batches
- Order validation
- Compliance checking
- Bulk data transformation

**Benefits:**
- **Consistent validation** - Same rules every time
- **Batch efficiency** - Process multiple items together
- **Cost savings** - No per-item LLM calls
- **Audit trails** - Deterministic decisions

---

## 🔑 Key Concepts

### Engine Implementation

All engines inherit from `EngineComponent`:

```python
from flock.components import EngineComponent
from flock.runtime import EvalInputs, EvalResult

class MyEngine(EngineComponent):
    async def evaluate(
        self,
        agent,           # Agent instance
        ctx,            # Execution context
        inputs: EvalInputs,      # Input artifacts
        output_group    # Expected output types
    ) -> EvalResult:
        # Your custom logic here
        input_artifact = inputs.first_as(InputType)

        # Process deterministically
        result = self.process(input_artifact)

        # Return result
        return EvalResult.from_object(result, agent=agent)
```

### Attaching Engines to Agents

```python
flock = Flock()

(
    flock.agent("mood_detector")
    .consumes(MoodPrompt)
    .publishes(MoodEmoji)
    .with_engines(EmojiMoodEngine())  # ← Attach engine
)
```

### Multiple Engines

Agents can use multiple engines:

```python
agent.with_engines(
    ValidationEngine(),
    TransformEngine(),
    FilterEngine()
)
```

### Hybrid Architectures

Mix LLM and engine-based agents:

```python
# LLM-based creative agent
creative_agent = (
    flock.agent("writer")
    .consumes(Prompt)
    .publishes(Story)
    # No engine - uses LLM
)

# Engine-based validation agent
validator = (
    flock.agent("validator")
    .consumes(Story)
    .publishes(ValidatedStory)
    .with_engines(ValidationEngine())  # Deterministic validation
)
```

## 🎓 When to Use Engines vs LLMs

| Scenario | Use Engine | Use LLM |
|----------|-----------|---------|
| Pattern matching | ✅ | ❌ |
| Keyword detection | ✅ | ❌ |
| Math calculations | ✅ | ❌ |
| Business rules | ✅ | ❌ |
| Lookups/mappings | ✅ | ❌ |
| Creative writing | ❌ | ✅ |
| Complex reasoning | ❌ | ✅ |
| Natural language understanding | ❌ | ✅ |
| Summarization | ❌ | ✅ |

## 💰 Cost Optimization Strategy

**Before (all LLM):**
```
100 mood detections × $0.002 per call = $0.20
```

**After (engine for simple tasks):**
```
100 mood detections × $0 = $0.00
```

**💡 Rule of Thumb:** If you can write the logic in code, use an engine!

## 🚀 Advanced Patterns

### Engine with Configuration
```python
class ConfigurableEngine(EngineComponent):
    def __init__(self, threshold: float, rules: dict):
        self.threshold = threshold
        self.rules = rules

    async def evaluate(self, agent, ctx, inputs, output_group):
        # Use configuration in processing
        ...
```

### Engine with State
```python
class StatefulEngine(EngineComponent):
    def __init__(self):
        self.cache = {}

    async def evaluate(self, agent, ctx, inputs, output_group):
        # Use stateful cache
        ...
```

### Engine with Fallback
```python
class HybridEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Try deterministic logic first
        result = self.try_deterministic(inputs)

        if result is None:
            # Fall back to LLM for complex cases
            return None  # Return None to trigger LLM evaluation

        return EvalResult.from_object(result, agent=agent)
```

## 📖 Related Examples

- **03-claudes-workshop/lesson_13_regex_matcher.py** - Workshop lesson on custom engines
- **06-agent-components/** - Per-agent lifecycle hooks
- **07-orchestrator-components/** - Global coordination patterns

## 📚 Documentation

- [Engine Component Guide](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/guides/components.md)
- AGENTS.md - "Components" section
- [Architecture Guide](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/guides/agents.md)

## 💡 Design Tips

1. **Start simple** - Basic keyword matching is often enough
2. **Be deterministic** - Same input should always produce same output
3. **Handle edge cases** - Validate inputs, handle missing data
4. **Return None for LLM fallback** - Let complex cases use LLM
5. **Document behavior** - Make logic clear for maintainers

---

**Ready to build deterministic agents? Start with emoji_mood_engine! 😊**
