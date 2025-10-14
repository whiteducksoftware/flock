# Custom Engines: Emoji Vibes & Batch Brews

Custom engines are where Flock’s declarative facade meets the code you actually want to write. In this tutorial you will build two wildly different `EngineComponent`s:

- A real-time emoji interpreter that reacts to short mood updates.
- A batch-oriented potion brewer that waits for enough ingredients before revealing its recipe.

Both examples live in `examples/05-engines/` so you can run them end-to-end.

---

## 1. Emoji Mood Engine (single artifact flow)

**Goal:** Turn plain-text mood updates into structured emoji summaries.

Run the example:

```bash
uv run python examples/05-engines/emoji_mood_engine.py
```

Key takeaways from [`EmojiMoodEngine`](../../examples/05-engines/emoji_mood_engine.py):

- Inherit from `EngineComponent` and override `evaluate()`.
- Use `inputs.first_as(Model)` to deserialize the first artifact into your Pydantic model.
- Return results with `EvalResult.from_object(...)`; Flock turns them into blackboard artifacts automatically.
- Small helper methods (_detect_mood, _explain) keep the core handler readable.

Snippet:

```python
class EmojiMoodEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        prompt = inputs.first_as(MoodPrompt)
        if not prompt:
            return EvalResult.empty()

        detected, keywords = self._detect_mood(prompt.message)
        emoji = self.MOOD_EMOJI.get(detected, self.MOOD_EMOJI["curious"])

        artifact = MoodEmoji(
            speaker=prompt.speaker,
            detected_mood=detected,
            emoji=emoji,
            explanation=self._explain(prompt.message, detected, keywords),
        )
        return EvalResult.from_object(artifact, agent=agent)
```

Try it yourself:

1. Add the word “nap” to a message and see which emoji appears.
2. Extend `MOOD_KEYWORDS` to include your team’s inside jokes.
3. Swap `EvalResult.from_object` for `EvalResult.from_objects` if you want multiple emoji outputs.

---

## 2. Potion Batch Engine (BatchSpec showcase)

**Goal:** Gather three whimsical ingredients, then publish a fully-fledged potion recipe.

Run the example:

```bash
uv run python examples/05-engines/potion_batch_engine.py
```

Highlights from [`PotionBatchEngine`](../../examples/05-engines/potion_batch_engine.py):

- The agent subscribes with `.consumes(PotionIngredient, batch=BatchSpec(size=3))`.
- `evaluate_batch()` receives *all* accumulated artifacts at once.
- `inputs.all_as(Model)` deserializes every ingredient payload for easy iteration.
- You can still keep a fallback `evaluate()` if something calls the engine outside of batching.

Snippet:

```python
class PotionBatchEngine(EngineComponent):
    async def evaluate_batch(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        ingredients = inputs.all_as(PotionIngredient)
        if not ingredients:
            return EvalResult.empty()

        recipe = PotionRecipe(
            title=self._name_potion(ingredients),
            incantation=self._craft_incantation(ingredients),
            tasting_notes=self._describe_feel(ingredients),
            ingredients=[f"{item.name} ({item.effect})" for item in ingredients],
        )
        return EvalResult.from_object(recipe, agent=agent)
```

Try it yourself:

1. Change `BatchSpec(size=3)` to `BatchSpec(size=2, timeout=timedelta(seconds=3))` to see timeout-driven flushes.
2. Add a fourth ingredient after a flush to confirm the accumulator resets cleanly.
3. Return two artifacts (e.g., `PotionRecipe` and `SafetyInstructions`) via `EvalResult.from_objects`.

---

## When to build a custom engine

- You want deterministic logic written in Python (rule-based, API calls, DSPy overrides).
- You need batching behaviour that standard engines do not provide out of the box.
- You want to reuse a “library” of engines across multiple agents.

Pair these engines with tracing (`FLOCK_AUTO_TRACE=true`) to watch every decision step in DuckDB.

Next: bring similar creativity to agent components with [Custom Agent Components](custom-agent-components.md).
