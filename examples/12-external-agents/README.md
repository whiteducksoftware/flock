# External Agents

Examples demonstrating the meta-orchestrator feature — orchestrating external CLI-based AI agents (Claude Code, Codex) as blackboard participants.

## Prerequisites

| Example | Claude Code | Codex | ANTHROPIC_API_KEY | OPENAI_API_KEY |
|---------|:-----------:|:-----:|:-----------------:|:--------------:|
| 01 | Required | - | Required | - |
| 02 | Required | Required | Required | Required |

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
PRDiff --> ChangelogEvent --+                                                         +--> review-merger --> ReviewSummary
                            +--> performance-reviewer (Codex) ----> PerformanceReview -+
```

External agents are spawned as subprocesses, authenticate back via bearer tokens, and publish results through the standard REST API. The blackboard treats their artifacts identically to internal agent output.
