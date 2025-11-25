"""
Hackathon Track 01: Basic Agent

🎓 LEARNING OBJECTIVE:
Understand the fundamental concept of Flock: agents that consume and produce
typed artifacts on a shared blackboard.

KEY CONCEPTS:
- Agent declaration with .agent().consumes().publishes()
- Type registration with @flock_type
- Publishing artifacts to the blackboard
- Running agents until completion

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = True  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# STEP 1: Define Your Data Types (Artifacts)
# ============================================================================
# In Flock, everything is typed. You define Pydantic models that represent
# the data flowing through your system. Think of these as "message types"
# that agents can read from and write to the blackboard.
# ============================================================================

@flock_type
class RecipeRequest(BaseModel):
    """A request for a recipe - what the user wants to cook."""
    dish_name: str = Field(description="Name of the dish to create a recipe for")
    cuisine_type: str = Field(default="international", description="Type of cuisine")
    dietary_restrictions: list[str] = Field(
        default_factory=list,
        description="Dietary restrictions (e.g., 'vegetarian', 'gluten-free')"
    )


@flock_type
class Recipe(BaseModel):
    """A complete recipe with ingredients and instructions."""
    dish_name: str
    cuisine_type: str
    ingredients: list[str] = Field(description="List of ingredients with quantities")
    instructions: list[str] = Field(description="Step-by-step cooking instructions")
    prep_time_minutes: int = Field(description="Preparation time in minutes")
    cook_time_minutes: int = Field(description="Cooking time in minutes")
    difficulty: str = Field(description="Difficulty level: easy, medium, or hard")


# ============================================================================
# STEP 2: Create the Orchestrator
# ============================================================================
# The Flock orchestrator manages the blackboard and coordinates agents.
# Think of it as the "conductor" of your multi-agent system.
# ============================================================================

flock = Flock()


# ============================================================================
# STEP 3: Define Your Agent
# ============================================================================
# Agents declare WHAT they consume and WHAT they produce. The orchestrator
# handles the rest - triggering agents when matching artifacts appear,
# managing execution, and routing outputs.
#
# The fluent API makes this very readable:
# - .agent("name") - Give your agent a unique name
# - .description("...") - Help the LLM understand the agent's role
# - .consumes(Type) - What artifact types this agent processes
# - .publishes(Type) - What artifact types this agent creates
# ============================================================================

chef_agent = (
    flock.agent("chef")
    .description(
        "A creative chef who creates detailed recipes from recipe requests. "
        "Always provides accurate ingredient quantities and clear step-by-step instructions."
    )
    .consumes(RecipeRequest)  # This agent reacts to RecipeRequest artifacts
    .publishes(Recipe)        # This agent produces Recipe artifacts
)


# ============================================================================
# STEP 4: Run Your System
# ============================================================================
# To execute your agents:
# 1. Publish artifacts to the blackboard (flock.publish())
# 2. Run until all agents finish (flock.run_until_idle())
# 3. Retrieve results from the blackboard (flock.store.get_by_type())
# ============================================================================

async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("=" * 70)
    print("🍳 BASIC AGENT EXAMPLE - Recipe Generator")
    print("=" * 70)
    print()
    
    # Create a recipe request
    request = RecipeRequest(
        dish_name="Spicy Thai Green Curry",
        cuisine_type="Thai",
        dietary_restrictions=["vegetarian"]
    )
    
    print(f"📝 Recipe Request:")
    print(f"   Dish: {request.dish_name}")
    print(f"   Cuisine: {request.cuisine_type}")
    print(f"   Restrictions: {', '.join(request.dietary_restrictions) or 'None'}")
    print()
    print("⏳ Publishing request and waiting for chef agent...")
    print()
    
    # Publish the request to the blackboard
    # This will trigger any agents subscribed to RecipeRequest
    await flock.publish(request)
    
    # Run until all agents finish processing
    await flock.run_until_idle()
    
    # Retrieve the generated recipe
    recipes = await flock.store.get_by_type(Recipe)
    
    if recipes:
        recipe = recipes[0]
        print("✅ Recipe Generated!")
        print("=" * 70)
        print(f"🍽️  {recipe.dish_name} ({recipe.cuisine_type})")
        print(f"   Difficulty: {recipe.difficulty}")
        print(f"   Prep: {recipe.prep_time_minutes} min | Cook: {recipe.cook_time_minutes} min")
        print()
        print("📋 Ingredients:")
        for ingredient in recipe.ingredients:
            print(f"   • {ingredient}")
        print()
        print("👨‍🍳 Instructions:")
        for i, instruction in enumerate(recipe.instructions, 1):
            print(f"   {i}. {instruction}")
    else:
        print("❌ No recipe generated. Check agent configuration.")
    
    print()
    print("=" * 70)


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8344 to interact with the recipe generator!")
    print()
    print("💡 Try publishing different recipe requests and watch the chef agent work!")
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# 🎓 NOW IT'S YOUR TURN!
# ============================================================================
# 
# EXPERIMENT 1: Try Different Recipes
# -----------------------------------
# Modify the RecipeRequest in main_cli() to try different dishes:
#   - Change dish_name to "Chocolate Chip Cookies"
#   - Try cuisine_type "Italian" or "Mexican"
#   - Add dietary_restrictions like ["vegan", "nut-free"]
#
# What happens? Does the recipe adapt to your changes?
#
#
# EXPERIMENT 2: Add More Fields
# -----------------------------
# Extend the RecipeRequest model to include:
#   - serving_size: int (how many people)
#   - spice_level: str (mild, medium, hot, extra-hot)
#   - budget: str (budget-friendly, moderate, gourmet)
#
# Then update the chef agent's description to mention these fields.
# Run the example and see if the recipe reflects your new fields!
#
#
# EXPERIMENT 3: Multiple Requests
# --------------------------------
# Publish multiple RecipeRequest artifacts:
#   await flock.publish(RecipeRequest(dish_name="Pasta Carbonara", cuisine_type="Italian"))
#   await flock.publish(RecipeRequest(dish_name="Sushi Rolls", cuisine_type="Japanese"))
#   await flock.publish(RecipeRequest(dish_name="Tacos", cuisine_type="Mexican"))
#
# How many recipes are generated? Why?
#
#
# EXPERIMENT 4: Dashboard Mode
# -----------------------------
# Set USE_DASHBOARD = True and run the example.
# In the dashboard:
#   1. Click "Publish" button
#   2. Select "RecipeRequest" from the dropdown
#   3. Fill in the form fields
#   4. Click "Publish Artifact"
#   5. Watch the chef agent execute in real-time!
#
# What do you see in the Agent View? What about the Blackboard View?
#
#
# EXPERIMENT 5: Agent Description Matters
# ----------------------------------------
# Change the chef agent's description to:
#   .description("A minimalist chef who creates recipes with only 3 ingredients")
#
# Run the example again. Does the output change? Why?
#
# Try other descriptions:
#   - "A health-conscious chef focused on low-calorie recipes"
#   - "A gourmet chef who creates restaurant-quality recipes"
#   - "A budget chef who uses inexpensive ingredients"
#
#
# CHALLENGE: Build Your Own
# --------------------------
# Create a new agent system for a different domain:
#   1. Define two types: Request and Response
#   2. Create an agent that transforms Request → Response
#   3. Try domains like:
#      - Travel planning (DestinationRequest → TravelItinerary)
#      - Book recommendations (BookRequest → BookRecommendation)
#      - Workout plans (FitnessGoal → WorkoutPlan)
#
# What did you learn about agent declaration?
#
# ============================================================================

