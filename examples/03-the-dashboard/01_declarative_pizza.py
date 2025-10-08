"""
🍕 THE DECLARATIVE PIZZA MASTER
================================

Welcome to your first Flock agent! You're about to experience the "aha!" moment
that makes Flock different from every other AI framework.

🎯 THE BIG IDEA:
Instead of writing prompts like "please make a pizza with these ingredients...",
you just define WHAT a pizza looks like. The LLM figures out HOW to make one.

This is called DECLARATIVE PROGRAMMING:
- You describe the WHAT (the data structure)
- Flock handles the HOW (the execution)

⏱️  TIME: 5 minutes
💡 DIFFICULTY: ⭐ Super beginner-friendly
"""

import asyncio

from pydantic import BaseModel

from flock.orchestrator import Flock
from flock.registry import flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🥘 STEP 1: Define Your Data Structures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Think of ordering pizza at a restaurant. You tell them WHAT you want
# (e.g., "I want a large pepperoni with extra cheese"), not HOW to make it.
# You don't instruct them: "First knead the dough, then spread sauce..."
#
# That's the declarative way! And that's how Flock works.


@flock_type  # 👈 This decorator registers your type with Flock's blackboard
class MyDreamPizza(BaseModel):
    """
    INPUT: The vague, dreamy idea you have for a pizza

    This could be anything:
    - "the ultimate pineapple pizza" (controversial but valid!)
    - "a pizza that tastes like a taco"
    - "something with truffle oil and arugula"

    Notice: Just a simple string. No validation. No structure. Pure chaos.
    """

    pizza_idea: str


@flock_type  # 👈 Another type! This is what comes OUT of the agent
class Pizza(BaseModel):
    """
    OUTPUT: The structured, detailed pizza recipe

    This is the magic: we DECLARE what a pizza should have, and the LLM
    will fill in all these fields based on the input idea.

    No prompts needed. The schema IS the instruction.
    """

    ingredients: list[str]  # 🧀 What goes on the pizza
    size: str  # 📏 Small? Medium? Family-sized chaos?
    crust_type: str  # 🍞 Thin? Thick? Stuffed with cheese?
    step_by_step_instructions: list[str]  # 📝 How to actually make it


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🤖 STEP 2: Create the Orchestrator and Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# The "Flock" is like the kitchen where all your agents work
flock = Flock("openai/gpt-4.1")  # 🧠 Using GPT-4.1 as the brain


# Now create an agent with ZERO CODE and ZERO PROMPTS
# Just declare: "This agent consumes PizzaIdeas and publishes Pizzas"
# That's it. Flock figures out the rest.
pizza_master = (
    flock.agent("pizza_master")  # 👨‍🍳 Give it a name
    .consumes(MyDreamPizza)  # 📥 What it reads from the blackboard
    .publishes(Pizza)  # 📤 What it writes to the blackboard
)

# ✨ THE MAGIC JUST HAPPENED:
# You didn't write ANY instructions. No "You are a helpful pizza chef...".
# The Pizza schema IS the instruction. The LLM sees:
# - "Oh, I need to output ingredients, size, crust_type, instructions"
# - "The input is a vague pizza_idea string"
# - "I should transform one into the other"
#
# And it just... does it. Every time. Reliably.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 3: Run the Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    await flock.serve(dashboard=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 WHAT YOU JUST LEARNED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ✅ Declarative > Imperative
#    - You defined WHAT (Pizza schema), not HOW (no prompts!)
#
# ✅ Type Safety
#    - Pydantic validates the output. If the LLM tries to return invalid data,
#      it fails BEFORE reaching your code.
#
# ✅ Self-Documenting
#    - The schema tells you exactly what the agent does. No hidden prompts.
#
# ✅ Future-Proof
#    - When GPT-6 comes out, this code still works. Schemas don't break.
#
# 🚀 NEXT STEP: Run 02_input_and_output.py to learn about complex types!
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main(), debug=True)
