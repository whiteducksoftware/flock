# Engine Evaluation: DSPy vs. BAML (and Alternatives)

This document analyzes candidate “LLM engines” for Flock’s declarative evaluation component. It compares the current DSPy-based path with BAML and other viable libraries through the lens of Flock’s philosophy and architecture, and outlines a pragmatic migration plan toward an engine-agnostic design.

## Executive Summary

- DSPy gives powerful “programming LLMs” primitives (Signatures, Predict, ReAct, CoT, Teleprompters) but introduces complexity that clashes with Flock’s goals of minimal mental model and contract-first ergonomics. Our current integration (see `src/flock/components/evaluation/declarative_evaluation_component.py` and `src/flock/core/mixin/dspy_integration.py`) is functional but brittle, difficult to extend, and leaks DSPy semantics into component code and MCP tools.
- BAML focuses squarely on strongly typed, validated structured outputs via a DSL and generated clients, with runtime “TypeBuilder” for dynamic schemas. This aligns closely with Flock’s “contracts first, Pydantic-native, testable by default” philosophy. Trade‑off: adds a code‑gen/build step and a new toolchain to the dev workflow.
- Recommendation: introduce an engine abstraction and prototype a BAML-backed `EvaluationComponent`. Keep DSPy available for advanced agentic patterns (ReAct/CoT/tools) while prioritizing BAML (or a simpler Pydantic-first engine) for structured I/O tasks. In parallel, evaluate lightweight engines (PydanticAI, Instructor) for a minimal, dependency-friendly default.

## Flock Philosophy Recap (what matters for the engine)

- Declarative contracts: inputs/outputs expressed as Pydantic (or equivalent) with clear, testable schemas.
- Unified mental model: Agent + Components; engines should be implementation details behind `EvaluationComponent`s.
- Production-ready: deterministic tests, CI stability, snapshot-able serialization, minimal global state.
- Extensibility: easy to add tools/MCP, dynamic types, streaming, and error handling without deep vendor lock-in.

## Current State: DSPy in Flock

Relevant code:
- `src/flock/components/evaluation/declarative_evaluation_component.py` (primary evaluator)
- `src/flock/core/mixin/dspy_integration.py` (signature building, LM config, tool plumbing, result shaping)
- `src/flock/components/utility/memory_utility_component.py` (touches DSPy signatures for memory exposure)
- MCP integration: `src/flock/core/mcp/*` uses `dspy.Tool` wrapping

Strengths
- Rich primitives: `Predict`, `ReAct`, `ChainOfThought`, streaming via `dspy.streamify`, history/cost tracking.
- Signatures allow typed I/O, including Literals and custom types. We already translate our declarative strings to DSPy signatures.
- Teleprompting/optimizers can iteratively improve programs (not heavily used in Flock today).

Pain Points (observed in repo and tests)
- Complexity/ergonomics: bridging Flock contracts → DSPy Signatures → DSPy Modules leads to indirection and maintenance burden (see type resolution in `DSPyIntegrationMixin._resolve_type_string`, field parsing, error fallbacks).
- Tight coupling: `dspy.Tool` shows up in our MCP layers; streaming & result normalization logic is engine-specific in component code.
- Determinism/testability: teleprompting and global DSPy `settings` interplay can be flaky if not carefully isolated.
- Extensibility: adding alternative engines today means replicating substantial evaluator logic and rethinking result shaping and tool adapters.

## BAML Overview (BoundaryML/baml)

What it offers (from docs and examples)
- DSL with explicit input/output schemas and `{{ ctx.output_format }}` to strongly bias structured output (JSON).
- Generated clients for Python/TS/Ruby/etc., with Python Pydantic targets. Good fit for Flock’s Pydantic-first contracts.
- Runtime `TypeBuilder` for dynamic schemas, unions, optionals, streaming state types, and field-level assertions/validators (`@assert`).
- Guardrails/validation built-ins with consistent error types (`BamlValidationError`).
- Tooling: CLI (`baml init`, `baml-cli generate`), codegen configuration, streaming hooks.

Benefits vs Flock goals
- Contracts-first: BAML is schema‑oriented; codegen produces Pydantic models/clients—natural fit for Flock’s I/O discipline and snapshot testing.
- Deterministic tests: validations and structured parsing reduce “prompt drift”; easier golden snapshots of `to_dict()`.
- Dynamic types: `TypeBuilder` provides runtime schema evolution akin to how we currently mutate DSPy signatures.
- Multi-language: not critical for Flock runtime, but strengthens ecosystem compatibility (servers/SDKs).

Trade-offs
- Build step + CLI dependency: requires code generation and version matching for the runtime; CI needs to install/run CLI.
- Less native agentic control than DSPy: BAML focuses on structured outputs; “ReAct” style control loops remain on Flock side (fine, since Flock already models routing/loops as components).

## Head-to-Head: DSPy vs BAML (fit for Flock)

Criteria | DSPy | BAML
---|---|---
Contract-first I/O | Supported via Signatures, but Flock must map its model → Signature manually | Native; DSL → generated Pydantic models; validations and asserts
Testability/determinism | Good if avoiding optimizers; global `settings`/history can leak | Strong; schema bias + parser improves consistency, typed errors for failures
Complexity in Flock | High: custom signature builder, tool adapters, result shaping | Moderate: codegen + runtime TypeBuilder; engine code in Flock stays thin
Tools/MCP | `dspy.Tool` mature; we already wrap MCP tools | Represent tools as typed inputs/outputs; selection flows stay in Flock routing; still feasible
Streaming | Available via `dspy.streamify` | Available; streaming fields/types and React hooks patterns; parity sufficient for Flock UI
Reasoning/CoT | First-class (`ChainOfThought`, `ReAct`) | Expressed via prompts/flow; CoT not a first-class engine primitive
DevOps | Python lib only | CLI + runtime; language server, generators; more moving parts

Conclusion
- For structured generation against explicit contracts (the majority of Flock use), BAML is a closer match to Flock’s philosophy and reduces integration code.
- For deeply agentic, tool-heavy reasoning loops, DSPy still shines; Flock can retain DSPy as an optional engine for those cases.

## Other Engine Candidates (GitHub survey)

- PydanticAI (pydantic-ai)
  - Fit: Very strong for Flock’s Pydantic‑first ethos; minimal, Pythonic, provider-agnostic; easy to mock in tests.
  - Status: Active; examples in repos referencing “pydantic-ai” show agents with structured outputs and good validation.
  - Consider as “default lightweight engine” for simple contracts, with BAML as the heavier, schema/DSL option.

- Instructor (ecosystem using “instructor” with Pydantic)
  - Fit: Simple structured output validation around providers; small surface area; easy integration/testing; no codegen.
  - Limits: Fewer built-ins than BAML; no DSL/TypeBuilder; relies more on provider JSON modes/function calling.
  - Good candidate for a very lightweight engine adapter.

- Guardrails (guardrails-ai/guardrails)
  - Fit: Rich validation/guarding layer; complements any engine; can be integrated as a validation UtilityComponent.
  - Limits: Not an “engine” by itself; adds complexity; good as optional guard layer regardless of engine.

- LMQL (lmql-lang/lmql)
  - Fit: Strong constraint language; academic pedigree; could improve determinism.
  - Limits: Adds a new language/runtime; heavier developer learning; likely overkill vs Flock goals.

- Jsonformer/Outlines/Guidance (structured generation/regex/grammars)
  - Fit: Strong guarantees for JSON/grammar-constrained outputs; potential for deterministic tests.
  - Limits: Varying maturity; may require bespoke adapters and limit multi‑modal/tooling.

Overall
- Shortlist to prototype: BAML, PydanticAI, Instructor. Guardrails as an optional validator utility.

## Migration Plan: Engine Abstraction

Introduce a small, stable interface used by `EvaluationComponent`s. Sketch:

```python
class EngineResult(TypedDict, total=False):
    data: dict
    raw: Any
    cost: float
    history: list[Any]

class EvaluationEngine(Protocol):
    async def prepare(self, schema: type[BaseModel] | str, **opts) -> None: ...
    async def run(self, inputs: dict[str, Any], tools: list[Any] | None = None) -> EngineResult: ...
    def stream(self, inputs: dict[str, Any], tools: list[Any] | None = None) -> AsyncIterator[Any]: ...
```

- Add thin adapters:
  - `DspyEngine` (wraps our existing `DSPyIntegrationMixin` logic)
  - `BamlEngine` (wraps BAML client; `TypeBuilder` for runtime fields; converts exceptions to a consistent error dict)
  - `PydanticAIEngine` (provider-agnostic, minimal)
  - `InstructorEngine` (lightweight structured output)
- Update `DeclarativeEvaluationComponent` to depend on `EvaluationEngine` via DI/config, not on DSPy directly. Preserve existing config surface (model, temperature, streaming, max_retries, tools) and map to engine-specific options.
- Keep MCP tool abstraction engine-neutral. Provide helper to map MCP tools to engine tool specs once per engine.

## What Changes in Flock

- Components
  - New `flock.core.eval.engines/` package with engines and thin helpers.
  - Refactor `DeclarativeEvaluationComponent` to select an engine by name (`"baml" | "dspy" | "pydanticai" | "instructor"`).
  - Preserve `include_reasoning/include_thought_process` filters; engines return fields that we filter consistently.

- Tests
  - Add `p0` tests to run the same agent against two engines with identical Pydantic I/O to assert consistent behavior and to snapshot `to_dict()`.
  - Add error‑path tests to ensure engine exceptions → structured error dict.

- CI/Tooling
  - If BAML is enabled, add CLI install step in CI and codegen caching (keep BAML behind optional marker initially).
  - Maintain “no network by default” by faking providers or injecting “echo” engines for tests.

## Risks & Mitigations

- BAML toolchain overhead: Keep BAML adapter opt‑in at first; default to PydanticAI/Instructor for dev speed.
- Engine divergence: Limit `EvaluationEngine` surface to stabilize; avoid bleeding engine types into components.
- Backwards compatibility: Keep DSPy adapter; default engine can be set per agent/config.

## Recommendation

- Adopt an engine‑agnostic design and ship two adapters in sequence:
  1) `PydanticAIEngine` or `InstructorEngine` as the default lightweight structured-output path.
  2) `BamlEngine` as an opt‑in for stronger schema enforcement and TypeBuilder features.
- Keep `DspyEngine` available for ReAct/CoT‑heavy scenarios and as a bridge for existing users.
- Add `GuardrailsUtilityComponent` for validation independent of engine.

This approach honors Flock’s contract-first focus, improves testability and maintainability, and reduces DSPy coupling without forcing a full rewrite.

## Next Steps (proposed spikes)

- Spike 1: Define `EvaluationEngine` protocol + `DspyEngine` adapter (wrap existing code); migrate `DeclarativeEvaluationComponent` to use it.
- Spike 2: Prototype `PydanticAIEngine` or `InstructorEngine` with a minimal subset (non-streaming) and P0 tests.
- Spike 3: Prototype `BamlEngine` behind optional marker, add simple codegen in CI, dynamic field with `TypeBuilder`, and error-path tests.
- Spike 4: MCP tools unification: design an engine-neutral tool spec and mappers.
- Spike 5: Docs: author “Choosing an Engine” guide and update examples.

## References (GitHub/Docs used)

- DSPy (stanfordnlp/dspy): signatures, Predict/ReAct/CoT, streaming, tools, history/cost.
- BAML (BoundaryML/baml): DSL, `ctx.output_format`, Python/Pydantic codegen, `TypeBuilder`, streaming and assertions, typed errors.
- Additional candidates (from GitHub search): PydanticAI, Instructor, Guardrails, LMQL.

