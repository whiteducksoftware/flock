# Examples Quick Reference Guide

**Last Updated:** 2025-10-08

## Quick Navigation

### For First-Time Users
**Start Here:** `/examples/01-the-declarative-way/01_declarative_pizza.py` (5 minutes)
**Then:** Work through `01-the-declarative-way/` in order (30 minutes total)
**Next:** Jump to `05-claudes-workshop/` lessons 01-02

### For Specific Features

| I Want To Learn... | Go To Example |
|-------------------|---------------|
| Basic single agent | `01-the-declarative-way/01_declarative_pizza.py` |
| Complex nested types | `01-the-declarative-way/02_input_and_output.py` |
| Tools & MCP integration | `01-the-declarative-way/03_mcp_and_tools.py` |
| Agent chaining | `05-claudes-workshop/lesson_02_band_formation.py` |
| Conditional consumption | `03-the-dashboard/02-dashboard-edge-cases.py` |
| Feedback loops | `05-claudes-workshop/lesson_04_debate_club.py` |
| Distributed tracing | `05-claudes-workshop/lesson_05_tracing_detective.py` |
| Visibility & security | `05-claudes-workshop/lesson_06_secret_agents.py` |
| Parallel processing | `05-claudes-workshop/lesson_07_news_agency.py` |
| Dashboard visualization | `03-the-dashboard/02-dashboard-edge-cases.py` |

### For Production Patterns

| Pattern | Example | Use Case |
|---------|---------|----------|
| Single Transform | 01-01, 05-01 | Data enrichment, validation |
| Sequential Pipeline | 05-02 | Multi-step workflows |
| Parallel-Then-Join | README quick start | Multiple analysis perspectives |
| Conditional Routing | 03-02, 05-03 | Quality gates, smart filtering |
| Feedback Loops | 05-04 | Iterative refinement |
| Fan-Out | 05-07 | Broadcast to multiple processors |
| Security-Aware | 05-06 | Multi-tenant, RBAC systems |

---

## Example Inventory by Status

### ✅ Complete & Ready to Use
- `01-the-declarative-way/` - 3 examples, comprehensive README
- `05-claudes-workshop/` - 7 lessons, progressive difficulty
- `06-readme/` - 1 simplified example for quick reference
- `07-notebooks/` - 1 Jupyter notebook (proof of concept)

### 🚧 Partial or Placeholder
- `02-the-blackboard/` - README only, examples planned
- `03-the-dashboard/` - 3 examples exist, README is placeholder
- `04-the-api/` - README only, examples planned

---

## Feature Coverage Quick Lookup

### Core Features (100% Coverage)
- `@flock_type` decorator
- `.consumes(Type)`
- `.publishes(Type)`
- `flock.publish()` / `flock.run_until_idle()`

### Well-Covered (50%+ Coverage)
- `.description(text)` - most examples
- Conditional consumption `where=` - 03-02, 05-03, 05-04
- Store operations `get_by_type()` - multiple examples

### Limited Coverage (10-30%)
- `.with_tools()` / `.with_mcps()` - 01-03, 05-03
- Visibility controls - 05-06 only
- Dashboard features - 03-02 only
- `prevent_self_trigger()` - 05-04 (implied)

### Not Demonstrated (0% Coverage)
- Batch processing (`batch=` parameter)
- Join operations (`join=` parameter)
- Text predicates
- Multi-tenancy (`.tenant()`)
- Performance tuning (`.best_of()`, `.max_concurrency()`)
- Custom utilities/engines

---

## Code Patterns Cheat Sheet

### Basic Agent Setup
```python
from flock import Flock, flock_type
from pydantic import BaseModel

@flock_type
class Input(BaseModel):
    data: str

@flock_type
class Output(BaseModel):
    result: str

flock = Flock("openai/gpt-4.1")
agent = flock.agent("name").consumes(Input).publishes(Output)

await flock.publish(Input(data="test"))
await flock.run_until_idle()
```

### Conditional Consumption
```python
# Example: 03-the-dashboard/02-dashboard-edge-cases.py
agent = (
    flock.agent("quality_gate")
    .consumes(Review, where=lambda r: r.score >= 9)
    .publishes(Approved)
)
```

### Tools & MCP
```python
# Example: 01-the-declarative-way/03_mcp_and_tools.py
from flock.registry import flock_tool

@flock_tool
def my_tool(param: str) -> str:
    """Docstring becomes tool description for LLM."""
    return f"Result: {param}"

agent = (
    flock.agent("worker")
    .with_tools([my_tool])
    .with_mcps(["server_name"])
    .consumes(Task)
    .publishes(Result)
)
```

### Visibility Controls
```python
# Example: 05-claudes-workshop/lesson_06_secret_agents.py
from flock.visibility import PrivateVisibility, LabelledVisibility

field_agent = (
    flock.agent("field_agent")
    .consumes(Mission)
    .publishes(
        RawIntelligence,
        visibility=PrivateVisibility(agents={"analyst"})
    )
)

analyst = (
    flock.agent("analyst")
    .identity(AgentIdentity(name="analyst", labels={"clearance:secret"}))
    .consumes(RawIntelligence)
    .publishes(
        Report,
        visibility=LabelledVisibility(required_labels={"clearance:secret"})
    )
)
```

---

## Time Estimates

### Quick Start (Minimal)
- **5 min:** Read README core concepts
- **5 min:** Run `01-the-declarative-way/01_declarative_pizza.py`
- **10 min:** Modify pizza example to add constraints
- **Total:** 20 minutes to "hello world"

### Getting Started (Foundation)
- **30 min:** Complete `01-the-declarative-way/` (all 3 examples)
- **25 min:** Lessons 01-02 from `05-claudes-workshop/`
- **Total:** 55 minutes to understand basics + chaining

### Intermediate Mastery
- **40 min:** Lessons 03-04 (tools + feedback loops)
- **20 min:** Lesson 05 (tracing)
- **Total:** ~2 hours to production patterns

### Advanced Topics
- **25 min:** Lesson 06 (security)
- **20 min:** Lesson 07 (scale)
- **Total:** ~2.75 hours to complete workshop

---

## Common Questions → Examples

**Q: How do I make my first agent?**
A: `01-the-declarative-way/01_declarative_pizza.py`

**Q: How do agents communicate?**
A: `05-claudes-workshop/lesson_02_band_formation.py` (blackboard pattern)

**Q: How do I add web browsing?**
A: `01-the-declarative-way/03_mcp_and_tools.py` or `05-claudes-workshop/lesson_03_web_detective.py`

**Q: How do I filter which artifacts an agent processes?**
A: `03-the-dashboard/02-dashboard-edge-cases.py` (where= predicate)

**Q: How do I prevent infinite loops?**
A: `05-claudes-workshop/lesson_04_debate_club.py` (prevent_self_trigger)

**Q: How do I debug my agents?**
A: `05-claudes-workshop/lesson_05_tracing_detective.py` (DuckDB traces)

**Q: How do I secure multi-tenant systems?**
A: `05-claudes-workshop/lesson_06_secret_agents.py` (5 visibility types)

**Q: How many agents can I run in parallel?**
A: `05-claudes-workshop/lesson_07_news_agency.py` (8 concurrent agents)

---

## Next Steps After Examples

After completing the examples:

1. **Read the main README** - Architecture comparison, feature list
2. **Check AGENTS.md** - Development patterns, contribution guide
3. **Explore the codebase** - Source code in `src/flock/`
4. **Build something real** - Apply patterns to your use case
5. **Join the community** - Share your examples, ask questions

---

## Example File Naming Convention

Pattern observed in examples:
- `01_descriptive_name.py` - Numbered, snake_case
- `README.md` - One per category
- Examples are runnable: `uv run examples/path/to/file.py`

---

## Documentation Status Legend

- ✅ **Complete:** Code + comprehensive documentation
- 🚧 **Partial:** Code exists but docs are placeholder/incomplete
- ❌ **Missing:** Neither code nor docs exist
- ⚠️ **Outdated:** Exists but may need updates

---

**For Full Analysis:** See `examples-analysis.md` (18,000+ words)
**For Source Code:** Browse `/examples/` directory
**For Questions:** Check inline comments in example files (40-50% of lines are educational comments)
