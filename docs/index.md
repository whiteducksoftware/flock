# Flock by White Duck


<img src="/img/flock.png" width="800" style="display: block; margin: 0 auto;">





| Traditional Agent Frameworks 🙃          |                        Flock 🐤🐧🐓🦆                         |
|------------------------------------------|--------------------------------------------------------------|
| 🤖 **Complex Prompt Engineering**         | 📝 **Declarative Agent Definitions**                         |
| • Endless, brittle prompts               | • Just declare what each agent gets and produces             |
| • Fragile and hard-to-tune                | • No more manual prompt engineering                          |
|                                          |                                                              |
| 💥 **Fragile Execution**                  | ⚡ **Rock-Solid Reliability**                                 |
| • One crash and it’s game over           | • Built-in fault tolerance with automatic retries & recovery   |
| • Difficult to monitor and recover       | • Full observability and logging built right in              |
|                                          |                                                              |
| 🏗️ **Rigid, Static Workflows**             | 🔄 **Dynamic & Flexible Orchestration**                      |
| • Limited adaptability                   | • Modular, concurrent, and scalable workflows                |
| • Hard to change on the fly              | • Persistent state management and dynamic hand-offs            |

### v0.1 - The Flock Has Landed

Welcome to the first release of Flock!

Current agent frameworks are fun, but as a company of architects, consultants, and engineers, we found most of them somewhat lacking. To confidently recommend agents to our clients (and since everyone seems to need them!), we were left with only one viable solution:

**Write our own agent framework!**

Rather than reinvent the wheel, we’re building on the shoulders of giants—leveraging proven tools like Temporal, DSPy, Docling, and more—to make your life easier and your agents more manageable.

If you need an agent framework where testability and production readiness are core principles, look no further!

There’s still a long road ahead, and we appreciate any help.

Feel free to join the community and be part of the Flock!



## What’s Flock All About?

Flock is all about making LLM-powered agent systems simple, reliable, and scalable. Forget the hassle of long, convoluted prompts. With Flock, you declare:
- **Inputs:** What data your agent needs (with type hints and human‑readable descriptions).
- **Outputs:** What your agent produces.
- **Tools:** Optional extras that your agent can use to extend its functionality.

Flock handles the heavy lifting—parsing your declarations, building precise prompts, configuring the underlying LLM, and even managing fault tolerance with Temporal. It’s designed for modern production environments where testability and reliability are a must.

## Key Features

- **Declarative Agent Definitions:**  
  Simply state what your agents require and what they produce. No more prompt engineering headaches!

- **Lifecycle Hooks:**  
  Customize your agent’s behavior with built-in hooks (`initialize()`, `terminate()`, and `on_error()`). This gives you full control over setup, cleanup, and error handling.

- **Rock-Solid Reliability:**  
  With Temporal integration, your agents get automatic retries, durable state, and robust error handling. One agent’s crash won’t bring down the whole system.

- **Type Safety & JSON Serialization:**  
  Agents are built as Pydantic models—ensuring strong typing, easy JSON (de)serialization, and straightforward testing.

- **DSPy Integration:**  
  Flock leverages DSPy to interact with LLMs. It extracts type hints and descriptions to generate precise, context-rich prompts.

- **Flexible Orchestration:**  
  Whether running locally for debugging or deploying in production, Flock supports dynamic agent chaining, parallel execution, and batch processing.

## Advanced Usage

### Agents with Tools

Integrate external tools (like web search, code evaluation, etc.) to boost your agents’ capabilities:

```python
from flock.core.tools import basic_tools

research_agent = FlockAgent(
    name="research_agent",
    input="research_topic: str|Topic to investigate",
    output="research_result: str|Outcome of the research",
    tools=[basic_tools.web_search_tavily],
)
```

### Agent Chaining

Build complex workflows by chaining agents together:

```python
# First agent in the chain
project_plan_agent = FlockAgent(
    name="project_plan_agent",
    input="project_idea: str|Initial project idea",
    output="plan_headings: list[str]|Headings for the project plan",
    tools=[basic_tools.web_search_tavily, basic_tools.code_eval],
)

# Second agent that refines the plan
content_agent = FlockAgent(
    name="content_agent",
    input="context: dict|Global context, project_plan_agent.plan_headings: list[str]|Plan headings",
    output="project_plan_content: str|Detailed content for each heading",
)

# Set up hand-off: project_plan_agent passes its output to content_agent
project_plan_agent.hand_off = content_agent
```

### Running on Temporal

For enterprise-grade reliability, run your agents on Temporal:
- Automatic retries, durable state, and robust error handling ensure your workflows keep running.
- Scale distributed workflows effortlessly.

```python
result = await flock.run_async(
    start_agent=bloggy,
    input="a blog about cats",
    local_debug=False  # Switch this off to run on Temporal
)
```



## Evolution & Future Direction

Flock was born from our frustration with existing agent frameworks. We believe that agents should be simple, reliable, and production-ready. Our focus is on:

- **Declarative Simplicity:**  
  Forget endless prompts—just declare your agent’s interface and let Flock handle the rest.

- **Production-Grade Reliability:**  
  With Temporal integration and robust error handling, your agents keep on running no matter what.

- **Flexibility & Modularity:**  
  Build complex workflows effortlessly with dynamic chaining and a rich tool ecosystem.

- **Enhanced Observability:**  
  Built-in logging and monitoring provide full insights into your workflows.

Join us as we revolutionize AI agent systems—simple, reliable, and powerful!


## Contributing

Contributions are welcome! Join our community on GitHub, submit Pull Requests, and help us build the future of AI agent systems.

## License

This project is licensed under the terms of the LICENSE file in the repository.

## Acknowledgments

- Built with [DSPy](https://github.com/stanfordnlp/dspy)
- Uses [Temporal](https://temporal.io/) for workflow management
- Integrates with [Tavily](https://tavily.com/) for web search capabilities
- Web interface built with FastHTML and MonsterUI