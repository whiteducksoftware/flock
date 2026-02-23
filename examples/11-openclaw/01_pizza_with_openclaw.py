"""
OpenClaw Integration: Pizza Generation via External Agent

This example demonstrates the simplest OpenClaw integration: a single agent
backed by an OpenClaw gateway instead of a direct LLM call.

The OpenClaw agent receives the input artifact and output schema, then uses
its full toolkit (tools, skills, web search, reasoning) to produce the result.

🔧 SETUP: Configure your OpenClaw gateway before running:
    1) Enable gateway.http.endpoints.responses.enabled=true in OpenClaw config
    2) export OPENCLAW_CODEX_URL=http://localhost:19789
    3) export OPENCLAW_CODEX_TOKEN=your-token

Run:
    uv run python examples/11-openclaw/01_pizza_with_openclaw.py

Dashboard streaming note:
    If you run this flow with a Flock dashboard/WebSocket sink enabled,
    OpenClaw token streaming is activated automatically (no extra flags needed).
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock, OpenClawConfig
from flock.registry import flock_type


@flock_type
class MyPizzaIdea(BaseModel):
    pizza_idea: str = Field(
        default="Pizza with pineapple",
        description="A short description of your dream pizza",
    )


@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]


# ============================================================================
# Setup: Configure OpenClaw gateway
# ============================================================================
# Option 1: Explicit configuration
# flock = Flock(
#     openclaw=OpenClawConfig(
#         gateways={
#             "codex": GatewayConfig(
#                 url="http://127.0.0.1:19789",
#                 token_env="OPENCLAW_CODEX_TOKEN",  # env var name, not token value
#             )
#         }
#     )
# )

# Option 2: Auto-discover from environment (uncomment to use):
flock = Flock(openclaw=OpenClawConfig.from_env())


# ============================================================================
# Define agent: Same fluent API, different compute backend
# ============================================================================
# Instead of flock.agent("pizza_master"), we use flock.openclaw_agent("codex")
# Everything else stays the same — consumes, publishes, blackboard semantics.
pizza_master = (
    flock.openclaw_agent("codex")
    .description("Creates detailed pizza recipes from ideas")
    .consumes(MyPizzaIdea)
    .publishes(Pizza)
)


# ============================================================================
# Run: Publish and let the OpenClaw agent do its thing
# ============================================================================
async def main():
    pizza_idea = MyPizzaIdea(
        pizza_idea="A spicy Hawaiian with jalapeños and smoked pineapple"
    )

    print(f"🍕 Sending pizza idea to OpenClaw agent: {pizza_idea.pizza_idea}\n")

    await flock.publish(pizza_idea)
    await flock.run_until_idle()

    pizzas = await flock.store.get_by_type(Pizza)
    if pizzas:
        pizza = pizzas[0]
        print(f"🍕 Pizza: {pizza.size} {pizza.crust_type}")
        print(f"   Ingredients: {', '.join(pizza.ingredients)}")
        print(f"   Steps: {len(pizza.step_by_step_instructions)}")

    print("\n✅ Done! The OpenClaw agent used its full toolkit to create this pizza.")


if __name__ == "__main__":
    asyncio.run(main())
