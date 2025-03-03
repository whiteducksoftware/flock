# Basic Concepts

Welcome to Flock! This guide will introduce you to the fundamental concepts that make Flock a unique and powerful framework for building AI agents. Instead of wrestling with complex prompts, Flock lets you focus on what matters - declaring what you want your agents to do.

## The Core Idea

Think of Flock like ordering at a restaurant - you specify what dish you want, not the detailed instructions for the chef. Similarly, with Flock, you declare what you want your agent to accomplish, and the framework figures out how to make it happen.

Traditional approaches often look like this:
```python
agent.prompt = """Analyze the given text using the following steps:
Step 1: Read and comprehend the content
Step 2: Identify key themes...
... (many more lines of prompt engineering) ..."""
```

With Flock, it's refreshingly simple:
```python
agent = FlockFactory.create_default_agent(
    name="analyzer",
    input="text_content",
    output="analysis, key_themes: list[str]"
)
```

## Key Components

### The Flock Orchestrator

The `Flock` class is your command center. It manages all your agents, handles their interactions, and ensures everything runs smoothly:

```python
from flock.core import Flock

flock = Flock(model="openai/gpt-4o")
```

### Agents

Agents are the workhorses of your system. Each agent has:
- A unique name
- Defined inputs
- Expected outputs
- Optional tools and configurations

```python
agent = FlockFactory.create_default_agent(
    name="summarizer",
    input="text | The content to summarize",
    output="summary, highlights: list[str] | Key points extracted"
)
```

### Input/Output Declarations

Flock uses an intuitive syntax for declaring what agents need and produce:

```python
# Simple declarations
input="query"
output="response"

# With type hints
output="title: str, word_count: int, confidence: float"

# With descriptions
input="url | The webpage to analyze"
output="sentiment: float | Sentiment score from -1 to 1"
```

### Tools

Tools extend what your agents can do - whether it's searching the web, processing files, or performing calculations:

```python
from flock.core.tools import basic_tools

web_agent = FlockFactory.create_default_agent(
    name="web_analyzer",
    input="url",
    output="content_summary",
    tools=[basic_tools.get_web_content_as_markdown]
)
```

For more advanced capabilities, Flock provides specialized tools like [Azure Search integration](../core-concepts/tools/azure-tools.md) for powerful vector search and document retrieval. Check out the [Tools Overview](../core-concepts/tools/overview.md) for a comprehensive list of available tools.

### Modules

Modules add capabilities to your agents through lifecycle hooks:

```python
# Example with output formatting
analysis_agent = FlockFactory.create_default_agent(
    name="analyzer",
    input="query",
    output="result",
    enable_rich_tables=True,
    output_theme=OutputTheme.aardvark_blue
)
```

### Type System

Flock provides robust type safety through Python's type system and Pydantic:

```python
from typing import Literal
from dataclasses import dataclass

@dataclass
class MovieReview:
    title: str
    rating: float
    category: Literal["action", "drama", "comedy"]
    
reviewer = FlockFactory.create_default_agent(
    name="movie_reviewer",
    input="movie_title",
    output="review: MovieReview"
)
```

### Workflows

Connect agents to create sophisticated workflows:

```python
# Simple handoff between agents
idea_agent.hand_off = implementation_agent

# Run the workflow
flock.run(
    start_agent=idea_agent,
    input={"query": "Design a weather dashboard"}
)
```

## Development Modes

### Local Debug Mode
Perfect for development and testing:
```python
flock = Flock(enable_temporal=False)
```

### Production Mode
For robust, scalable deployments with Temporal:
```python
flock = Flock(enable_temporal=True)
```

## Best Practices

1. **Start Simple**
   - Begin with single agents
   - Add complexity gradually
   - Test thoroughly

2. **Embrace Types**
   - Use type hints consistently
   - Define clear data structures
   - Leverage Pydantic models

3. **Handle Errors**
   - Plan for edge cases
   - Use appropriate error handling
   - Test failure scenarios

4. **Monitor Performance**
   - Enable appropriate logging
   - Use telemetry
   - Track performance metrics

## Next Steps

Ready to dive deeper? Check out:
- [Type System](../core-concepts/type-system.md) for more on type safety
- [Agent Definition](../features/agent-definition.md) for detailed configuration
- [Examples](../examples/hello-flock.md) for practical implementations
- [Workflows](../core-concepts/workflows.md) for complex agent interactions