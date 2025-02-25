# Configuration

This guide explains how to configure Flock for your specific needs. Flock provides a flexible configuration system that allows you to customize various aspects of its behavior.

## Flock Configuration

When creating a Flock instance, you can provide various configuration options:

```python
from flock.core import Flock

flock = Flock(
    model="openai/gpt-4o",           # The default model to use
    local_debug=True,                # Whether to run in local debug mode
    enable_logging=True,             # Enable logging
    enable_telemetry=False,          # Disable telemetry
    temporal_executor_config=None,   # Temporal executor configuration
    telemetry_config=None,           # Telemetry configuration
    logger=None                      # Custom logger
)
```

### Model Configuration

The `model` parameter specifies the default model to use for agents that don't specify their own model:

```python
# Using OpenAI's GPT-4o model
flock = Flock(model="openai/gpt-4o")

# Using Anthropic's Claude model
flock = Flock(model="anthropic/claude-3-opus-20240229")

# Using a local model
flock = Flock(model="local/llama-3-70b")
```

### Execution Mode

The `local_debug` parameter determines whether to run in local debug mode or production mode:

```python
# Run in local debug mode (default)
flock = Flock(local_debug=True)

# Run in production mode (uses Temporal)
flock = Flock(local_debug=False)
```

### Logging Configuration

The `enable_logging` parameter enables or disables logging:

```python
# Enable all logging
flock = Flock(enable_logging=True)

# Enable specific loggers
flock = Flock(enable_logging=["flock", "agent", "memory"])

# Disable logging
flock = Flock(enable_logging=False)
```

You can also provide a custom logger:

```python
import logging

# Configure your logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("flock.log"),
        logging.StreamHandler()
    ]
)

# Create a Flock instance with your logger
flock = Flock(logger=logging.getLogger("my_flock"))
```

### Telemetry Configuration

The `enable_telemetry` parameter enables or disables telemetry:

```python
# Enable telemetry
flock = Flock(enable_telemetry=True)

# Disable telemetry
flock = Flock(enable_telemetry=False)
```

You can also provide a custom telemetry configuration:

```python
from flock.core.telemetry.telemetry_config import TelemetryConfig

# Configure telemetry
telemetry_config = TelemetryConfig(
    service_name="my-flock-service",
    exporter_type="otlp",
    exporter_endpoint="http://localhost:4317",
    resource_attributes={
        "deployment.environment": "production"
    }
)

# Create a Flock instance with telemetry
flock = Flock(
    enable_telemetry=True,
    telemetry_config=telemetry_config
)
```

### Temporal Configuration

If you're running in production mode (`local_debug=False`), you can provide a Temporal executor configuration:

```python
from flock.core.execution.temporal_executor import TemporalExecutorConfig

# Configure Temporal
temporal_config = TemporalExecutorConfig(
    retry_attempts=3,           # Maximum number of retry attempts
    retry_interval=5,           # Initial interval between retries (seconds)
    retry_max_interval=60,      # Maximum interval between retries (seconds)
    retry_coefficient=2.0,      # Coefficient to multiply the interval by after each retry
    task_queue="flock-queue",   # Temporal task queue name
    namespace="default",        # Temporal namespace
    server_url="localhost:7233" # Temporal server URL
)

# Create a Flock instance with Temporal
flock = Flock(
    local_debug=False,
    temporal_executor_config=temporal_config
)
```

## Agent Configuration

When creating a FlockAgent, you can provide various configuration options:

```python
from flock.core import FlockAgent

agent = FlockAgent(
    name="my_agent",                 # Agent name
    input="query: str",              # Input schema
    output="result: str",            # Output schema
    description="My agent",          # Agent description
    model="openai/gpt-4o",           # Model to use
    tools=[some_tool_function],      # Tools to use
    hand_off=next_agent,             # Next agent in the workflow
    evaluator=my_evaluator,          # Custom evaluator
    memory_mapping="...",            # Memory mapping
    modules=[my_module]              # Modules to attach
)
```

### Input and Output Schema

The `input` and `output` parameters define the input and output schema for the agent:

```python
# Simple schema
agent = FlockAgent(
    input="query",
    output="result"
)

# Schema with type hints
agent = FlockAgent(
    input="query: str",
    output="result: str"
)

# Schema with type hints and descriptions
agent = FlockAgent(
    input="query: str | The query to process",
    output="result: str | The processed result"
)

# Multiple inputs/outputs
agent = FlockAgent(
    input="query: str, context: str",
    output="result: str, confidence: float"
)
```

### Tools Configuration

The `tools` parameter specifies the tools that the agent can use:

```python
from flock.core.tools import basic_tools

# Single tool
agent = FlockAgent(
    tools=[basic_tools.web_search_duckduckgo]
)

# Multiple tools
agent = FlockAgent(
    tools=[
        basic_tools.web_search_duckduckgo,
        basic_tools.code_eval,
        basic_tools.get_current_time
    ]
)
```

### Handoff Configuration

The `hand_off` parameter specifies the next agent in the workflow:

```python
# Direct handoff to another agent
agent1.hand_off = agent2

# Handoff with additional input
from flock.core import HandOff
agent1.hand_off = HandOff(
    next_agent=agent2,
    input={"additional_data": "some value"}
)

# Dynamic handoff based on a function
def determine_next_agent(result):
    if result["confidence"] > 0.8:
        return agent2
    else:
        return agent3

agent1.hand_off = determine_next_agent

# Auto handoff (let the LLM decide)
agent1.hand_off = "auto_handoff"
```

### Evaluator Configuration

The `evaluator` parameter specifies the evaluator to use:

```python
from flock.evaluators.declarative import DeclarativeEvaluator
from flock.evaluators.natural_language import NaturalLanguageEvaluator

# Declarative evaluator (default)
agent = FlockAgent(
    evaluator=DeclarativeEvaluator(name="declarative")
)

# Natural language evaluator
agent = FlockAgent(
    evaluator=NaturalLanguageEvaluator(name="natural_language")
)
```

### Memory Configuration

The `memory_mapping` parameter specifies how memory should be used:

```python
# Simple memory mapping
agent = FlockAgent(
    memory_mapping="""
        query -> memory.semantic(threshold=0.9) -> result
    """
)

# Complex memory mapping
agent = FlockAgent(
    memory_mapping="""
        query -> memory.semantic(threshold=0.9, scope='global') |
        memory.filter(recency='7d') |
        memory.sort(by='relevance') |
        memory.combine
        -> findings
    """
)
```

### Module Configuration

The `modules` parameter specifies the modules to attach to the agent:

```python
from flock.modules.memory import MemoryModule, MemoryModuleConfig
from flock.modules.metrics import MetricsModule, MetricsModuleConfig

# Memory module
memory_module = MemoryModule(
    name="memory",
    config=MemoryModuleConfig(
        file_path="memory.json",
        save_after_update=True
    )
)

# Metrics module
metrics_module = MetricsModule(
    name="metrics",
    config=MetricsModuleConfig(
        metrics_dir="metrics",
        track_execution_time=True,
        track_token_usage=True
    )
)

# Attach modules to agent
agent = FlockAgent(
    modules=[memory_module, metrics_module]
)

# Or add modules after creation
agent.add_module(memory_module)
agent.add_module(metrics_module)
```

## Environment Variables

Flock also supports configuration via environment variables:

- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `TAVILY_API_KEY`: Tavily API key
- `FLOCK_MODEL`: Default model to use
- `FLOCK_LOCAL_DEBUG`: Whether to run in local debug mode
- `FLOCK_ENABLE_LOGGING`: Whether to enable logging
- `FLOCK_ENABLE_TELEMETRY`: Whether to enable telemetry
- `FLOCK_TEMPORAL_SERVER_URL`: Temporal server URL
- `FLOCK_TEMPORAL_NAMESPACE`: Temporal namespace

## Configuration File

You can also create a configuration file to store your settings:

```python
# config.py
OPENAI_API_KEY = "your-api-key"
DEFAULT_MODEL = "openai/gpt-4o"
LOCAL_DEBUG = True
ENABLE_LOGGING = True
ENABLE_TELEMETRY = False
```

Then import it in your code:

```python
import config
from flock.core import Flock

flock = Flock(
    model=config.DEFAULT_MODEL,
    local_debug=config.LOCAL_DEBUG,
    enable_logging=config.ENABLE_LOGGING,
    enable_telemetry=config.ENABLE_TELEMETRY
)
```

## Next Steps

Now that you understand how to configure Flock, you can:

- Learn about [Agents](../core-concepts/agents.md) in Flock
- Explore the [Type System](../core-concepts/type-system.md)
- Understand [Workflows](../core-concepts/workflows.md)
