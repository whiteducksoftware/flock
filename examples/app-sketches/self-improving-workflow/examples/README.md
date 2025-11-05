# Self-Improving Workflow Examples

Working examples demonstrating Self-Improving Workflow patterns.

## Examples

### 01_basic_workflow.py

**Basic 3-phase workflow** demonstrating:
- Phase-aware agents
- Work discovery
- Basic cascade (Analysis → Implementation → Validation)

**Run:**
```bash
uv run python examples/10-full-projects/self-improving-workflow/examples/01_basic_workflow.py
```

### Coming Soon

- `02_phase_instructions.py` - Workflow with phase context injection
- `03_cross_phase_discovery.py` - Advanced cross-phase branching
- `04_orchestration.py` - Workflow with monitoring and orchestration
- `05_custom_phases.py` - Extending with custom phase types

## Usage

Each example is self-contained and can be run independently. They demonstrate progressive complexity:

1. **Basic** - Simple 3-phase workflow
2. **Intermediate** - Phase instructions and context
3. **Advanced** - Cross-phase discovery and branching
4. **Production** - Monitoring, orchestration, error handling

## Prerequisites

- Flock installed (`poe install`)
- OpenAI API key set (`export OPENAI_API_KEY=sk-...`)
- Python 3.12+

## Learning Path

1. Start with `01_basic_workflow.py` to understand core concepts
2. Review [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for architecture
3. Check [CODE_SNIPPETS.md](../CODE_SNIPPETS.md) for patterns
4. Build your own workflows!



