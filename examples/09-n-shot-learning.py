"""
Example demonstrating n-shot learning with the ExampleUtilityComponent.

This example shows how to:
1. Create example records
2. Seed them into storage using the static seed_examples method
3. Create an agent with example learning enabled
4. Run the agent to see examples being injected into the input
"""

from datetime import datetime

from flock.components.utility.example_utility_component import ExampleRecord, ExampleUtilityComponent, ExampleUtilityConfig
from flock.core import Flock, DefaultAgent

# Create some example records for a customer service agent
examples = [
    ExampleRecord(
        agent_name="customer_service",
        example_id="example_1",
        content="Q: How do I reset my password?\nA: To reset your password, click on the 'Forgot Password' link on the login page and follow the instructions sent to your email."
    ),
    ExampleRecord(
        agent_name="customer_service",
        example_id="example_2", 
        content="Q: What is your return policy?\nA: We offer a 30-day return policy for all unused items in their original packaging. Simply contact our support team to initiate a return."
    ),
    ExampleRecord(
        agent_name="customer_service",
        example_id="example_3",
        content="Q: How long does shipping take?\nA: Standard shipping typically takes 5-7 business days. Express shipping options are available at checkout for 2-3 day delivery."
    )
]

# Seed the examples into storage
print("Seeding examples into storage...")
ExampleUtilityComponent.seed_examples(examples)
print(f"Seeded {len(examples)} examples for customer service agent")

# Create a customer service agent with example learning enabled
agent = DefaultAgent(
    name="customer_service",
    description="Helps customers with their inquiries using examples",
    input="customer_query: str | The customer's question or issue",
    output="response: str | A helpful response to the customer",
    enable_examples=True,
    example_config=ExampleUtilityConfig(
        max_examples=3,
        example_timeframe_days=30,
        example_input_key="examples_context"
    )
)

# Create flock and add agent
flock = Flock(model="azure/gpt-4")
flock.add_agent(agent)

# Example interaction
query = "How do I track my order?"
print(f"\nCustomer query: {query}")

# Run the agent - examples will be automatically injected
result = flock.run(
    agent="customer_service",
    input={"customer_query": query}
)

print(f"\nAgent response: {result.response}")

# The agent will have received relevant examples in the 'examples_context' input key
# which can influence its response based on the provided examples

# You can also add more examples programmatically
new_example = ExampleRecord(
    agent_name="customer_service",
    example_id="example_4",
    content="Q: How do I track my order?\nA: You can track your order by logging into your account and clicking on 'My Orders'. Enter your order number to see the current status and tracking information."
)

# Seed the new example
ExampleUtilityComponent.seed_examples([new_example])
print("\nAdded new example for order tracking")

# Run the agent again with the same query
result = flock.run(
    agent="customer_service",
    input={"customer_query": query}
)

print(f"\nAgent response with new example: {result.response}")
