# Hello Flock

This example demonstrates how to create a simple agent using Flock. It's a great starting point for understanding the basics of the framework.

## Basic Example

Let's create a simple agent that takes a greeting as input and returns a personalized response:

```python
from flock.core import Flock, FlockAgent

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# Create an agent
hello_agent = FlockAgent(
    name="hello_agent",
    input="greeting: str | A greeting message",
    output="response: str | A personalized response"
)

# Add the agent to the flock
flock.add_agent(hello_agent)

# Run the agent
result = flock.run(
    start_agent=hello_agent,
    input={"greeting": "Hello, Flock!"}
)

print(result)
```

Output:
```python
{
    'greeting': 'Hello, Flock!',
    'response': 'Hello there! It\'s great to meet you. I\'m Flock, your friendly AI assistant. How can I help you today?'
}
```

## Adding Type Hints

Let's enhance our example by adding more specific type hints:

```python
from flock.core import Flock, FlockAgent

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# Create an agent with more specific type hints
hello_agent = FlockAgent(
    name="hello_agent",
    input="name: str | The user's name, language: str | The preferred language",
    output="greeting: str | A personalized greeting in the specified language"
)

# Add the agent to the flock
flock.add_agent(hello_agent)

# Run the agent
result = flock.run(
    start_agent=hello_agent,
    input={
        "name": "Alice",
        "language": "Spanish"
    }
)

print(result)
```

Output:
```python
{
    'name': 'Alice',
    'language': 'Spanish',
    'greeting': '¡Hola Alice! Es un placer conocerte. ¿Cómo estás hoy?'
}
```

## Using Tools

Let's enhance our agent by adding a tool that gets the current time:

```python
from flock.core import Flock, FlockAgent
from flock.core.tools import basic_tools

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# Create an agent with a tool
hello_agent = FlockAgent(
    name="hello_agent",
    input="name: str | The user's name",
    output="greeting: str | A personalized greeting with the current time",
    tools=[basic_tools.get_current_time]
)

# Add the agent to the flock
flock.add_agent(hello_agent)

# Run the agent
result = flock.run(
    start_agent=hello_agent,
    input={"name": "Bob"}
)

print(result)
```

Output:
```python
{
    'name': 'Bob',
    'greeting': 'Hello Bob! It\'s currently 2:30 PM in your timezone. How can I assist you today?'
}
```

## Adding a Description

Let's add a description to our agent to make it more self-documenting:

```python
from flock.core import Flock, FlockAgent

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# Create an agent with a description
hello_agent = FlockAgent(
    name="hello_agent",
    description="An agent that generates personalized greetings based on user information",
    input="name: str | The user's name, mood: str | The user's current mood",
    output="greeting: str | A personalized greeting that acknowledges the user's mood"
)

# Add the agent to the flock
flock.add_agent(hello_agent)

# Run the agent
result = flock.run(
    start_agent=hello_agent,
    input={
        "name": "Charlie",
        "mood": "excited"
    }
)

print(result)
```

Output:
```python
{
    'name': 'Charlie',
    'mood': 'excited',
    'greeting': 'Hey Charlie! I can feel your excitement! That\'s awesome! What\'s got you so pumped up today?'
}
```

## Using a Different Model

You can specify a different model for your agent:

```python
from flock.core import Flock, FlockAgent

# Create a Flock instance with a default model
flock = Flock(model="openai/gpt-4o")

# Create an agent with a different model
hello_agent = FlockAgent(
    name="hello_agent",
    model="anthropic/claude-3-opus-20240229",  # Override the default model
    input="name: str | The user's name",
    output="greeting: str | A personalized greeting"
)

# Add the agent to the flock
flock.add_agent(hello_agent)

# Run the agent
result = flock.run(
    start_agent=hello_agent,
    input={"name": "David"}
)

print(result)
```

## Saving and Loading Agents

You can save and load agents for reuse:

```python
from flock.core import Flock, FlockAgent

# Create an agent
hello_agent = FlockAgent(
    name="hello_agent",
    input="name: str | The user's name",
    output="greeting: str | A personalized greeting"
)

# Save the agent to a file
hello_agent.save_to_file("hello_agent.json")

# Load the agent from a file
loaded_agent = FlockAgent.load_from_file("hello_agent.json")

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# Add the loaded agent to the flock
flock.add_agent(loaded_agent)

# Run the agent
result = flock.run(
    start_agent=loaded_agent,
    input={"name": "Eve"}
)

print(result)
```

## Running Asynchronously

You can run agents asynchronously:

```python
import asyncio
from flock.core import Flock, FlockAgent

async def main():
    # Create a Flock instance
    flock = Flock(model="openai/gpt-4o")

    # Create an agent
    hello_agent = FlockAgent(
        name="hello_agent",
        input="name: str | The user's name",
        output="greeting: str | A personalized greeting"
    )

    # Add the agent to the flock
    flock.add_agent(hello_agent)

    # Run the agent asynchronously
    result = await flock.run_async(
        start_agent=hello_agent,
        input={"name": "Frank"}
    )

    print(result)

# Run the async function
asyncio.run(main())
```

## Next Steps

Now that you've seen the basics of Flock, you might want to explore:

- [Chain Gang](chain-gang.md) - Learn how to chain multiple agents together
- [Type System](../core-concepts/type-system.md) - Learn more about the type system
- [Tools](../core-concepts/tools.md) - Learn more about using tools with agents
- [Memory](../core-concepts/memory.md) - Learn how to add memory to your agents
