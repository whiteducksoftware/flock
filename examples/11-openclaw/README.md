# OpenClaw Integration Examples

These examples demonstrate how to use [OpenClaw](https://github.com/openclaw/openclaw) agents as Flock pipeline participants. Instead of calling an LLM directly, agents delegate to an OpenClaw gateway — giving them access to tools, skills, web search, file systems, and multi-step reasoning.

## Prerequisites

- A running OpenClaw gateway (e.g., `openclaw gateway start`)
- Gateway URL and auth token

## Setup

```bash
# Configure gateway(s) via environment variables
export OPENCLAW_CODIE_URL=http://localhost:19789
export OPENCLAW_CODIE_TOKEN=your-token

# For multi-gateway examples
export OPENCLAW_CLAUDE_URL=http://localhost:18789
export OPENCLAW_CLAUDE_TOKEN=your-token
```

## Examples

| # | Example | What It Shows |
|---|---------|---------------|
| 01 | [Pizza with OpenClaw](01_pizza_with_openclaw.py) | Simplest integration — one OpenClaw agent, one artifact |
| 02 | [Mixed Pipeline](02_mixed_pipeline.py) | OpenClaw + native LLM agents in the same workflow |
| 03 | [Env Config](03_env_config.py) | Auto-discovery from environment + multi-gateway setup |

## Key Concepts

**One-line swap:** Replace `flock.agent("name")` with `flock.openclaw_agent("alias")` — everything else stays the same.

```python
# Before: Direct LLM
pizza_master = flock.agent("pizza_master").consumes(Idea).publishes(Pizza)

# After: OpenClaw agent
pizza_master = flock.openclaw_agent("codie").consumes(Idea).publishes(Pizza)
```

**All Flock features work unchanged:** blackboard routing, visibility, fan-out, conditions, tracing, dashboard — OpenClaw is just a different engine.

**Two config styles:**
```python
# Explicit
flock = Flock(openclaw=OpenClawConfig(gateways={"codie": GatewayConfig(url=..., token_env=...)}))

# Environment-based (recommended for production)
flock = Flock(openclaw=OpenClawConfig.from_env())
```
