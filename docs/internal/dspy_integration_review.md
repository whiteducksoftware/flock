# DSPy Integration Review — Options to Simplify Flock’s Declarative Evaluator

This review summarizes how Flock uses DSPy today, the pain points we see in practice, and concrete options to replace (or wrap) the parts we rely on with a lean, native implementation. It closes with alternative libraries worth considering and a recommended path forward.

## Summary

- Flock’s `DeclarativeEvaluationComponent` uses DSPy primarily for:
  - A language model wrapper (`dspy.LM`) over LiteLLM
  - Prompt assembly via `dspy.Signature` and its adapters
  - Program selection: `Predict` (default), `ReAct` (with tools), or `ChainOfThought`
  - Optional streaming via `dspy.streamify`

- The integration works but adds complexity:
  - Hidden global state (`dspy.settings`), coupling prompt/LM setup tightly to DSPy
  - ReAct loop shape and tool integration is “DSPy-first” (wrapping everything as `dspy.Tool`)
  - Template/adapter logic isn’t under our control and can be harder to trace/debug
  - The pieces Flock actually needs are small compared to the full DSPy surface

- Conclusion: It’s viable to replace the DSPy dependency in the evaluator with a focused, native layer built directly atop LiteLLM (which we already depend on via DSPy) and Flock’s own contracts/registries. We can do this incrementally behind a feature gate.

---

## How Flock Uses DSPy Today

Key callsites and responsibilities:

- `src/flock/components/evaluation/declarative_evaluation_component.py`
  - Creates an LM context via `dspy.LM(model=..., temperature=..., max_tokens=..., cache=...)`
  - Builds a dynamic `dspy.Signature` from Flock’s contracts using `DSPyIntegrationMixin.create_dspy_signature_class(...)`
  - Chooses a program (`Predict`, `ReAct`, or `ChainOfThought`) via `_select_task(...)`
  - With `stream=True`, wraps the program via `dspy.streamify(...)` and yields chunks
  - Converts a `dspy.Prediction` to a python dict; computes cost from `lm.history`

- `src/flock/core/mixin/dspy_integration.py`
  - Signature building from Flock’s string/Pydantic contracts to `InputField`/`OutputField`
  - LM configuration helper, program selection, result post-processing

- MCP/Tools glue
  - We wrap tools as `dspy.Tool` where needed so `dspy.ReAct` can call them

What we don’t leverage from DSPy (or only tangentially):
- Optimizers, training/telemetry subsystems, adapters beyond basic chat assembly, advanced demos/few-shot management, meta-programming features

---

## Pain Points with DSPy Integration

- Global mutable state and magic:
  - `dspy.settings` stores the active LM, adapter, streaming callbacks, etc.
  - Side-effects make reasoning about behavior harder across tests/runs.

- ReAct dependency:
  - We’re effectively forced into a particular ReAct shape. The code path is opinionated and the adapter chain adds indirection.
  - Wrapping Flock/MCP tools as `dspy.Tool` is extra glue that leaks DSPy types through our API.

- Prompt + signature ownership:
  - We build a DSPy Signature dynamically, but the final adapter/prompt assembly is inside DSPy, making debuggability and customization indirect.

- Streaming and costs:
  - `dspy.streamify` is convenient but again relies on `dspy.settings` and `StreamListener` wiring we don’t control.

---

## What Flock Actually Needs (Minimal Set)

1. LM client over LiteLLM
   - Chat/text/responses mode; retries; provider quirks (e.g., OpenAI reasoning models); optional cache hook.
   - Streaming events.

2. Prompt assembly from contracts
   - Flock already parses string/Pydantic signatures. We can form a stable system + user message template directly (e.g., “Given input fields…, produce outputs… as JSON matching schema …”).

3. A simple predictor
   - One-shot “predict” that calls LM and returns structured outputs. Prefer JSON schema outputs when provider supports it (OpenAI `response_format`), fallback to robust JSON-only prompting + correction loop.

4. A lean ReAct loop (optional)
   - Iterate: next_thought, next_tool_name, next_tool_args; call tool; append observation; stop on finish or max_iters.
   - We can implement this in ~150–200 LOC with clear hooks and without wrapping tools into `dspy.Tool`.

5. Streaming wrapper
   - Directly aggregate LiteLLM streaming chunks into user events. Provide typed events (e.g., `AgentStreamChunk(field="...", text="...")`).

---

## Viability of a Native Implementation

Short answer: high.

Rough design (new package, no external dependency beyond LiteLLM):

- `flock.core.eval.lm_client`:
  - Adapter around LiteLLM with: retries, cache hooks, provider-specific quirks, streaming yield handling, cost gathering.

- `flock.core.eval.signature`:
  - Converts Flock’s string/Pydantic contracts into:
    - A JSON schema for outputs (when supported) and
    - A canonical instruction string for non-schema providers.

- `flock.core.eval.predictor`:
  - `predict_async(inputs, schema, instruction, options)` → dict
  - Enforces JSON shape (schema-based when possible), with a short correction loop on malformed JSON.
  - Streaming variant yields field-level or raw chunks.

- `flock.core.eval.react_agent`:
  - A minimal, well-documented ReAct runner:
    - Maintains a trajectory dict list.
    - Accepts tools as plain callables (native) and/or MCP tools (already standardized in Flock).
    - Fallback extraction pass to populate declared outputs at the end.

- `flock.components.evaluation.declarative_evaluation_component`:
  - Feature-flag to switch from DSPy path to native path, preserving the public component config API.
  - Controlled via `DeclarativeEvaluationConfig.override_evaluator_type` (e.g., `"native"`), or env `FLOCK_USE_NATIVE_EVALUATOR=1`.

Pros:
- Fewer moving parts; predictable behavior; easier debugging.
- We own the template and loop shape; easier to evolve routing/memory integration.
- No transitive dependency on DSPy when we don’t need the rest of its features.

Cons/Risks:
- We must implement and maintain a small ReAct and streaming wrapper.
- Loss of future DSPy features/optimizers (which we currently don’t use in core flows).

---

## Alternative Libraries and Patterns Considered

- LiteLLM only (recommended base):
  - We already rely on it (via DSPy). Provides provider unification, retries, and streaming.
  - Combined with a tiny Flock-native layer, this is sufficient.

- OpenAI/Anthropic function calling / JSON schema:
  - For providers that support structured outputs, leverage response_format and tool/function-calling natively.
  - We can route through LiteLLM to keep cross-provider sanity.

- Guidance (Microsoft):
  - Powerful templating and grammar constraints. Heavyweight for our needs; adds another DSL.

- Instructor / Outlines:
  - Good for Pydantic-typed structured outputs. Viable for the “Predict” path but not a complete ReAct solution.

- LangGraph / LangChain:
  - LangGraph adds graph-native orchestration for agent workflows (plan/execute, supervisor/replanner, handoffs). Popular planning archetypes appear across many public repos (e.g., multi-agent SWE assistants, deepresearch templates, plan-execute examples). Useful reference for planning shapes and streaming UX, but we don’t need their full stack.
  - LangChain remains heavy for our goals; we can take inspiration from graph/supervisor patterns without importing the framework.

- CrewAI:
  - Team-of-agents coordination with roles and tasks; comes with planning/execution patterns. Good reference for multi-agent “crew” abstractions. Again, heavier than needed for Flock’s minimal, declarative approach.

Recommendation: LiteLLM + small native layer. Optionally add Instructor-like helpers for structured outputs if desired.

---

## Migration Plan

1) Add native evaluator behind a feature gate
- Implement `flock.core.eval.*` (LM client, predictor, react agent, streaming).
- Extend `DeclarativeEvaluationComponent` to branch: `override_evaluator_type="native"` or env toggle.
- Reuse existing tests; add parity tests to ensure output shape and error paths match.

2) Default to native evaluator
- After a release or two with opt-in, flip the default and keep DSPy path as fallback.

3) Remove DSPy dependency
- Once stable and docs/examples are updated, drop DSPy from core (keeping a compatibility shim if needed).

---

## Modularity-First Design (In The Spirit of Flock)

Goal: Make planning and reasoning algorithms swappable components — simple to adopt, easy to extend. Devs select a “program” like Predict, ReAct, Plan-Execute, ToT, Debate, or Reflection by adding a component or setting a config flag. Internals stay orthogonal: LM client, prompt builder, tool adapter, streaming, and cost tracking are thin, composable helpers.

Proposed building blocks (new internal modules under `flock.core.eval.*`):

- `LMClient` (provider-agnostic, LiteLLM-backed)
  - Handles retries, timeouts, provider quirks (e.g., reasoning models), streaming chunk normalization, usage/cost.
  - Pure function surface: `generate(request)`, `stream(request)`.

- `PromptBuilder`
  - Converts Flock contracts (string/Pydantic) to instruction + JSON schema (when supported).
  - Exposes a stable structure Flock controls (no opaque adapters): system message, user message, optional guardrails.

- `ToolAdapter`
  - Uniform callable protocol for native Python tools and MCP tools.
  - No wrapping into third-party types; program loops can invoke tools via a single interface.

- `Programs` (plug-in family; all share the same interface)
  - `PredictProgram`: one-shot structured prediction; uses schema or robust JSON parsing + correction.
  - `CoTProgram`: emits intermediate reasoning fields and extracts structured outputs.
  - `ReActProgram`: lean iterative loop with thought/tool/args/observation; finish or `max_iters`.
  - `PlanExecuteProgram`: two-phase (planner produces steps → executor performs them, optional replanner/critic).
  - `ToTProgram` (Tree-of-Thoughts): optional breadth/depth search with scoring heuristics; opt-in and bounded by config.
  - `DebateProgram`: orchestrates two (or more) sub-reasoners + an arbiter; bounded turns.
  - `ReflectionProgram`: adds self-critique pass and targeted re-ask.

  Each program implements:
  - `run(inputs, tools, prompt, lm, options) -> dict`
  - Optional `run_stream(...) -> AsyncIterator[StreamEvent]`

- `StreamAdapter`
  - Maps LiteLLM chunks to typed events (token, field, status), allowing OutputUtility/UI to render consistently.

How this plugs into Flock components
- Keep `DeclarativeEvaluationComponent` as the single entrypoint; it delegates to a `Program` selected via config.
- Config examples:
  - `program_type: "predict" | "react" | "plan_execute" | "cot" | "debate" | "tot" | "reflection"`
  - `max_iters`, `enable_stream`, `use_schema`, `planner_model`, `critic_model`, etc.
- Programs are registered and discovered like any other component type (small registry), so users can author custom programs.

Why this is simple for developers
- Minimal API: devs set `program_type` and maybe `max_iters`; everything else works with the same contracts.
- Clear extension point: drop in a new `Program` without touching LM, tools, or streaming layers.
- Consistent output: programs emit structured dicts conforming to the declared output schema.

References from the ecosystem (for patterns, not as dependencies)
- Plan/Execute and Supervisor patterns: many LangGraph-based repos (e.g., multi-agent SWE assistants, plan-execute templates, deepresearch starters) illustrate task breakdown, replanning, routing.
- ReAct: DSPy’s `ReAct` and various LangChain/LangGraph examples.
- Reflection/Debate/ToT: research-style nodes that can be bounded and made optional.

Recommended initial set
- PredictProgram (default), ReActProgram, PlanExecuteProgram, ReflectionProgram.
- Add CoT and ToT as opt-in modules once the core is stable.

Testing strategy
- Parity tests vs current DSPy-backed flows for Predict and ReAct (same inputs → same shape; comparable behavior under errors).
- Bounded, deterministic tests for PlanExecute and Reflection (fake tools and LM stubs).

---

## Async/Sync Execution Model (Impact and Plan)

Today
- Flock exposes both `run` (sync) and `run_async`. Internally some wrappers call `run_until_complete`, which can clash with already-running loops (e.g., notebooks).
- DSPy relies on global `dspy.settings` which complicates safe reentrancy and parallelism.

Going Native — Benefits
- `LMClient` is fully async and stateless; Programs are async by default. No global settings to mutate across runs.
- Streaming is modeled as an async iterator with typed events, enabling clean backpressure and cancellation.
- LiteLLM supports async + concurrency; we can map this directly into safe Program concurrency when appropriate.

Plan
- Keep `Program.run` async and expose sync wrappers at the orchestrator or component boundary only (thin and testable).
- Improve the sync wrapper to handle running-loop environments safely (e.g., schedule in a background thread/loop when a loop is already running, or use anyio’s utilities).
- Ensure run-batch helpers rely on TaskGroup-style concurrency (asyncio/anyio) with strict caps.
- Add tests for: sync-in-running-loop, streaming consumption, and concurrent invocations (no shared state).


## Developer Ergonomics Improvements (with a native layer)

- First-class JSON schema outputs:
  - Use Pydantic models directly to derive JSON schema.
  - Pass schema to providers that support it; instruct robust JSON-only fallback otherwise.

- Tool integration without wrappers:
  - Accept native callables and Flock MCP tools; standardize invocation and error surfaces.

- Streaming UX:
  - Yield typed chunks (field, delta) instead of raw tokens only.
  - Make it easy to plug into OutputUtility and the Web UI.

- Clearer traces:
  - Keep a simple, structured `trajectory` list the UI/telemetry can render without adapter black boxes.

---

## Recommendation

Proceed with a native, minimal evaluator path built on LiteLLM and Flock’s own contract parsing and tool registry. Keep DSPy as an optional fallback during migration. This improves control, simplifies dev ergonomics, and reduces indirect complexity without sacrificing capabilities we rely on.

If we later need optimizer-like capabilities (few-shot selection, program synthesis), we can design them to operate purely on Flock’s contracts and traces, independent of any external runtime.

---

## Why Flock Needs This (Long‑Term Win)

- Reduce cognitive load: Owning a small, explicit evaluator surface (LMClient + Programs) matches Flock’s declarative/contracts-first mental model and makes behavior obvious, testable, and teachable.
- Modularity at the core: Planning algorithms (ReAct, Plan‑Execute, Reflection, ToT, Debate) become simple, swappable Programs — consistent with Flock’s “Agent + Components” ethos.
- Fewer hidden globals: Removing reliance on `dspy.settings` and adapter magic eliminates surprising side‑effects across runs/tests and lowers debugging time.
- Faster iteration: We can evolve prompts, schema constraints, and tool invocation rules without waiting on third‑party changes; migration to new provider features (e.g., structured outputs, parallel tools) becomes straightforward.
- Better UX and docs: Devs pick `program_type` and go; outputs are always shaped by the agent’s declared contract. This makes examples, tutorials, and API docs cleaner and more consistent.
- Safer defaults at scale: A native ReAct loop can enforce hard iteration/time budgets; Plan‑Execute/Reflection can include guardrails that fit our telemetry and Temporal story.
- Optional, not mandatory: DSPy remains a fallback during migration, keeping risk managed, while we steadily move to the native path.
