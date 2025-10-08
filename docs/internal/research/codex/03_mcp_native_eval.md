# MCP‑Native Agent Evaluation

Score: 9.1 / 10

## Abstract
The Model Context Protocol (MCP) standardizes tool access across providers. Flock integrates MCP at the orchestrator/agent level. We hypothesize that MCP‑native tool use reduces tool‑call errors and improves task success versus ad‑hoc bindings. We propose an evaluation harness using public MCP servers (filesystem, HTTP, GitHub) and agent tasks across retrieval, repo operations, and web I/O.

## Research Questions / Hypotheses
- H1: MCP tools reduce tool‑call error rates (schema mismatches, missing params) versus ad‑hoc tools.
- H2: MCP discovery + allowlists improve safety and reliability with minimal latency overhead.
- H3: Standardized tool telemetry improves debuggability and recovery from tool failure.

## Experiment Sketch
- Build comparable agents with and without MCP; run tasks requiring file I/O, HTTP fetch, and repo queries.
- Log tool errors, retries, latency, success.
- Add allowlist/denylist policies; measure effect on misuse and safety violations.

## Project Plan (3–5 weeks)
- Week 1: Assemble MCP testbed; align schemas.
- Week 2: Implement harness and tasks; run baselines.
- Week 3: Analyze failures and recovery; ablations on discovery/whitelists.

## Metrics
- Tool‑call error rate, success, retries, tool latency distribution, cost.

## Value Proposition
- A practical demonstration that standardizing tool interfaces via MCP yields measurable reliability and safety wins.

## Sources / Further Reading
- MCP overview (Anthropic) and multi‑vendor adoption. https://www.anthropic.com/news/model-context-protocol
- MCP docs (OpenAI Agents SDK). https://openai.github.io/openai-agents-python/mcp/
- The Verge coverage of MCP as an industry standard. https://www.theverge.com/2025/2/13/24239218/model-context-protocol-mcp-standard-ai-assistants
