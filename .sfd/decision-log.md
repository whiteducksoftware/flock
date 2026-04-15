## SFD Decision Log

### Surface Type
API / Library (Python framework — developer-facing)

### Convergence Status
Converged on 2026-04-15 — Contracts approved on 2026-04-15

### Decisions
- [2026-04-15] Use existing `.agent()` builder with `.kind("external").adapter("claude_code")` — Rejected: dedicated `.external_agent()` method with `.command()` (too many knobs, user shouldn't know CLI flags). Rejected: separate config object like OpenClaw (too much infrastructure for v1).
- [2026-04-15] Adapter handles ALL serialization/deserialization internally — User doesn't control `--print`, `--output-format`, process spawning, or output parsing. The adapter is the expert on how to talk to each external agent.
- [2026-04-15] V1 ships with hardcoded adapters for `claude_code` and `codex` — No generic "any CLI tool" support yet. Keep it focused.
- [2026-04-15] No configuration knobs in v1 (timeout, cwd, env, concurrency) — Start minimal. Add config surface only when users hit real walls.
- [2026-04-15] Mixed pipelines (external + native agents) must work seamlessly — The blackboard doesn't care where compute comes from. This is the main value prop.
- [2026-04-15] `.kind("external").adapter("x")` resolves to an EngineComponent from adapter registry — Same mechanism as `.with_engines()`, just a cleaner surface. `.adapter()` implies `.kind("external")` so `.kind()` is optional.
- [2026-04-15] ExternalEngineComponent base class with `build_command()` and `parse_output()` overrides — Each adapter only specifies how to invoke the CLI and parse its output. Shared subprocess management in base.
- [2026-04-15] External agents cannot use `.with_mcps()` or `.with_tools()` — The external agent owns its own tool surface. Flock doesn't inject tools into subprocess agents.

### Converged Surface
```python
# Minimal: two new builder methods
flock.agent("code-answerer")
    .kind("external")
    .adapter("claude_code")
    .consumes(CodingQuestion)
    .publishes(CodingAnswer)

# Mixed pipeline: external + native in same workflow
flock.agent("implementer").kind("external").adapter("claude_code").consumes(Spec).publishes(Code)
flock.agent("test-writer").kind("external").adapter("codex").consumes(Code).publishes(Tests)
flock.agent("reviewer").consumes(Code, Tests).publishes(Review)  # native LLM
```

### Derived Contracts

#### Adapter Registry
```python
EXTERNAL_ADAPTERS: dict[str, type[EngineComponent]] = {
    "claude_code": ClaudeCodeAdapter,
    "codex": CodexAdapter,
}
```

#### ExternalEngineComponent (base class)
```python
class ExternalEngineComponent(EngineComponent):
    async def evaluate(agent, ctx, inputs, output_group) -> EvalResult
    def build_prompt(inputs, output_group) -> str        # shared
    def build_command(prompt) -> list[str]                # adapter overrides
    async def run_process(cmd) -> str                     # shared
    def parse_output(raw, output_group) -> list[BaseModel] # adapter overrides
```

#### AgentBuilder additions
```python
def kind(self, kind: str) -> AgentBuilder       # sets self._kind
def adapter(self, name: str) -> AgentBuilder     # resolves from registry, sets engine
```

#### Domain Rules
- `.kind("external")` without `.adapter()` → ValueError at build time
- `.adapter("unknown")` → ValueError at build time
- `.adapter("x")` implies `.kind("external")` — kind() is optional
- External agents cannot use `.with_mcps()` or `.with_tools()`
- External agents CAN use all blackboard features (subscriptions, fan-out, batching, conditions)
- Prompt includes full Pydantic schema of output type

#### Non-Functional
- Subprocess timeout: 120s default (hardcoded v1)
- One concurrent instance per agent (v1)
- Stderr captured for error reporting
- Process failure → standard Flock error handling

### Acceptance Criteria
- [ ] `.agent("x").kind("external").adapter("claude_code").consumes(A).publishes(B)` builds without error
- [ ] Publishing A triggers the external agent
- [ ] Claude Code receives prompt containing A's data + B's schema
- [ ] JSON output parsed into B and published to blackboard
- [ ] Mixed pipeline (external + native) resolves dependencies correctly
- [ ] `.adapter("unknown")` raises ValueError at build time
- [ ] `.kind("external")` without `.adapter()` raises ValueError at build time
- [ ] Subprocess timeout produces agent error artifact
- [ ] Invalid JSON output triggers retry or error (not silent failure)

### Gate Status
- [x] Gate 1: Surface Converged (2026-04-15)
- [x] Gate 2: Contracts Approved (2026-04-15)
- [ ] Gate 3: Architecture Review
- [ ] Gate 4: Hardening Complete
- [ ] Gate 5: Release Ready

### Hardening Status
- [ ] Persistence (currently: mock data)
- [ ] Auth (currently: placeholder)
- [ ] Domain logic (currently: simulated)
- [ ] Error handling (currently: happy-path)
- [ ] Performance (currently: unoptimized)
