# Flock v0.3 - Hummingbird  

![Flock Banner](../assets/images/hummingbird.png){ width="200" }

We're excited to announce Flock v0.3, codenamed **"Hummingbird"**! This release brings a fundamental redesign of Flock's core architecture, introducing **unprecedented modularity and flexibility** to AI agent development.  

Modules and evaluators were the last missing pieces to fully modularize Flock.  

Worried this might lead to hard-to-manage boilerplate? No problem! **FlockFactory** provides pre-configured agents, making interaction with modules and evaluators **purely optional**, so you can focus on **what** the agent does, not **how** it works.  

But if you want **total control** over your agent, feel free to dive into these new additions. They unlock **crazy new possibilities** in Flock!  

Like a hummingbird, modules are small and nimble code packages. Put enough of them inside a flock, and... well, even we don't know what happens next.  

### Other notable additions:  
- **CLI Interface** – Flock now has a command-line interface  
- **REST API Server** – Expose your agents via HTTP endpoints
- **Color-coded logging** – Better debugging experience  
- **New examples**  
- ...and much more!  

---

## 🚀 Core Changes   

### 🎯 New Module System   
- **Pluggable modules system á la FastAPI**   
- **Easy-to-implement** module interface  
- **Configuration system** for clean parameter management  

### 🔄 New Evaluator System  
- **Pluggable evaluation system**  
- Built-in support for multiple evaluation strategies:  
  - **Declarative Evaluator** – The default way Flock is designed  
  - **Natural Language Evaluator** – Use "classic" prompting  
  - **Zep Evaluator** – Add or query data
- **Easily extendable** with custom evaluation approaches  

### 🔀 New Router System
- **Pluggable router system** for dynamic agent chaining
- Built-in support for multiple routing strategies:
  - **Default Router** – Uses the agent's hand_off property
  - **LLM Router** – Uses an LLM to determine the next agent
  - **Agent Router** – Uses a dedicated agent to make routing decisions
- **Easily extendable** with custom routing approaches

### 🌐 REST API Server
- **FastAPI-based** HTTP server for exposing agents
- **Synchronous and asynchronous** execution modes
- **Run status tracking** with unique run IDs
- **Agent discovery** endpoint to list available agents
- **Simple integration** with existing Flock instances

### 🔄 Auto-Handoff Feature
- **Dynamic agent chaining** without explicit handoff definitions
- **LLM-powered routing** to determine the best next agent
- **Emergent behavior** in multi-agent systems
- **Simple to use** with the "auto_handoff" string value

### 📚 New high end examples like the Repository Analyzer
- **Automatic documentation generation** for any codebase
- **Rule-based version** using custom evaluators
- **LLM-based version** for more flexible and powerful analysis
- **Comprehensive documentation** including overview, architecture, components, and more

### 🏭 FlockFactory    
- Provides **pre-configured agents**, so you don't have to manage modules and evaluators manually!  

### 📦 Built-in Modules  
- **Memory Module** – Persistent agent memory  
- **Output Module** – Advanced output formatting and storage  
- **Metrics Module** – Detailed performance tracking  
- **Zep Module** – Uses Zep for Knowledge Graphs
- **Azure Search Tools** – Integration with Azure AI Search for vector search and document retrieval

---

## ⚠️ Breaking Changes  
- **Removed callback handlers** from `FlockAgent` in favor of modules  
- **Changed agent initialization** pattern to support evaluators  
- **Simplified module lifecycle hooks** (removed redundant pre/post hooks)  

---

## ✨ Small Changes & Fixes 

### 🎨 Theme Designer

### 🌈 Color Coded Logging

---

## 📜 Code Rundown  

### Old way:  
```python
agent = FlockAgent(
    name="bloggy",
    input="blog_idea",
    output="funny_blog_title, blog_headers",
)
flock.add_agent(bloggy)
```  

### New way:  
```python
bloggy = FlockFactory.create_default_agent(
    name="bloggy",
    input="blog_idea",
    output="funny_blog_title, blog_headers",
)
flock.add_agent(bloggy)
```  

See? **Basically nothing changed!** Just more modular and flexible.  

---

## 🔮 What's Next?  

### Coming in v0.3 updates:  
- **More modules** (built-in RAG coming soon!)  
- **More evaluators**  
- **CLI management tool improvements**  
- **Finishing documentation**

### Looking ahead to v0.4 – *Magpie*:  
- **Flock WebUI** – Real-time monitoring, no-code agent creation & management  
- **Seamless deployment** – Kubernetes, Docker, and enterprise-ready solutions  

---

## 🛠 Installation  

```bash
pip install flock-core>=0.3.0
```  

---  

📖 **Full documentation**: [https://whiteducksoftware.github.io/flock](https://whiteducksoftware.github.io/flock)  
💻 **GitHub**: [https://github.com/whiteducksoftware/flock](https://github.com/whiteducksoftware/flock)
