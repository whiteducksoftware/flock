# Evaluators

Evaluators are a key component of the Flock framework that determine how agents process inputs to produce outputs. They provide a flexible and modular way to customize the evaluation strategy for different agents.

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Evaluator
    participant LLM
    participant Tools
    
    User->>Agent: Input Data
    Agent->>Evaluator: Forward Input
    
    rect rgb(240, 240, 240)
        Note over Evaluator,Tools: Evaluation Process
        Evaluator->>Evaluator: Process Input
        Evaluator->>LLM: Generate Prompt
        LLM->>Evaluator: Response
        
        opt Tool Usage
            Evaluator->>Tools: Call Tool
            Tools->>Evaluator: Tool Result
            Evaluator->>LLM: Tool Result + Context
            LLM->>Evaluator: Updated Response
        end
    end
    
    Evaluator->>Agent: Return Output
    Agent->>User: Final Result
    
    style Evaluator fill:#aa6a6a,stroke:#333,stroke-width:2px
    style Agent fill:#d4a76a,stroke:#333,stroke-width:2px
    style LLM fill:#6a8caa,stroke:#333,stroke-width:2px
    style Tools fill:#6a9a7b,stroke:#333,stroke-width:2px
```

## What are Evaluators?

In Flock, an evaluator is responsible for taking an agent's inputs and producing outputs using a specific evaluation strategy. This could involve:

- Calling an LLM with a specific prompt
- Using a rule-based system
- Implementing custom logic
- Integrating with external systems

Evaluators abstract away the details of how inputs are processed, allowing agents to focus on what they need and what they produce, rather than how they produce it.

## Evaluator Architecture

All evaluators inherit from the `FlockEvaluator` base class, which defines the interface that all evaluators must implement:

```python
class FlockEvaluator(BaseModel, ABC):
    """Base class for all evaluators.

    An evaluator is responsible for taking inputs and producing outputs
    using some evaluation strategy.
    """

    name: str = Field(..., description="Name of the evaluator")
    config: FlockEvaluatorConfig = Field(default_factory=FlockEvaluatorConfig)

    @abstractmethod
    async def evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        tools: list[Callable] = None,
    ) -> dict[str, Any]:
        """Evaluate inputs to produce outputs."""
        pass
```

## Built-in Evaluators

Flock provides several built-in evaluators:

### Declarative Evaluator

The `DeclarativeEvaluator` is the default evaluator used by Flock. It takes a declarative approach to evaluation, focusing on what the agent needs as input and what it produces as output, rather than requiring complex prompt engineering.

```python
from flock.evaluators.declarative.declarative_evaluator import DeclarativeEvaluator, DeclarativeEvaluatorConfig

evaluator = DeclarativeEvaluator(
    name="declarative_evaluator",
    config=DeclarativeEvaluatorConfig(
        temperature=0.2,  # Temperature for LLM generation
        max_tokens=2000,  # Maximum tokens for LLM generation
    )
)
```

### Natural Language Evaluator

The `NaturalLanguageEvaluator` allows you to use traditional prompt engineering techniques with Flock. It provides more control over the prompt used to generate outputs.

```python
from flock.evaluators.natural_language.natural_language_evaluator import NaturalLanguageEvaluator, NaturalLanguageEvaluatorConfig

evaluator = NaturalLanguageEvaluator(
    name="natural_language_evaluator",
    config=NaturalLanguageEvaluatorConfig(
        temperature=0.2,  # Temperature for LLM generation
        max_tokens=2000,  # Maximum tokens for LLM generation
        prompt_template="You are an expert in {topic}. Please provide information about {query}.",
    )
)
```

### Zep Evaluator

The `ZepEvaluator` integrates with the Zep knowledge graph system, allowing agents to add or query data from a knowledge graph.

```python
from flock.evaluators.zep.zep_evaluator import ZepEvaluator, ZepEvaluatorConfig

evaluator = ZepEvaluator(
    name="zep_evaluator",
    config=ZepEvaluatorConfig(
        zep_api_url="https://api.zep.us",
        zep_api_key="your-api-key",
    )
)
```

## Using Evaluators

To use an evaluator with an agent, simply set the agent's `evaluator` property:

```python
from flock.core import Flock, FlockAgent
from flock.evaluators.natural_language.natural_language_evaluator import NaturalLanguageEvaluator

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# Create an agent with a custom evaluator
agent = FlockAgent(
    name="my_agent",
    input="query: str | The query to process",
    output="result: str | The processed result",
    evaluator=NaturalLanguageEvaluator(name="my_evaluator")
)

# Add the agent to the flock
flock.add_agent(agent)
```

When using `FlockFactory`, you can specify the evaluator as a parameter:

```python
from flock.core import Flock, FlockFactory
from flock.evaluators.natural_language.natural_language_evaluator import NaturalLanguageEvaluator

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# Create an agent with a custom evaluator
agent = FlockFactory.create_default_agent(
    name="my_agent",
    input="query: str | The query to process",
    output="result: str | The processed result",
    evaluator=NaturalLanguageEvaluator(name="my_evaluator")
)

# Add the agent to the flock
flock.add_agent(agent)
```

## Evaluator Configuration

All evaluators have a configuration class that inherits from `FlockEvaluatorConfig`. This class defines the configuration parameters for the evaluator:

```python
class FlockEvaluatorConfig(BaseModel):
    """Configuration for an evaluator.

    This class defines the configuration parameters for an evaluator.
    Subclasses can extend this to add additional parameters.
    """

    name: str = Field(
        default="default_evaluator", description="Name of the evaluator"
    )
    enabled: bool = Field(
        default=True, description="Whether the evaluator is enabled"
    )
    temperature: float = Field(
        default=0.2,
        description="Temperature for LLM generation",
        ge=0.0,
        le=1.0,
    )
    max_tokens: int = Field(
        default=2000,
        description="Maximum tokens for LLM generation",
        ge=1,
    )
```

Each evaluator type can extend this configuration class to add additional parameters specific to that evaluator type.

## Creating Custom Evaluators

You can create custom evaluators by inheriting from the `FlockEvaluator` base class and implementing the `evaluate` method:

```python
from flock.evaluators.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig

class MyCustomEvaluator(FlockEvaluator):
    """Custom evaluator implementation."""

    def __init__(
        self,
        name: str = "my_custom_evaluator",
        config: FlockEvaluatorConfig = None,
    ):
        """Initialize the MyCustomEvaluator."""
        super().__init__(name=name, config=config or FlockEvaluatorConfig(name=name))

    async def evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        tools: list[Callable] = None,
    ) -> dict[str, Any]:
        """Evaluate inputs to produce outputs."""
        # Custom evaluation logic here
        # ...
        return {"result": f"Processed: {inputs['query']}"}
```

## Benefits of Evaluators

Evaluators provide several benefits:

1. **Separation of Concerns**: Evaluators separate the what (inputs/outputs) from the how (evaluation strategy).
2. **Modularity**: Different evaluator implementations can be easily swapped, allowing for different evaluation strategies.
3. **Extensibility**: New evaluator types can be added without changing the core framework.
4. **Configurability**: Evaluators can be configured with different parameters to fine-tune their behavior.
5. **Reusability**: Evaluators can be reused across different agents.

## Best Practices

When using evaluators, consider the following best practices:

1. **Choose the Right Evaluator**: Different evaluators are suitable for different use cases. Choose the one that best fits your needs.
2. **Configure Appropriately**: Adjust the evaluator's configuration parameters to fine-tune its behavior.
3. **Test Thoroughly**: Test your evaluators with different inputs to ensure they behave as expected.
4. **Consider Performance**: Some evaluators may be more computationally intensive than others. Consider the performance implications of your choice.
5. **Handle Errors**: Implement error handling to make your evaluators more robust.

## Next Steps

Now that you understand evaluators, you might want to explore:

- [Agents](agents.md) - Learn more about Flock agents
- [Modules](modules.md) - Explore Flock's module system
- [Routers](routers.md) - Learn about dynamic agent chaining
- [Custom Agents](../advanced/custom-agents.md) - Create your own custom agents
