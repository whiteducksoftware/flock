# Your First Agent

**Difficulty:** ⭐ Beginner | **Time:** 15 minutes

Welcome to your first Flock agent! You're about to experience the "aha!" moment that makes Flock different from every other AI framework.

## What You'll Build

A pizza recipe generator that transforms vague pizza ideas into structured, detailed recipes using declarative programming.

## The Big Idea: Declarative vs Imperative

Instead of writing prompts like "please make a pizza with these ingredients...", you just define WHAT a pizza looks like. The LLM figures out HOW to make one.

```python
# ❌ Traditional way (imperative)
prompt = """
You are a helpful pizza chef. The user will give you a pizza idea.
Your task is to:
1. Choose appropriate ingredients
2. Decide on a pizza size
3. Select a crust type
4. Write step-by-step instructions
Please output in the following JSON format: {...}
""" # 500+ lines of prompt engineering

# ✅ Flock way (declarative)
@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]

# The schema IS the instruction! 🎯
```

## Step 1: Define Your Data Structures

Think of ordering pizza at a restaurant. You tell them WHAT you want, not HOW to make it.

```python
import asyncio
from pydantic import BaseModel
from flock import Flock
from flock.registry import flock_type

@flock_type  # 👈 This decorator registers your type with Flock's blackboard
class MyDreamPizza(BaseModel):
    """
    INPUT: The vague, dreamy idea you have for a pizza

    This could be anything:
    - "the ultimate pineapple pizza" (controversial but valid!)
    - "a pizza that tastes like a taco"
    - "something with truffle oil and arugula"
    """
    pizza_idea: str


@flock_type  # 👈 This is what comes OUT of the agent
class Pizza(BaseModel):
    """
    OUTPUT: The structured, detailed pizza recipe

    The magic: we DECLARE what a pizza should have, and the LLM
    will fill in all these fields based on the input idea.

    No prompts needed. The schema IS the instruction.
    """
    ingredients: list[str]  # 🧀 What goes on the pizza
    size: str  # 📏 Small? Medium? Family-sized chaos?
    crust_type: str  # 🍞 Thin? Thick? Stuffed with cheese?
    step_by_step_instructions: list[str]  # 📝 How to actually make it
```

**🔥 Key Insight:** Notice there are NO prompts here. The schema itself tells the LLM exactly what to produce!

## Step 2: Create the Orchestrator and Agent

```python
# The "Flock" is like the kitchen where all your agents work
flock = Flock("openai/gpt-4.1")  # 🧠 Using GPT-4.1 as the brain

# Create an agent with ZERO CODE and ZERO PROMPTS
# Just declare: "This agent consumes PizzaIdeas and publishes Pizzas"
pizza_master = (
    flock.agent("pizza_master")  # 👨‍🍳 Give it a name
    .consumes(MyDreamPizza)  # 📥 What it reads from the blackboard
    .publishes(Pizza)  # 📤 What it writes to the blackboard
)
```

**✨ The Magic Just Happened:**

You didn't write ANY instructions. No "You are a helpful pizza chef...".

The `Pizza` schema IS the instruction. The LLM sees:

- "Oh, I need to output ingredients, size, crust_type, instructions"
- "The input is a vague pizza_idea string"
- "I should transform one into the other"

And it just... does it. Every time. Reliably.

## Step 3: Run the Agent

```python
async def main():
    # Create a pizza idea (go wild! The agent can handle it)
    pizza_idea = MyDreamPizza(pizza_idea="pizza with tartufo")

    print(f"🎯 Ordering: {pizza_idea.pizza_idea}")
    print("👨‍🍳 Pizza master is working...\n")

    # Publish to the blackboard (agents subscribed to MyDreamPizza will trigger)
    await flock.publish(pizza_idea)

    # Wait for all agents to finish processing
    await flock.run_until_idle()

    # 🎉 Done! The Pizza artifact is now on the blackboard
    print("✅ Pizza recipe generated!")

if __name__ == "__main__":
    asyncio.run(main())
```

## Expected Output

When you run this, you'll see a structured `Pizza` object in the console with:

- A list of premium ingredients including truffle
- An appropriate pizza size
- A suitable crust type
- Step-by-step cooking instructions

All generated automatically from your simple input!

## What You Just Learned

✅ **Declarative > Imperative**
: You defined WHAT (Pizza schema), not HOW (no prompts!)

✅ **Type Safety**
: Pydantic validates the output. If the LLM tries to return invalid data, it fails BEFORE reaching your code.

✅ **Self-Documenting**
: The schema tells you exactly what the agent does. No hidden prompts.

✅ **Future-Proof**
: When GPT-6 comes out, this code still works. Schemas don't break.

## Try It Yourself

**Challenge 1: Add Dietary Restrictions**

Extend `MyDreamPizza` to include dietary needs:

```python
@flock_type
class MyDreamPizza(BaseModel):
    pizza_idea: str
    dietary_restrictions: list[str] = []  # e.g., ["vegetarian", "gluten-free"]
```

Watch how the agent automatically respects these constraints!

**Challenge 2: Add Cooking Time**

Add a `cooking_time_minutes: int` field to the `Pizza` output. No prompt changes needed—the LLM will figure it out.

**Challenge 3: Create a Validation Agent**

Create a second agent that consumes `Pizza` and publishes `ValidatedPizza` with a `quality_score: float` field.

## Next Steps

Now that you understand the declarative approach, let's see how agents can work together!

[Continue to Multi-Agent Workflow →](multi-agent-workflow.md){ .md-button .md-button--primary }

## Complete Code

??? example "Click to see the complete code"
    ```python
    import asyncio
    from pydantic import BaseModel
    from flock import Flock
    from flock.registry import flock_type

    @flock_type
    class MyDreamPizza(BaseModel):
        pizza_idea: str

    @flock_type
    class Pizza(BaseModel):
        ingredients: list[str]
        size: str
        crust_type: str
        step_by_step_instructions: list[str]

    flock = Flock("openai/gpt-4.1")

    pizza_master = (
        flock.agent("pizza_master")
        .consumes(MyDreamPizza)
        .publishes(Pizza)
    )

    async def main():
        pizza_idea = MyDreamPizza(pizza_idea="pizza with tartufo")
        print(f"🎯 Ordering: {pizza_idea.pizza_idea}")
        print("👨‍🍳 Pizza master is working...\n")

        await flock.publish(pizza_idea)
        await flock.run_until_idle()

        print("✅ Pizza recipe generated!")

    if __name__ == "__main__":
        asyncio.run(main())
    ```

## Reference Links

- [Agent API Reference](../reference/api/agent.md) - Complete agent builder documentation
- [Artifacts Guide](../guides/blackboard.md) - Deep dive into artifact types
- [Getting Started](../getting-started/quick-start.md) - Installation and setup
