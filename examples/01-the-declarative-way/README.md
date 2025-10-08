# 🍕 The Declarative Way: Zero Prompts, All Type Safety

> **"Why write 500-line prompts when Pydantic can speak louder?"**

Welcome to the heart of Flock's philosophy: **declarative programming**. Forget prompt engineering. Forget hoping the LLM understands your intent. Just declare the contract, and let the types do the talking.

## 🎯 What You'll Learn

This trilogy of examples teaches you the core superpower of Flock:

**🍕 Example 01: Pizza Master** (5 min)
- The "Aha!" moment: Schemas ARE instructions
- Why declarative beats imperative for AI agents
- Your first type-safe agent in ~20 lines

**🎬 Example 02: Movie Studio** (10 min)
- Complex nested types (Characters with backstories!)
- Field constraints (runtime > 200 minutes? Check!)
- Literal types for controlled outputs
- How to guide LLMs with type hints, not prompts

**🔎 Example 03: Web Researcher** (15 min)
- MCP (Model Context Protocol) integration
- Custom Python tools with `@flock_tool`
- Agents that interact with the real world
- Zero prompt engineering, maximum capability

**Total time: ~30 minutes** | **Difficulty: ⭐ Beginner-friendly**

---

## 🤔 What Even IS "Declarative"?

### The Old Way (Imperative/Prompt Engineering):
```python
prompt = """You are a pizza chef. When given a pizza idea, you should:
1. List ingredients (be creative!)
2. Choose a size (small, medium, large)
3. Pick a crust type (thin, thick, stuffed)
4. Write step-by-step instructions
5. Format as JSON with keys: ingredients, size, crust_type, instructions
6. Make sure ingredients is an array
7. Actually, can you also...
[490 more lines of instructions that GPT-4 ignores]"""
```

### The Flock Way (Declarative):
```python
@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]

pizza_master = flock.agent("pizza_master").consumes(PizzaIdea).publishes(Pizza)
```

**That's it.** The schema IS the instruction. No 500-line prompt. No hoping. Just contracts.

---

## 🚀 Quick Start

```bash
# From the flock repository root:
cd examples/01-the-declarative-way

# Run them in order!
uv run python 01_declarative_pizza.py
uv run python 02_input_and_output.py
uv run python 03_mcp_and_tools.py
```

---

## 📚 Detailed Breakdown

### 01_declarative_pizza.py
**The core concept:** You don't tell the agent HOW to make a pizza. You tell it WHAT a pizza looks like. The LLM figures out the rest.

**Key learning:**
- `@flock_type` registers Pydantic models
- `.consumes()` + `.publishes()` creates the contract
- No prompts needed (the schema is self-documenting)
- Runtime validation catches errors

**Why this matters:** Survives GPT-4 → GPT-5 upgrades. Schemas don't break when models change.

---

### 02_input_and_output.py
**Level up:** Real applications need complex data structures. Nested objects, validation rules, controlled vocabularies.

**Key learning:**
- Nested types (`Movie` contains `list[Character]`)
- Field constraints (`runtime: int = Field(ge=200, le=240)`)
- Literal types for enums (`genre: Literal["action", "sci-fi", ...]`)
- Descriptions guide the LLM (but aren't fragile prompts)

**Why this matters:** You can express business logic in types. "Runtime must be 200-240 minutes" becomes a validation rule, not a prompt hope.

---

### 03_mcp_and_tools.py
**Real power:** Agents need to DO things. Search the web. Write files. Call APIs.

**Key learning:**
- `@flock_tool` decorator for Python functions
- MCP integration for external capabilities (web search, file ops)
- Agents can combine tools (search web + read pages + write report)
- Docstrings become tool descriptions

**Why this matters:** Now your agents can interact with the real world, not just transform text.

---

## 🎓 The Philosophy

### What Flock Believes:
1. **Types > Prompts** - Schemas survive model upgrades. Prompts don't.
2. **Validation > Hope** - Runtime errors are better than production bugs.
3. **Contracts > Control Flow** - Declare WHAT, not HOW.

### What This Means for You:
- ✅ Testable agents (mock the input type, assert on output type)
- ✅ Self-documenting code (the schema tells you everything)
- ✅ Future-proof (GPT-6 will still understand Pydantic)
- ✅ Less debugging (Pydantic catches errors before LLM runs)

---

## 🔬 Try This After You Finish

**Challenge 1:** Modify `01_declarative_pizza.py`
- Add a `toppings_count: int = Field(ge=3, le=10)` constraint
- See how the LLM respects it without prompt changes

**Challenge 2:** Extend `02_input_and_output.py`
- Add a `Director` nested type
- Require at least 1 director with IMDB rating > 7.0

**Challenge 3:** Build your own MCP agent
- Create a "Weather Reporter" that searches current weather
- Write markdown reports with `@flock_tool`
- Use type constraints for temperature ranges

---

## 🤝 Next Steps

Once you've mastered declarative basics, move on to:

**→ [05-claudes-workshop/](../05-claudes-workshop/)** ✅ - 7 progressive lessons from beginner to advanced

**Also coming soon:**
- [02-the-blackboard/](../02-the-blackboard/) 🚧 - Multi-agent collaboration patterns
- [03-the-dashboard/](../03-the-dashboard/) 🚧 - Real-time visualization
- [04-the-api/](../04-the-api/) 🚧 - API integration examples

---

## 💡 The "Aha!" Moment

**Most frameworks:** Write a prompt. Hope the LLM follows it. Debug when it doesn't.

**Flock:** Define a schema. LLM MUST follow it (Pydantic validates). No hoping required.

**That's the declarative way.**

---

**Questions?** The inline code comments are extensive. Read them! Or check the main [README](../../../README.md) for more context.

---

*Built with ❤️ using Flock Flow 0.5*
