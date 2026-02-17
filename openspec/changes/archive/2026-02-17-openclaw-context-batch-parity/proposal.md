## Why

After shipping transport, fan-out, and streaming parity work, OpenClaw integration still has a set of **wiring-level parity gaps** against native DSPy behavior. The highest-priority gap is context history: OpenClaw calls are currently mostly stateless per activation and do not consume `ctx.artifacts` as conversation/runtime context the same way native DSPy flows can.

Pyro clarified architecture direction: OpenClaw tool capability is server-side and already available through OpenClaw itself, so **ReAct/tool-definition forwarding is explicitly a non-goal** for this change.

## What Changes

This change introduces context-first parity improvements for OpenClaw engine behavior:

1. Add context-history serialization into OpenClaw request payloads (priority 1).
2. Add explicit batch-mode parity handling (`ctx.is_batch`) and coverage.
3. Wire output group description (`publishes(..., description=...)`) into OpenClaw task prompt.
4. Resolve config/API parity knobs:
   - add OpenClaw engine `instructions` override similar to DSPy,
   - decide and implement/cleanup `response_mode` behavior (remove dead knob or make it effective),
   - evaluate optional pass-through for generation params (`temperature`, `max_tokens`) if gateway contract supports it safely.
5. Add integration + unit tests and documentation updates.

## Explicit Non-Goals

- Passing Flock tool definitions to OpenClaw (`agent.tools`) or implementing DSPy-style client-side ReAct loop.
- Replacing OpenClaw's native tool architecture.
- New streaming work (already tracked in `openclaw-streaming-parity`).

## Scope

### In Scope
- `OpenClawEngine` request shaping and prompt composition.
- Context + batch semantics in OpenClaw payload contracts.
- Output-group description and instructions override behavior.
- Cleanup/implementation decision for `response_mode`.
- Tests and guide updates.

### Out of Scope
- New gateway endpoints or transport redesign.
- Multi-output envelope support (already handled separately as fail-fast).
- Tool forwarding/ReAct parity as an implementation goal.

## Impact

### Affected files (planned)
- `src/flock/integrations/openclaw/engine.py`
- `src/flock/integrations/openclaw/config.py`
- `src/flock/core/orchestrator.py` (if constructor/builder args change)
- `tests/test_openclaw_engine.py`
- `tests/integration/openclaw/test_openclaw_pipeline.py`
- `docs/guides/openclaw.md`

### Risks
- Prompt bloat from context serialization can reduce determinism if uncontrolled.
- Batch-mode behavior may expose assumptions in existing OpenClaw prompt contract.

### Mitigation
- Keep context bounded and deterministic (clear schema + explicit formatting).
- Add focused tests for context-on/off and batch-on/off paths before implementation.
