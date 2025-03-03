# Tools Overview

Flock provides a variety of tools that agents can use to interact with external systems, access specialized capabilities, and extend their functionality beyond language processing.

## What Are Tools?

In Flock, tools are functions that agents can invoke to perform specific tasks. Unlike the agent's core language capabilities, tools allow agents to:

- Access external data sources and APIs
- Perform specialized calculations or operations
- Interact with services like databases, search engines, or vector stores
- Execute custom business logic

Tools are designed to be modular and composable, allowing you to give your agents exactly the capabilities they need for their specific tasks.

## Available Tool Categories

Flock includes several categories of built-in tools:

1. **Search and Retrieval Tools**
   - Azure AI Search tools for document and vector search
   - (More coming soon)

2. **Utility Tools**
   - Math operations
   - Data processing
   - File operations

3. **Integration Tools**
   - External API connectors
   - Service integrations

## Using Tools with Agents

Tools can be assigned to agents during creation:

```python
from flock import FlockFactory
from flock.core.tools.azure_tools import azure_search_query

# Create an agent with access to the Azure Search query tool
agent = FlockFactory.create_default_agent(
    name="search_agent",
    input="query",
    output="results",
    tools=[azure_search_query]
)
```

Agents can then use these tools during their execution cycle, calling them as needed to fulfill their tasks.

## Creating Custom Tools

You can easily create custom tools for your specific needs:

```python
from flock.core.logging.trace_and_logged import traced_and_logged

@traced_and_logged
def my_custom_tool(param1: str, param2: int = 0) -> dict:
    """
    A custom tool that performs a specific task.
    
    Args:
        param1: The first parameter
        param2: The second parameter with default value
        
    Returns:
        A dictionary with the results
    """
    # Your tool implementation here
    result = {"status": "success", "value": f"{param1} processed with {param2}"}
    return result
```

Key points for creating effective tools:

1. Use the `@traced_and_logged` decorator for proper tracing and logging
2. Provide clear type hints for parameters and return values
3. Write descriptive docstrings explaining what the tool does
4. Handle errors gracefully within the tool implementation
5. Return structured data that agents can easily process

## Tool Best Practices

1. **Error Handling**: Implement proper error handling within tools to prevent agent failures
2. **Tool Composition**: Design tools to be composable so they can be combined for complex workflows
3. **Parameter Validation**: Validate parameters within tools to prevent incorrect usage
4. **Documentation**: Clearly document what each tool does, its parameters, and return values
5. **Security**: Be mindful of security implications, especially for tools that access external systems

## Next Steps

- Explore specific tool implementations in detail in their respective documentation pages
- Learn how to create your own custom tools tailored to your specific use cases
- See examples of tools in action in the Tutorials section 