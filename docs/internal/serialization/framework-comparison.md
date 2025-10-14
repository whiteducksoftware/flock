# Framework Comparison: Agent Serialization Patterns

**Date**: 2025-10-13
**Research Scope**: How major AI agent frameworks handle agent serialization

---

## Executive Summary

All major AI agent frameworks (AutoGen, LangChain, CrewAI, Semantic Kernel, Haystack) have **standardized on YAML/JSON + Pydantic + Function Registry** architecture. None use pickle for configuration serialization.

**Key Finding**: Even Microsoft's AutoGen (v0.4) explicitly states: _"Tools NOT YET supported in component serialization"_ - demonstrating that **tool/function serialization remains the hardest problem** in the industry.

---

## Framework Comparison Matrix

| Framework | Primary Format | Code Handling | Security Model | Cross-Machine | Documentation URL |
|-----------|---------------|---------------|----------------|---------------|-------------------|
| **AutoGen v0.4** | Component serialization | Tools NOT YET supported | Trusted sources only | Yes | [Link](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/serialize-components.html) |
| **LangChain** | JSON via Serializable | Function by reference | Secrets separated | Yes | [Link](https://python.langchain.com/docs/how_to/serialization/) |
| **LangGraph** | SQLite/Postgres checkpoints | State only, not code | State isolation | Yes | [Link](https://langchain-ai.github.io/langgraph/concepts/persistence/) |
| **CrewAI** | YAML-first | Tools as code references | Clean separation | Yes | [Link](https://docs.crewai.com/en/concepts/agents) |
| **Semantic Kernel** | JSON Schema | Plugin registration | Automatic namespacing | Yes | [Link](https://learn.microsoft.com/en-us/semantic-kernel/concepts/plugins/) |
| **Haystack** | YAML only | Component types by path | Callback hooks | Yes | [Link](https://docs.haystack.deepset.ai/docs/serialization) |

---

## 1. AutoGen v0.4 (Microsoft)

### Serialization Approach

**Component-Based Serialization**: AutoGen v0.4 can serialize agent components, but **tools are not yet supported**.

### Code Example

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models import OpenAIChatCompletionClient

# Create agent
agent = AssistantAgent(
    name="assistant",
    model_client=OpenAIChatCompletionClient(model="gpt-4"),
    description="A helpful assistant",
)

# Serialize to dict
component_config = agent.dump_component()

# Save to JSON
import json
with open("agent_config.json", "w") as f:
    json.dump(component_config, f)

# Deserialize
agent_restored = AssistantAgent.load_component(component_config)
```

### Key Insights

**Strengths**:
- ✅ Clean component abstraction
- ✅ JSON-based (human-readable)
- ✅ Works with model clients

**Limitations**:
- ⚠️ **Tools NOT YET supported** (as of v0.4)
- ⚠️ State not persisted (only configuration)
- ⚠️ Requires "trusted sources" for security

**Quote from Documentation**:
> "Note: Tool objects are not yet serializable and will be ignored during serialization."

**Lesson**: Even Microsoft struggles with tool serialization - this validates that **function registry is the right approach**.

---

## 2. LangChain (JSON Serialization)

### Serialization Approach

**Serializable Interface**: LangChain uses a `Serializable` base class with JSON serialization.

### Code Example

```python
from langchain_core.load import dumpd, load

# Create a chain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant"),
    ("user", "{input}"),
])
llm = ChatOpenAI(model="gpt-4")
chain = prompt | llm

# Serialize to dict
serialized = dumpd(chain)

# Save to JSON
import json
with open("chain.json", "w") as f:
    json.dump(serialized, f)

# Deserialize
chain_restored = load(serialized)
```

### Key Insights

**Strengths**:
- ✅ **Secrets separated** - API keys not in serialized form
- ✅ **Lossless serialization** - Full chain reconstruction
- ✅ **Namespace isolation** - `["langchain", "prompts", "ChatPromptTemplate"]` paths

**Limitations**:
- ⚠️ Functions/tools serialized **by reference** (must be importable)
- ⚠️ No support for lambdas (raises error)

**Example Serialized Output**:
```json
{
  "lc": 1,
  "type": "constructor",
  "id": ["langchain", "prompts", "chat", "ChatPromptTemplate"],
  "kwargs": {
    "messages": [
      {
        "lc": 1,
        "type": "constructor",
        "id": ["langchain", "prompts", "SystemMessagePromptTemplate"],
        "kwargs": {"prompt": {"template": "You are a helpful assistant"}}
      }
    ]
  }
}
```

**Lesson**: Import paths work for well-structured code, but break for dynamic functions.

---

## 3. LangGraph (Checkpoint-Based Persistence)

### Serialization Approach

**State Checkpointing**: LangGraph persists conversation state, not agent configuration.

### Code Example

```python
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph

# Create graph with checkpointer
checkpointer = SqliteSaver.from_conn_string(":memory:")
graph = StateGraph(state_schema=MyState)
graph.add_node("agent", my_agent_function)
app = graph.compile(checkpointer=checkpointer)

# Run with thread ID
config = {"configurable": {"thread_id": "conversation-1"}}
result = app.invoke({"input": "Hello"}, config)

# State automatically persisted to SQLite
# Resume later:
result2 = app.invoke({"input": "Continue"}, config)
```

### Key Insights

**Strengths**:
- ✅ **Production-ready** - SQLite, Postgres, Redis support
- ✅ **State isolation** - Thread-based conversation tracking
- ✅ **Time-travel** - Can rewind to any checkpoint

**Limitations**:
- ⚠️ **State only** - Does not serialize agent configuration
- ⚠️ **Runtime persistence** - Not for cross-machine transfer

**Lesson**: State persistence ≠ agent configuration serialization. We need both.

---

## 4. CrewAI (YAML-First Design)

### Serialization Approach

**YAML Configuration**: CrewAI uses YAML files that non-technical users can edit.

### Code Example

**`config/agents.yaml`**:
```yaml
researcher:
  role: "Senior Researcher"
  goal: "Discover groundbreaking technologies"
  backstory: "A curious mind with a passion for innovation"
  tools:
    - web_search_tool
    - scrape_tool
  llm: gpt-4

writer:
  role: "Content Writer"
  goal: "Craft compelling narratives"
  backstory: "A creative storyteller"
  tools:
    - text_formatter
  llm: gpt-3.5-turbo
```

**Python Code**:
```python
from crewai import Agent, Crew
import yaml

# Load from YAML
with open("config/agents.yaml") as f:
    agent_configs = yaml.safe_load(f)

# Create agents
researcher = Agent(
    role=agent_configs["researcher"]["role"],
    goal=agent_configs["researcher"]["goal"],
    backstory=agent_configs["researcher"]["backstory"],
    tools=resolve_tools(agent_configs["researcher"]["tools"]),  # Registry lookup
    llm=agent_configs["researcher"]["llm"],
)

crew = Crew(agents=[researcher, writer])
```

### Key Insights

**Strengths**:
- ✅ **Human-editable** - Non-developers can modify agents
- ✅ **Tools by name** - String references to registry
- ✅ **Clean separation** - Configuration vs code

**Limitations**:
- ⚠️ Requires tool registry implementation
- ⚠️ Tools must be pre-registered

**Lesson**: YAML + function registry enables non-technical agent editing - powerful for productization.

---

## 5. Semantic Kernel (Plugin Registration)

### Serialization Approach

**Function Calling Schema**: Semantic Kernel uses OpenAI function calling schemas for plugins.

### Code Example

```python
import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

kernel = sk.Kernel()

# Register plugins
kernel.import_skill(MySkillClass(), skill_name="MySkill")

# Plugins are automatically converted to JSON Schema:
# {
#   "name": "MySkill-MyFunction",
#   "description": "Does something useful",
#   "parameters": {
#     "type": "object",
#     "properties": {
#       "input": {"type": "string", "description": "The input"}
#     }
#   }
# }

# Serialize kernel configuration
config = kernel.serialize()  # Returns JSON with plugin references
```

### Key Insights

**Strengths**:
- ✅ **Automatic marshalling** - Functions → JSON Schema
- ✅ **Namespace isolation** - `SkillName-FunctionName` pattern
- ✅ **LLM-friendly** - Direct OpenAI function calling

**Limitations**:
- ⚠️ Plugins must be C# classes or Python functions
- ⚠️ No support for lambdas

**Lesson**: JSON Schema is excellent for LLM integration, but requires structured functions.

---

## 6. Haystack (Component-Based Pipelines)

### Serialization Approach

**YAML Pipelines**: Haystack serializes entire pipelines as YAML with component type paths.

### Code Example

**`pipeline.yaml`**:
```yaml
components:
  retriever:
    type: haystack.components.retrievers.InMemoryBM25Retriever
    init_parameters:
      top_k: 10

  prompt_builder:
    type: haystack.components.builders.PromptBuilder
    init_parameters:
      template: "Context: {{context}}\n\nQuestion: {{question}}"

  llm:
    type: haystack.components.generators.OpenAIGenerator
    init_parameters:
      model: gpt-4
      api_key:
        type: env_var
        env_vars: [OPENAI_API_KEY]

connections:
  - sender: retriever.documents
    receiver: prompt_builder.context
  - sender: prompt_builder.prompt
    receiver: llm.prompt
```

**Python Code**:
```python
from haystack import Pipeline

# Load from YAML
pipeline = Pipeline.loads(yaml_content)

# Or save to YAML
pipeline.dumps()  # Returns YAML string
```

### Key Insights

**Strengths**:
- ✅ **Import path resolution** - `type: module.Class`
- ✅ **Environment variables** - Secrets via env vars
- ✅ **Visual pipelines** - Easy to understand flow

**Limitations**:
- ⚠️ Requires all components be importable
- ⚠️ No custom lambda support

**Lesson**: Import paths work well for structured components, but require clean module organization.

---

## Common Patterns Across All Frameworks

### 1. **No Pickle for Configuration**

All frameworks avoid pickle for agent configuration:
- **Security**: Pickle enables arbitrary code execution
- **Portability**: Pickle is Python version dependent
- **Debugging**: Binary blobs are not human-readable

### 2. **Function Registry Pattern**

All frameworks use string references to functions:
- **AutoGen**: Component IDs
- **LangChain**: Import paths (`["langchain", "prompts", "ChatPromptTemplate"]`)
- **CrewAI**: Tool names (`web_search_tool`)
- **Semantic Kernel**: Skill-Function names (`MySkill-MyFunction`)
- **Haystack**: Import paths (`haystack.components.retrievers.InMemoryBM25Retriever`)

### 3. **Secrets Separation**

All frameworks separate secrets from configuration:
- **Environment variables**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- **Secret managers**: AWS Secrets Manager, Azure Key Vault
- **Config files**: `.env` files excluded from version control

### 4. **State vs Configuration**

All frameworks distinguish:
- **Configuration** (serializable): Agent structure, parameters, tool references
- **State** (runtime): Conversation history, semaphores, connections

---

## Security Analysis

### CVE-2025-1716: Pickle Bypass Vulnerability

**Severity**: CRITICAL
**Affected**: All pickle-based serialization

**Attack Vector**:
```python
import pickle
import os

class Exploit:
    def __reduce__(self):
        return (os.system, ('rm -rf /',))  # ❌ RCE

# Attacker crafts malicious agent:
agent_yaml = """
name: evil_agent
tools: !!python/object/apply:pickle.loads
  - """ + base64.b64encode(pickle.dumps(Exploit())).decode() + """
"""

# Victim loads:
agent = Agent.from_yaml(agent_yaml)  # ❌ Remote code execution
```

**Mitigation**: **NEVER use pickle for user-provided configuration**

### Safe Alternatives

**1. YAML with safe_load**:
```python
import yaml
config = yaml.safe_load(yaml_content)  # ✅ No code execution
```

**2. Pydantic Validation**:
```python
from pydantic import BaseModel

class AgentConfig(BaseModel):
    name: str
    tools: list[str]  # ✅ Validated strings only

config = AgentConfig(**yaml_data)
```

**3. Function Registry**:
```python
# Pre-register safe functions
TOOL_REGISTRY = {
    "web_search": web_search_tool,
    "calculator": calculator_tool,
}

# Resolve from config
tools = [TOOL_REGISTRY[name] for name in config["tools"]]  # ✅ Controlled
```

---

## Recommendations for Flock

### Stop Doing (Legacy v0.4)
- ❌ YAML + pickle + base64
- ❌ Binary serialization for human-editable config
- ❌ Lambdas in YAML (pickling)

### Start Doing (v0.2+)
- ✅ YAML + Pydantic validation (follow CrewAI, Haystack)
- ✅ Function registry with string IDs (follow all frameworks)
- ✅ Import path resolution (follow LangChain, Haystack)
- ✅ Secrets via environment variables (follow all frameworks)
- ✅ State vs configuration separation (follow LangGraph)

### Implementation Priority

1. **Phase 1 (2 weeks)**: Pydantic schemas + function registry + `to_dict`/`from_dict`
2. **Phase 2 (1 week)**: Deprecation warnings + migration tool
3. **Phase 3 (6+ months)**: Remove pickle entirely

---

## Conclusion

**Industry Consensus**: YAML/JSON + Pydantic + Function Registry

**Security Mandate**: No pickle for configuration

**Developer Experience**: Human-readable, editable by non-technical users

**Portability**: Cross-Python-version, cross-machine compatibility

Flock should follow these established patterns to ensure security, maintainability, and ecosystem compatibility.

---

**References**:
- AutoGen: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/serialize-components.html
- LangChain: https://python.langchain.com/docs/how_to/serialization/
- LangGraph: https://langchain-ai.github.io/langgraph/concepts/persistence/
- CrewAI: https://docs.crewai.com/en/concepts/agents
- Semantic Kernel: https://learn.microsoft.com/en-us/semantic-kernel/concepts/plugins/
- Haystack: https://docs.haystack.deepset.ai/docs/serialization
- CVE-2025-1716: https://advisories.gitlab.com/pkg/pypi/picklescan/CVE-2025-1716/
