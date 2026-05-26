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
my_flock = Flock(model="openai/gpt-4o")

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

## 📹 Video Demo

https://github.com/user-attachments/assets/bdab4786-d532-459f-806a-024727164dcc



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
# Common tools (Tavily, Markdownify)
uv pip install flock-core[all-tools]

# All optional dependencies (including tools, docling, etc.)
uv sync --all-extras
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


## 🐤 New in Flock 0.4.0 `Magpie` 🐤
<p align="center">
<img width="300" alt="image" src="https://github.com/user-attachments/assets/34c2fe2f-6dd2-498c-a826-1687cb158755" />
</p>

### 0.4.5 - MCP Support - Declaratively connect to 1000s of different tools!

Create a server

```python 
ws_fetch_server = FlockFactory.create_mcp_server(
    name="fetch_server",
    enable_tools_feature=True,
    connection_params=FlockFactory.WebsocketParams(
        url="ws://localhost:4001/message"
    ),
```

Add it to Flock

```python 
flock = Flock(
    name="mcp_testbed",
    servers=[
        ws_fetch_server
    ]
)
```

And tell the flock agents which server to use

```python 
webcrawler_agent = FlockFactory.create_default_agent(
    name="webcrawler_agent",
    description="Expert for looking up and retrieving web content",
    input="query: str | User-Query, initial_url: Optional[str] | Optional url to start search from.",
    output="answer: str | Answer to user-query, page_url: str | The url of the page where the answer was found on, page_content: str | Markdown content of the page where the answer was found.",
    servers=[ws_fetch_server], # servers are passed here.
)
```

Done! The Flock agent has now access to every tool the server offers.


### 🚀 REST API – Deploy Flock Agents as REST API Endpoints

Easily deploy your Flock agents as scalable REST API endpoints. Interact with your agent workflows via standard HTTP requests.

The all-in-one `flock.serve()` method turns your Flock into a proper REST API!

<img width="1135" alt="image" src="https://github.com/user-attachments/assets/95a58e96-d866-4fd1-aca3-c7635843503c" />

Need custom endpoints to wrap abstract agent logic or add business logic? We've got you.
Define them. Declaratively.

```python
word_count_route = FlockEndpoint(
    path="/api/word_count",
    methods=["GET"],
    callback=word_count,
    query_model=WordCountParams,
    response_model=WordCountResponse,
    summary="Counts words in a text",
    description="Takes a text and returns the number of words in it.",
)

flock.serve(custom_endpoints=[img_url_route, word_count_route, yoda_route])
```

<img width="1135" alt="image" src="https://github.com/user-attachments/assets/d9315648-ac10-4129-aca4-1cb4c8835672" />

Want chat and UI too? Just turn them on.

```python
flock.serve(ui=True, chat=True)
```

---

### 🖥️ Web UI – Test Flock Agents in the Browser

Test and interact with your Flock agents directly in your browser using an integrated web interface.

![image](https://github.com/user-attachments/assets/5746ae82-757b-43a3-931d-56d19d39371a)

Highlights of this feature-rich interface:

* Run all your agents and agent flows
* Chat with your agents
* Create sharable links – these freeze agent config so testers can focus on evaluation
* Send direct feedback – includes everything needed to reproduce issues
* Switch modes – like standalone chat mode, which hides all but the chat

<img width="1135" alt="image" src="https://github.com/user-attachments/assets/398337ee-e56e-4bce-8bd8-d258c261cb64" />

And much, much more... All features are based on real-world client feedback and serve actual business needs.

---

### ⌨️ CLI Tool – Manage Flock Agents via Command Line

Manage configurations, run agents, and inspect results – all from your terminal. A quick way to test and validate serialized flocks.

![image](https://github.com/user-attachments/assets/9370e7e8-94c3-4e26-8c7e-46ff2edd667a)

---

### 💾 Enhanced Serialization – Share, Deploy, and Run Flocks from YAML

Define and share entire Flock configurations using readable YAML files. Perfect for versioning, deployment, and portability.

Take note how even custom types like `FantasyCharacter` are serialized so the target system doesn't even need your code! Everything portable!

```yaml
name: pydantic_example
model: openai/gpt-4o
enable_temporal: false
show_flock_banner: false
temporal_start_in_process_worker: true
agents:
  character_agent:
    name: character_agent
    model: openai/gpt-4o
    description: Generates fantasy RPG character profiles for a specified number of
      characters.
    input: 'number_of_characters: int | The number of fantasy character profiles to
      generate.'
    output: 'character_list: list[FantasyCharacter] | A list containing the generated
      character profiles.'
    write_to_file: false
    wait_for_input: false
    evaluator:
      name: default
      config:
        model: openai/gpt-4o
        use_cache: true
        temperature: 0.8
        max_tokens: 8192
        stream: false
        include_thought_process: false
        kwargs: {}
      type: DeclarativeEvaluator
    modules:
      output:
        name: output
        config:
          enabled: true
          theme: abernathy
          render_table: false
          max_length: 1000
          truncate_long_values: true
          show_metadata: true
          format_code_blocks: true
          custom_formatters: {}
          no_output: false
          print_context: false
        type: OutputModule
      metrics:
        name: metrics
        config:
          enabled: true
          collect_timing: true
          collect_memory: true
          collect_token_usage: true
          collect_cpu: true
          storage_type: json
          metrics_dir: metrics/
          aggregation_interval: 1h
          retention_days: 30
          alert_on_high_latency: true
          latency_threshold_ms: 30000
        type: MetricsModule
types:
  FantasyCharacter:
    module_path: __main__
    type: pydantic.BaseModel
    schema:
      description: 'Data model for fantasy RPG character information.

        Docstrings and Field descriptions can help guide the LLM.'
      properties:
        name:
          description: A creative fantasy character name.
          title: Name
          type: string
        race:
          description: The character's race.
          enum:
          - human
          - elf
          - dwarf
          - orc
          - halfling
          title: Race
          type: string
        class_type:
          description: The character's class.
          enum:
          - warrior
          - mage
          - rogue
          - cleric
          - ranger
          title: Class Type
          type: string
        level:
          description: Character level
          title: Level
          type: integer
        strength:
          description: Strength stat
          title: Strength
          type: integer
        dexterity:
          description: Dexterity stat
          title: Dexterity
          type: integer
        constitution:
          description: Constitution stat
          title: Constitution
          type: integer
        intelligence:
          description: Intelligence stat
          title: Intelligence
          type: integer
        wisdom:
          description: Wisdom stat
          title: Wisdom
          type: integer
        charisma:
          description: Charisma stat
          title: Charisma
          type: integer
        weapons:
          description: A list of weapons the character carries.
          items:
            type: string
          title: Weapons
          type: array
        backstory:
          description: A brief, engaging backstory (2-3 sentences).
          title: Backstory
          type: string
        motivation:
          description: The character's motivation for their adventuring.
          title: Motivation
          type: string
        alignment:
          description: Character's moral alignment
          title: Alignment
          type: string
      required:
      - name
      - race
      - class_type
      - level
      - strength
      - dexterity
      - constitution
      - intelligence
      - wisdom
      - charisma
      - weapons
      - backstory
      - motivation
      - alignment
      type: object
components:
  DeclarativeEvaluator:
    type: flock_component
    module_path: flock.evaluators.declarative.declarative_evaluator
    file_path: src\\flock\\evaluators\\declarative\\declarative_evaluator.py
    description: Evaluator that uses DSPy for generation.
  OutputModule:
    type: flock_component
    module_path: flock.modules.output.output_module
    file_path: src\\flock\\modules\\output\\output_module.py
    description: Module that handles output formatting and display.
  MetricsModule:
    type: flock_component
    module_path: flock.modules.performance.metrics_module
    file_path: src\\flock\\modules\\performance\\metrics_module.py
    description: Module for collecting and analyzing agent performance metrics.
dependencies:
- pydantic>=2.0.0
- flock-core>=0.4.0
metadata:
  path_type: relative
  flock_version: 0.4.0

```

Why is text-based serialization cool? Because agents can manipulate their own config – go wild with meta agents and experiments.

---

### 🌀 New Execution Flows – Batch and Evaluation Modes

Run Flock in batch mode to process multiple inputs or in evaluation mode to benchmark agents against question/answer pairs.

```python
batch_data = [
    {"topic": "Robot Kittens", "audience": "Tech Enthusiasts"},
    {"topic": "AI in Gardening", "audience": "Homeowners"},
    ...
]

static_data = {"number_of_slides": 6}

silent_results = flock.run_batch(
    start_agent=presentation_agent,
    batch_inputs=batch_data,
    static_inputs=static_data,
    parallel=True,
    max_workers=5,
    silent_mode=True,
    return_errors=True,
    write_to_csv=".flock/batch_results.csv",
)
```

Supports CSV in and out. Combine with `.evaluate()` to benchmark Flock with known Q/A sets.

---

### ⏱️ First-Class Temporal Integration

Flock 0.4.0 brings seamless integration with Temporal.io. Build production-grade, reliable, and scalable agent workflows.

```python
flock = Flock(
    enable_temporal=True,
    temporal_config=TemporalWorkflowConfig(
        task_queue="flock-test-queue",
        workflow_execution_timeout=timedelta(minutes=10),
        default_activity_retry_policy=TemporalRetryPolicyConfig(
            maximum_attempts=2
        ),
    ),
)
```

Just set a flag. Add your constraints. Now you've got retry policies, timeout control, and error handling baked in.

---

### ✨ Utility – @flockclass Hydrator

Flock also adds conveniences. With `@flockclass`, you can turn any Pydantic model into a self-hydrating agent.

```python
from pydantic import BaseModel
from flock.util.hydrator import flockclass

@flockclass(model="openai/gpt-4o")
class CharacterIdea(BaseModel):
    name: str
    char_class: str
    race: str
    backstory_hook: str | None = None
    personality_trait: str | None = None

async def create_character():
    char = CharacterIdea(name="Gorok", char_class="Barbarian", race="Orc")
    print(f"Before Hydration: {char}")

    hydrated_char = await char.hydrate()

    print(f"\nAfter Hydration: {hydrated_char}")
    print(f"Backstory Hook: {hydrated_char.backstory_hook}")
```



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
