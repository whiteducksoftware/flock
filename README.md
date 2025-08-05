<p align="center">
  <!-- Placeholder for your Flock Logo/Banner - Replace URL -->
  <img alt="Flock Banner" src="https://raw.githubusercontent.com/whiteducksoftware/flock/master/docs/assets/images/flock.png" width="600">
</p>
<p align="center">
  <!-- Update badges -->
  <a href="https://pypi.org/project/flock-core/" target="_blank"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/flock-core?style=for-the-badge&logo=pypi&label=pip%20version"></a>
  <img alt="Python Version" src="https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python">
  <a href="https://github.com/whiteducksoftware/flock/actions/workflows/deploy-whiteduck-pypi.yml" target="_blank"><img alt="CI Status" src="https://img.shields.io/github/actions/workflow/status/whiteducksoftware/flock/deploy-whiteduck-pypi.yml?branch=master&style=for-the-badge&logo=githubactions&logoColor=white"></a>
  <a href="https://github.com/whiteducksoftware/flock/blob/master/LICENSE" target="_blank"><img alt="License" src="https://img.shields.io/pypi/l/flock-core?style=for-the-badge"></a>
  <a href="https://whiteduck.de" target="_blank"><img alt="Built by white duck" src="https://img.shields.io/badge/Built%20by-white%20duck%20GmbH-white?style=for-the-badge&labelColor=black"></a>
  <a href="https://www.linkedin.com/company/whiteduck" target="_blank"><img alt="LinkedIn" src="https://img.shields.io/badge/linkedin-%230077B5.svg?style=for-the-badge&logo=linkedin&logoColor=white&label=whiteduck"></a>
<a href="https://bsky.app/profile/whiteduck-gmbh.bsky.social" target="_blank"><img alt="Bluesky" src="https://img.shields.io/badge/bluesky-Follow-blue?style=for-the-badge&logo=bluesky&logoColor=%23fff&color=%23333&labelColor=%230285FF&label=whiteduck-gmbh"></a>
</p>


---


## The Problem You Know Too Well

🤯 **Prompt Hell**: Brittle 500-line prompts that break with every model update.  
💥 **System Failures**: One bad LLM response crashes your entire workflow  
🧪 **Testing Nightmares**: "How do I unit test a prompt?" (You don't.)  
🧪 **Measuring Quality**: "How do I know my prompts are close to optimal?" (You also don't.)  
📄 **Output Chaos**: Parsing unstructured LLM responses into reliable data  
⛓️ **Orchestration Limits**: Moving beyond simple chains and DAGs? Good luck  
🚀 **Production Gap**: Jupyter notebooks don't scale to enterprise systems  

*After building dozens of AI systems for enterprise clients, we realized the tooling was fundamentally broken.*


**Build with agents, not against them.**


## The Flock Solution

**What if you could just skip that 'prompt engineering' step?**

Flock is an agent framework for declarative AI workflows. You define what goes in and what should come out, the how is handled by the agent.   
No brittle prompts. No guesswork. Just reliable, testable AI agents.


✅ **Declarative Contracts**: Define inputs/outputs with Pydantic models. Flock handles the LLM complexity.  
⚡ **Built-in Resilience**: Automatic retries, state persistence, and workflow resumption via Temporal.io  
🧪 **Actually Testable**: Clear contracts make agents unit-testable like any other code  
🧪 **Optimal Quality**: Agents posses multiple self-optimization algorithms based on latest research  
🚀 **Dynamic Workflows**: Self-correcting loops, conditional routing, and intelligent decision-making  
🔧 **Zero-Config Production**: Deploy as REST APIs with one command. Scale without rewriting.

**Ready to see it in action?**

## ⚡ Quick Start

```python
from flock.core import Flock, FlockFactory

# 1. Create the main orchestrator
my_flock = Flock(model="openai/gpt-4.1")

# 2. Declaratively define an agent
brainstorm_agent = FlockFactory.create_default_agent(
    name="idea_generator",
    input="topic",
    output="catchy_title, key_points"
)

# 3. Add the agent to the Flock
my_flock.add_agent(brainstorm_agent)

# 4. Run the agent!
input_data = {"topic": "The future of AI agents"}
result = my_flock.run(start_agent="idea_generator", input=input_data)

# The result is a Box object (dot-accessible dict)
print(f"Generated Title: {result.catchy_title}")
print(f"Key Points: {result.key_points}")
```

**No 20-line prompt fiddling. Just structured output, every time.**

![image](https://github.com/user-attachments/assets/37a897cb-910f-49fc-89d4-510a780ad775)

**Explore more examples →** [**Flock Showcase Repository**](https://github.com/whiteducksoftware/flock-showcase)



## 💾 Installation - Use Flock in your project

Get started with the core Flock library:

```bash
# Using uv (recommended)
uv pip install flock-core

# Using pip
pip install flock-core
```

Extras: Install optional dependencies for specific features:

```bash
# Flock tools and mcp server
uv pip install flock-mcp
```

## 🔑 Installation - Develop Flock

```bash
git clone https://github.com/whiteducksoftware/flock.git
cd flock

# One-liner dev setup after cloning
pip install poethepoet && poe install
```

Additional provided `poe` tasks and commands:

```bash
poe install # Install the project
poe build # Build the project
poe docs # Serve the docs
poe format # Format the code
poe lint # Lint the code
```

## 🔑 Environment Setup

Flock uses environment variables (typically in a .env file) for configuration, especially API keys. Create a .env file in your project root:

```bash
# .env - Example

# --- LLM Provider API Keys (Required by most examples) ---
# Add keys for providers you use (OpenAI, Anthropic, Gemini, Azure, etc.)
# Refer to litellm docs (https://docs.litellm.ai/docs/providers) for names
OPENAI_API_KEY="your-openai-api-key"
# ANTHROPIC_API_KEY="your-anthropic-api-key"

# --- Tool-Specific Keys (Optional) ---
# TAVILY_API_KEY="your-tavily-search-key"
# GITHUB_PAT="your-github-personal-access-token"

# --- Default Flock Settings (Optional) ---
DEFAULT_MODEL="openai/gpt-4o" # Default LLM if agent doesn't specify

# --- Flock CLI Settings (Managed by `flock settings`) ---
# SHOW_SECRETS="False"
# VARS_PER_PAGE="20"
```

Be sure that the .env file is added to your .gitignore!


## 🐤 New in Flock 0.5.0 `Kea` 🐤

Keas are one of the smartest birds in the world famous for figuring out multi-step puzzles, unlatching doors, and coordinating in small groups to get what it wants.

<Insert Kea Logo>

### Self-optimizing agents

### Everything you need to evaluate and optimize agents

### Benchmarks

### Smooth Jupyter experience

### Multi-Threading and Thread Safety


--------------------------------

## 📚 Examples & Tutorials

For a comprehensive set of examples, ranging from basic usage to complex projects and advanced features, please visit our dedicated showcase repository:

➡️ [github.com/whiteducksoftware/flock-showcase](https://github.com/whiteducksoftware/flock-showcase) ⬅️

The showcase includes:

- Step-by-step guides for core concepts.
- Examples of tool usage, routing, memory, and more.
- Complete mini-projects demonstrating practical applications.

## 📖 Documentation

Full documentation, including API references and conceptual explanations, can be found at:

➡️ [whiteducksoftware.github.io/flock/](https://whiteducksoftware.github.io/flock/) ⬅️

## 🤝 Contributing

We welcome contributions! Please see the CONTRIBUTING.md file (if available) or open an issue/pull request on GitHub.

Ways to contribute:

- Report bugs or suggest features.
- Improve documentation.
- Contribute new Modules, Evaluators, or Routers.
- Add examples to the flock-showcase repository.

## 📜 License

Flock is licensed under the MIT License. See the LICENSE file for details.

## 🏢 About

Flock is developed and maintained by white duck GmbH, your partner for cloud-native solutions and AI integration.
