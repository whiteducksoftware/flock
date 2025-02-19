# Welcome to Flock

![Flock Banner](assets/images/flock.png){ width="800" }


Flock is a powerful framework for orchestrating LLM-powered agents that takes a fresh approach to agent development. Instead of wrestling with complex prompts, you simply declare what your agents need and what they should produce—Flock handles the rest.

## Why Flock?

Flock transforms how you build and deploy LLM-powered agents through its innovative declarative approach:

### 🎯 Declarative Agent Definitions

Instead of writing lengthy, brittle prompts, simply specify:

- What inputs your agent needs
- What outputs it should produce
- Let Flock handle the rest

### ⚡ Built with platforming in mind
- **Fault Tolerance**: Built-in retries and error handling through Temporal integration
- **State Management**: Robust handling of agent state and workflows
- **Automatic Recovery**: Self-healing capabilities for production deployments

### 🔄 Flexible & Scalable
- Dynamic agent chaining and hand-offs
- Modular, concurrent, and batch processing
- Easily adaptable to changing requirements

## Key Innovations

### 🎨 Declarative Agent System
Just like ordering a pizza—you specify what you want, not the 30 steps to make it! Thanks to LLMs, Flock can figure out those steps automatically. Define agents through clear input/output interfaces using concise syntax, and let Flock handle the complexity.

### 🔒 Type Safety & Clear Contracts
- Built on Pydantic models for robust type safety
- Automatic JSON serialization/deserialization
- Clear contracts for inputs and outputs
- Simplified testing and validation

### 🛠 Unparalleled Flexibility

- Every aspect of an agent can be customized
- Lifecycle hooks (`initialize()`, `terminate()`, `evaluate()`, `on_error()`)
- Setup and cleanup procedures
- Error handling strategies
- Dynamic property configuration

### ⚙️ Deployment with Temporal
- Automatic retries
- Durable state management
- Resilient workflows
- Built-in monitoring and observability

### 🔍 Observability with Open Telemetry and Temporal
- Tracing of all events
- Supports Jaeger, SQL and File Sinks out of the box
- Built-in monitoring and observability

## Quick Start

```python
from flock.core import Flock, FlockAgent

MODEL = "openai/gpt-4"

flock = Flock(model=MODEL, local_debug=True)

bloggy = FlockAgent(
    name="bloggy", 
    input="blog_idea", 
    output="funny_blog_title, blog_headers"
)
flock.add_agent(bloggy)

result = flock.run(
    start_agent=bloggy, 
    input={"blog_idea": "A blog about cats"}
)
```

## Ready to Get Started?

Check out our guides:

- [Quick Start Guide](getting-started/quickstart.md)
- [Core Concepts](core-concepts/agents.md)
- [Examples](examples/hello-flock.md)

## Join the Flock!

Flock is actively developed and maintained by [whiteduck](https://whiteduck.de). We welcome contributions and feedback from the community as we build the next generation of reliable, production-ready AI agent systems.

---

For detailed documentation on specific features, explore our sidebar navigation. Let's build something amazing together! 🚀