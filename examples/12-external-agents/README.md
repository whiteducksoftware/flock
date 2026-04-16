# External Agents

Examples demonstrating the meta-orchestrator feature — orchestrating external CLI-based AI agents (Claude Code, Codex) as blackboard participants via the engine pattern.

## Prerequisites

| Example | Claude Code | Codex | ANTHROPIC_API_KEY | OPENAI_API_KEY |
|---------|:-----------:|:-----:|:-----------------:|:--------------:|
| 01      | Required    | -     | Optional¹         | -              |
| 02      | Required    | Required | Optional¹      | Optional¹      |

¹ Both CLIs use your logged-in subscription by default — no API keys required.

Install the CLIs:

```bash
npm install -g @anthropic-ai/claude-code
npm install -g @openai/codex
```

## Examples

### 01 — Claude Code Query-Answer

Simple query-answer pattern: publish a coding question, Claude Code answers it as an external subprocess, an internal agent summarizes the result.

```bash
uv run python examples/12-external-agents/01_claude_code_query.py
```

### 02 — Multi-Agent Code Review

Two external agents review the same PR diff in parallel — Claude Code checks security/correctness, Codex checks performance/style. An internal agent merges their findings into a unified review summary.

```bash
uv run python examples/12-external-agents/02_multi_agent_code_review.py
```

## Architecture

```
                            +--> security-reviewer (Claude Code) --> SecurityReview --+
PRDiff --+----------------+ +                                                         +--> review-merger --> ReviewSummary
                            +--> performance-reviewer (Codex) ----> PerformanceReview -+
```

External agents are declared with `.kind("external").adapter("...")` and Flock auto-attaches an `ExternalEngineComponent` that wraps the matching CLI runtime. From the orchestrator's perspective they are just engine-driven agents — `evaluate()` spawns the subprocess, parses the JSON response, and returns typed Pydantic artifacts that flow through the blackboard exactly like any other agent's output.

No separate scheduler, no REST return path, no auth tokens for spawn — the engine pipeline handles everything in-process.
