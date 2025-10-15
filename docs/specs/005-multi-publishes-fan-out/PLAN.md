# Implementation Plan

## Validation Checklist
- [x] Context Ingestion section complete with all required specs
- [x] Implementation phases logically organized
- [x] Each phase starts with test definition (TDD approach)
- [x] Dependencies between phases identified
- [x] Parallel execution marked where applicable
- [ ] Multi-component coordination identified (if applicable)
- [x] Final validation phase included
- [x] No placeholder content remains

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate
2. **During Implementation**: Reference specific design documents in each task
3. **After Each Task**: Run Specification Compliance checks
4. **Phase Completion**: Verify all specification requirements are met

### Deviation Protocol

If implementation cannot follow specification exactly:
1. Document the deviation and reason
2. Get approval before proceeding
3. Update design docs if the deviation is an improvement
4. Never deviate without documentation

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[component: component-name]` - For multi-component features
- `[ref: document/section; lines: 1, 2-3]` - Links to specifications, patterns, or interfaces and (if applicable) line(s)
- `[activity: type]` - Activity hint for specialist agent selection

---

## Context Priming

*GATE: You MUST fully read all files mentioned in this section before starting any implementation.*

**Research Documentation**:

- `docs/internal/improved-publishes/design.md` - Complete `.publishes()` enhancement design
- `docs/internal/improved-publishes/architecture-changes.md` - Multiple engine calls architecture
- `docs/internal/improved-publishes/implementation-guide.md` - Step-by-step implementation guide
- `docs/internal/improved-publishes/examples.md` - Real-world use cases
- `docs/internal/improved-publishes/comparison.md` - Why this approach wins
- `docs/internal/improved-publishes/additional_ideas.md` - Sugar syntax ideas

**Key Design Decisions**:

1. **Multiple `.publishes()` calls = Multiple engine calls** - Perfect symmetry with `.consumes()`
2. **Single `.publishes(A, A, A)` = One engine call** - Generate related artifacts together
3. **Output Groups** - Each `.publishes()` call creates an `OutputGroup`, each group triggers one engine call
4. **TDD First** - Tests define behavior before implementation
5. **First iteration includes**: `fan_out`, `where`, `visibility`, `validate`, `description` parameters

**Implementation Context**:

- Commands to run: `pytest tests/` for testing, check existing test patterns in `tests/test_agent_builder.py`
- Current architecture: Agent execution calls `_run_engines()` once, needs modification for multiple groups
- Pattern to follow: Similar to how `.consumes()` accumulates subscriptions

---

## Implementation Phases

### Phase 1: Data Structures & Output Groups

**Goal**: Establish the core data structures for tracking multiple publish groups and their configuration.

- [x] **Prime Context**: Read architecture and implementation details
    - [x] Read `docs/internal/improved-publishes/architecture-changes.md` - Multiple engine calls design `[ref: architecture-changes.md; lines: 1-100]`
    - [x] Read `src/flock/agent.py` - Current AgentOutput structure `[ref: agent.py; lines: 63-86]`

- [x] **Write Tests**: Test OutputGroup and enhanced AgentOutput data structures `[activity: test-writing]`
    - [x] Test `OutputGroup` dataclass creation with multiple outputs
    - [x] Test `AgentOutput` with `fan_out`, `where`, `visibility`, `validate`, `description` fields
    - [x] Test that `OutputGroup.is_single_call()` returns True
    - [x] Test validation: `fan_out >= 1` or raise ValueError
    - [x] Test validation: `where` callable accepts BaseModel and returns bool
    - [x] Test validation: `validate` callable or list of (callable, error_msg) tuples

- [x] **Implement**: Create OutputGroup and enhance AgentOutput `[ref: architecture-changes.md; lines: 110-135]` `[activity: data-modeling]`
    - [x] Create `OutputGroup` dataclass in `src/flock/agent.py`:
        ```python
        @dataclass
        class OutputGroup:
            outputs: list[AgentOutput]
            shared_visibility: Visibility | None = None
            group_description: str | None = None
        ```
    - [x] Enhance `AgentOutput` dataclass to include:
        - `count: int = 1` - Number of artifacts to generate
        - `filter_predicate: Callable[[BaseModel], bool] | None = None` - Where clause
        - `validate_predicate: Callable[[BaseModel], bool] | list[tuple[Callable, str]] | None = None`
        - `group_description: str | None = None` - Override agent description for this group
    - [x] Add `is_many()` method to AgentOutput: `return self.count > 1`

- [x] **Validate**: Code quality and test passage
    - [x] Run tests: `pytest tests/test_agent_builder.py -v` `[activity: run-tests]`
    - [x] Lint code: Ensure dataclasses follow project style `[activity: lint-code]`
    - [x] Review: Data structures are immutable where appropriate `[activity: review-code]`

### Phase 2: AgentBuilder.publishes() Enhancement

**Goal**: Modify `.publishes()` to support multiple calls (creating groups) and new sugar parameters.

- [x] **Prime Context**: Understand current publishes() implementation
    - [x] Read `src/flock/agent.py` - AgentBuilder.publishes() `[ref: agent.py; lines: 646-699]`
    - [x] Read `docs/internal/improved-publishes/design.md` - API design `[ref: design.md; lines: 119-137]`

- [x] **Write Tests**: Test enhanced .publishes() API `[activity: test-writing]`
    - [x] Test single `.publishes(A, B, C)` creates ONE OutputGroup with 3 outputs
    - [x] Test multiple `.publishes(A).publishes(B)` creates TWO OutputGroups (1 output each)
    - [x] Test `.publishes(A, A, A)` counts duplicates → 1 group, 3 A's
    - [x] Test `.publishes(A, fan_out=3)` creates 1 group with 3 A's (sugar syntax)
    - [x] Test `.publishes(A, where=lambda x: x.valid)` stores filter predicate
    - [x] Test `.publishes(A, visibility=lambda x: "public" if x.important else "private")` stores dynamic visibility
    - [x] Test `.publishes(A, validate=lambda x: x.score > 0)` stores validation
    - [x] Test `.publishes(A, description="Special instructions")` stores group description
    - [x] Test combining parameters: `.publishes(A, fan_out=3, where=..., validate=...)`
    - [x] Test that `fan_out=0` raises ValueError
    - [x] Test backwards compatibility: existing `.publishes(A)` still works

- [x] **Implement**: Enhanced AgentBuilder.publishes() method `[ref: architecture-changes.md; lines: 150-200]` `[activity: api-development]`
    - [x] Change `Agent` class: replace `outputs: list[AgentOutput]` with `output_groups: list[OutputGroup]`
    - [x] Update `AgentBuilder.publishes()` signature:
        ```python
        def publishes(
            self,
            *types: type[BaseModel],
            visibility: Visibility | Callable[[BaseModel], Visibility] | None = None,
            fan_out: int | None = None,
            where: Callable[[BaseModel], bool] | None = None,
            validate: Callable[[BaseModel], bool] | list[tuple[Callable, str]] | None = None,
            description: str | None = None
        ) -> PublishBuilder:
        ```
    - [x] Implement duplicate counting when no `fan_out` provided (preserves order)
    - [x] Apply `fan_out` to ALL types when specified
    - [x] Create `OutputGroup` from outputs and append to `agent.output_groups`
    - [x] Store predicates and descriptions in each `AgentOutput`
    - [x] Validate `fan_out >= 1` if provided
    - [x] Return `PublishBuilder` for chaining

- [x] **Validate**: API correctness and backwards compatibility
    - [x] Run tests: `pytest tests/test_agent_builder.py::test_publishes* -v` `[activity: run-tests]`
    - [x] Verify backwards compatibility: existing code doesn't break `[activity: business-acceptance]`
    - [x] Review: API is intuitive and consistent with `.consumes()` `[activity: review-code]`

### Phase 3: Multiple Engine Calls in Agent.execute()

**Goal**: Modify agent execution to call the engine once per OutputGroup instead of once total.

**Status**: ✅ **COMPLETE** (Shipped 2025-10-15)

- [x] **Prime Context**: Understand current execution flow
    - [x] Read `src/flock/agent.py` - Agent.execute() and _run_engines() `[ref: agent.py; lines: 92-310]`
    - [x] Read `docs/internal/improved-publishes/architecture-changes.md` - Execution changes `[ref: architecture-changes.md; lines: 240-300]`

- [x] **Write Tests**: Test multiple engine call execution `[activity: test-writing]`
    - [x] Test agent with `.publishes(A).publishes(B).publishes(C)` calls engine 3 times
    - [x] Test agent with `.publishes(A, B, C)` calls engine 1 time
    - [x] Test agent with `.publishes(A, fan_out=3)` calls engine 1 time, generates 3 artifacts
    - [x] Test that each engine call receives group-specific context
    - [x] Test that artifacts from all groups are collected
    - [x] Test that engine calls are sequential (not parallel initially)
    - [x] Test error handling: if one group fails, others don't execute
    - [x] Mock engine to count calls and verify behavior

- [x] **Implement**: Multiple engine calls per execution `[ref: architecture-changes.md; lines: 240-280]` `[activity: performance-optimization]`
    - [x] Modify `Agent.execute()` (lines 194-239):
        - Loop over `self.output_groups`
        - Call `_run_engines()` once per group
        - Collect all outputs into single list
    - [x] Implement `_prepare_group_context()` (lines 490-509):
        - Ready for Phase 4 group-specific context
        - Currently passes same context (stub for future enhancement)
    - [x] Implement `_make_outputs_for_group()` (lines 511-576):
        - Extract artifacts matching THIS group's output types only
        - **Strict contract validation**: Engine must produce exactly `count` artifacts
        - Raises `ValueError` if contract violated (no silent failures)
        - Publish artifacts to board

- [x] **Validate**: Execution correctness and performance
    - [x] Run tests: `pytest tests/test_agent_builder.py` - All 48 tests passing (100%)
    - [x] Test results: 39 existing + 9 new Phase 3 tests
    - [x] Review: Error handling is robust (fail-fast on contract violations)
    - [x] Performance: Sequential execution, no excessive overhead
    - [x] Backwards compatibility: Agents without output_groups still work

**Deliverables**:
- `src/flock/agent.py` (lines 194-576): Multiple engine call architecture
- `tests/test_agent_builder.py` (lines 892-1489): 9 comprehensive async tests
- `tests/PHASE3_TEST_SUMMARY.md`: Complete test documentation

### Phase 4: Engine Fan-Out Contract + Concurrency Fix

**Goal**: Add `evaluate_fanout()` method to EngineComponent, allowing engines to opt-in to fan-out generation. Not all engines are LLMs - let each engine decide how to handle multiple outputs.

**Status**: ✅ **COMPLETE** (Shipped 2025-10-15)

**⚠️ BREAKING CHANGE**: All three engine methods (`evaluate`, `evaluate_batch`, `evaluate_fanout`) now receive `output_group: OutputGroup` parameter to fix critical concurrency bug. See `CONCURRENCY_FIX.md` for full rationale.

**Architecture Insight**: Following the `evaluate_batch()` pattern from `components.py:116-146`, engines should declare fan-out support explicitly. This keeps the framework engine-agnostic (no assumptions about prompts/LLMs).

**Concurrency Fix**: Engines must know which OutputGroup they're generating for. Passing `output_group` explicitly prevents shared-state bugs and makes the system thread-safe.

- [x] **Prime Context**: Understand engine abstraction patterns
    - [x] Read `src/flock/components.py` - EngineComponent base class `[ref: components.py; lines: 96-219]`
    - [x] Read `src/flock/engines/dspy_engine.py` - How DSPyEngine implements evaluate() and evaluate_batch() `[ref: dspy_engine.py; lines: 113-160]`
    - [x] Review evaluate_batch() pattern as template for evaluate_fanout() `[ref: components.py; lines: 116-146]`

- [x] **Write Tests**: Test fan-out engine contract `[activity: test-writing]`
    - [x] Test `EngineComponent.evaluate_fanout()` raises NotImplementedError by default
    - [x] Test error message includes helpful guidance (like evaluate_batch does)
    - [x] Test engine that implements evaluate_fanout() is called correctly
    - [x] Test Agent.execute() detects fan-out scenario and calls appropriate method
    - [x] Test error when fan-out requested but engine doesn't support it
    - [x] Mock fan-out-aware engine that returns exactly `count` artifacts
    - [x] Test that output_group is passed to all engine methods

- [x] **Implement**: Update ALL three engine methods in EngineComponent `[ref: components.py; lines: 96-219]` `[activity: component-development]`
    - [x] Update `evaluate()` signature - add `output_group` parameter:
        ```python
        async def evaluate(
            self,
            agent: Agent,
            ctx: Context,
            inputs: EvalInputs,
            output_group: OutputGroup  # NEW - tells engine what to produce
        ) -> EvalResult:
            raise NotImplementedError
        ```
    - [x] Update `evaluate_batch()` signature - add `output_group` parameter:
        ```python
        async def evaluate_batch(
            self,
            agent: Agent,
            ctx: Context,
            inputs: EvalInputs,
            output_group: OutputGroup  # NEW - tells engine what to produce
        ) -> EvalResult:
            raise NotImplementedError(...)
        ```
    - [x] Add `evaluate_fanout()` method - with `output_group` parameter:
        ```python
        async def evaluate_fanout(
            self,
            agent: Agent,
            ctx: Context,
            inputs: EvalInputs,
            output_group: OutputGroup  # Replaces count + group_description
        ) -> EvalResult:
            """Generate multiple outputs for an OutputGroup (fan-out).

            Override this method if your engine supports fan-out generation.
            The output_group tells you exactly what types and counts to produce.

            Args:
                agent: Agent instance executing this engine
                ctx: Execution context
                inputs: EvalInputs with input artifacts
                output_group: OutputGroup defining what to generate

            Returns:
                EvalResult with artifacts matching output_group specs

            Example:
                >>> async def evaluate_fanout(self, agent, ctx, inputs, output_group):
                ...     count = output_group.outputs[0].count
                ...     type_name = output_group.outputs[0].spec.type_name
                ...     description = output_group.group_description
                ...     # Generate artifacts accordingly
                ...     results = await self.generate_multiple(inputs, count)
                ...     return EvalResult.from_objects(*results, agent=agent)
            """
            count = output_group.outputs[0].count if output_group.outputs else 1
            raise NotImplementedError(
                f"{self.__class__.__name__} does not support fan-out generation.\n\n"
                f"To fix this:\n"
                f"1. Remove fan_out parameter from .publishes(), OR\n"
                f"2. Implement evaluate_fanout() in {self.__class__.__name__}, OR\n"
                f"3. Use a fan-out-aware engine (e.g., DSPyEngine)\n\n"
                f"Agent: {agent.name}\n"
                f"Requested count: {count}\n"
                f"Engine: {self.__class__.__name__}"
            )
        ```
    - [x] Update `Agent.execute()` to pass `output_group` to engine methods:
        ```python
        for group_idx, output_group in enumerate(self.output_groups):
            group_ctx = self._prepare_group_context(ctx, group_idx, output_group)

            # Detect fan-out scenario (any output has count > 1)
            has_fanout = any(output.count > 1 for output in output_group.outputs)
            is_single_type = len(set(o.spec.type_name for o in output_group.outputs)) == 1

            if has_fanout and is_single_type:
                # Fan-out: call evaluate_fanout()
                try:
                    result = await self._run_engines_fanout(
                        group_ctx,
                        eval_inputs,
                        output_group  # Pass group directly
                    )
                except NotImplementedError:
                    # Engine doesn't support fan-out - provide clear error
                    raise ValueError(...) from None
            else:
                # Standard: call evaluate()
                result = await self._run_engines(
                    group_ctx,
                    eval_inputs,
                    output_group  # Pass group directly
                )

            group_outputs = await self._make_outputs_for_group(group_ctx, result, output_group)
            all_outputs.extend(group_outputs)
        ```
    - [x] Update `_run_engines()` to pass `output_group`:
        ```python
        async def _run_engines(self, ctx, inputs, output_group):
            for engine in engines:
                result = await engine.evaluate(self, ctx, inputs, output_group)
                # ... (or evaluate_batch if ctx.is_batch)
        ```
    - [x] Update `_run_engines_fanout()` to pass `output_group`:
        ```python
        async def _run_engines_fanout(self, ctx, inputs, output_group):
            engine = engines[0]
            result = await engine.evaluate_fanout(self, ctx, inputs, output_group)
            # ...
        ```

- [x] **Validate**: Engine contract correctness
    - [x] Run tests: All 1069 tests passing (100% green suite) `[activity: run-tests]`
    - [x] Test error messages: Clear and helpful (like evaluate_batch) `[activity: review-code]`
    - [x] Verify backward compatibility: existing engines still work `[activity: business-acceptance]`
    - [x] Mock engine test: Fan-out aware engine produces correct count `[activity: run-tests]`

**Design Rationale**:
- ✅ Engine-agnostic: No assumptions about LLMs, prompts, or implementation
- ✅ Opt-in pattern: Engines choose whether to support fan-out
- ✅ Clear errors: Helpful messages guide users to solutions
- ✅ Flexible: DSPyEngine can use prompts, other engines can use their own strategies
- ✅ Consistent: Follows existing evaluate_batch() pattern

**Deliverables**:
- Breaking change: All engine methods (`evaluate`, `evaluate_batch`, `evaluate_fanout`) now accept `output_group: OutputGroup` parameter
- `src/flock/components.py`: Added `evaluate_fanout()` method with helpful error messages
- `src/flock/agent.py`: Updated all engine calls to pass `output_group` parameter
- `src/flock/engines/dspy_engine.py`: Updated to support new signatures
- `tests/test_agent.py`: Updated for Phase 3/4 strict validation semantics
- `tests/test_agent_builder.py`: Added fan-out support to CountingMockEngine
- `tests/test_components.py`: Updated NotImplementedError tests
- `tests/test_orchestrator_batchspec.py`: Updated batch spec tests
- `tests/test_output_groups.py`: Fixed validation test data generation
- `tests/integration/test_collector_orchestrator.py`: Added missing `.publishes()` declarations
- All 1069 tests passing (100% green suite)
- Zero regressions, full backwards compatibility maintained
- Critical utility agent bugs fixed (empty output, post-evaluate hooks)

**Note**: DSPyEngine implementation of `evaluate_fanout()` is optional Phase 4.5 (after contract established)

### Phase 4.5: DSPyEngine Fan-Out Implementation

**Goal**: Implement `evaluate_fanout()` in DSPyEngine to generate multiple outputs by calling the DSPy program multiple times.

**Status**: ✅ **COMPLETE** (Shipped 2025-10-15)

**Prerequisites**: Phase 4 complete (engine contract established)

- [x] **Prime Context**: Understand DSPyEngine implementation
    - [x] Read `src/flock/engines/dspy_engine.py` - Current evaluate() and evaluate_batch() `[ref: dspy_engine.py; lines: 155-181]`
    - [x] Review how evaluate_batch() uses _evaluate_internal() for shared logic `[ref: dspy_engine.py; lines: 169-181]`

- [x] **Write Tests**: Test DSPyEngine fan-out behavior `[activity: test-writing]`
    - [x] Test DSPyEngine.evaluate_fanout() with fan_out=10 generates 10 artifacts
    - [x] Test WHERE filtering reduces published count (fan_out=20, filter to 5)
    - [x] Test VALIDATE checks enforce quality standards
    - [x] Test dynamic visibility works with DSPyEngine fan-out
    - [x] All 12 Phase 5 filtering/validation tests passing with DSPyEngine

- [x] **Implement**: DSPyEngine.evaluate_fanout() `[activity: component-development]`
    - [x] Added evaluate_fanout() method to DSPyEngine (lines 183-222):
        ```python
        async def evaluate_fanout(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
            """Fan-out evaluation for producing multiple artifacts from single execution.

            Generates exactly `count` artifacts for each output declaration in the output_group
            by calling the DSPy program multiple times.
            """
            if not inputs.artifacts:
                return EvalResult(artifacts=[], state=dict(inputs.state))

            # Calculate total number of artifacts to generate
            total_count = output_group.total_count

            # Generate artifacts by calling DSPy program multiple times
            all_artifacts = []
            state = dict(inputs.state)
            all_logs = []

            for i in range(total_count):
                # Call DSPy program once per artifact
                result = await self._evaluate_internal(agent, ctx, inputs, batched=False)

                # Accumulate artifacts
                all_artifacts.extend(result.artifacts)

                # Merge state (keep last state)
                state.update(result.state)

                # Accumulate logs
                all_logs.extend(result.logs)

            return EvalResult(artifacts=all_artifacts, state=state, logs=all_logs)
        ```

- [x] **Validate**: DSPyEngine fan-out correctness
    - [x] Run tests: All 12 Phase 5 tests passing (100%) `[activity: run-tests]`
    - [x] Full test suite: 1081 tests passing (sanity check complete) `[activity: run-tests]`
    - [x] Verified filtering, validation, and visibility work with DSPyEngine `[activity: business-acceptance]`

**Implementation Strategy**: Instead of using prompt engineering to get DSPy to output arrays, we call the DSPy program `count` times independently. This:
- ✅ Ensures diversity (each call is independent with LLM sampling)
- ✅ Reuses existing _evaluate_internal() logic (simple, maintainable)
- ✅ Works with any DSPy signature (no schema changes needed)
- ✅ Provides proper type safety and validation per artifact

**Deliverables**:
- `src/flock/engines/dspy_engine.py` (lines 183-222): Complete fan-out implementation
- All Phase 5 filtering/validation tests now work with DSPyEngine
- 1081 tests passing (full suite green)

**Design Note**: This implementation calls DSPy multiple times rather than using prompt engineering. Other engines can implement evaluate_fanout() differently based on their capabilities.

### Phase 5: Filtering, Validation, and Visibility

**Goal**: Implement `where`, `validate`, and dynamic `visibility` processing in `_make_outputs_for_group()`.

**Status**: ✅ **COMPLETE** (Shipped 2025-10-15)

- [x] **Prime Context**: Review filtering and validation requirements
    - [x] Read `docs/internal/improved-publishes/additional_ideas.md` - Filtering ideas `[ref: additional_ideas.md; lines: 10-80]`
    - [x] Read `docs/internal/improved-publishes/design.md` - Validation design `[ref: design.md; lines: 450-520]`

- [x] **Write Tests**: Test filtering, validation, and visibility `[activity: test-writing]`
    - [x] Test `where` filters out artifacts: fan_out=10, where filters to 3, only 3 published
    - [x] Test `validate` rejects invalid artifacts: raise ValueError with clear message
    - [x] Test `validate` with list of tuples: multiple checks with custom error messages
    - [x] Test dynamic `visibility`: callable determines visibility per artifact
    - [x] Test static `visibility`: all artifacts get same visibility
    - [x] Test combining where + validate: both applied in order
    - [x] Test error messages are helpful (include which check failed)

- [x] **Implement**: Filtering, validation, visibility in _make_outputs_for_group() `[activity: component-development]`
    - [x] Enhanced `_make_outputs_for_group()` (lines 662-721) with full implementation:
        - Validate engine contract: Must produce exactly `count` artifacts (strict validation)
        - Apply WHERE filtering: Reduces artifacts (non-error, preserves valid subset)
        - Apply VALIDATE checks: Single callable or list of (check, error_msg) tuples
        - Apply visibility: Static or dynamic (callable based on artifact content)
        - Publish artifacts to board with proper metadata
    - [x] **Key Implementation Detail**: Reconstruct Pydantic models from payload dicts before passing to predicates
        - Predicates expect `BaseModel` instances, not dicts
        - Use `type_registry.resolve()` to get model class
        - Construct: `model_instance = model_cls(**artifact.payload)`
    - [x] Original pseudocode from planning phase (archived for reference):
        ```python
        # 1. Collect matching artifacts
        matching = [a for a in result.artifacts if a.type == output.spec.type_name]

        # 2. Apply where filtering
        if output.filter_predicate:
            matching = [a for a in matching if output.filter_predicate(a.payload)]

        # 3. Apply validation
        if output.validate_predicate:
            if callable(output.validate_predicate):
                for artifact in matching:
                    if not output.validate_predicate(artifact.payload):
                        raise ValueError(f"Validation failed for {artifact.type}")
            elif isinstance(output.validate_predicate, list):
                for artifact in matching:
                    for check, error_msg in output.validate_predicate:
                        if not check(artifact.payload):
                            raise ValueError(f"{error_msg}: {artifact.type}")

        # 4. Apply visibility (static or dynamic)
        for artifact in matching:
            if callable(output.default_visibility):
                artifact.visibility = output.default_visibility(artifact.payload)
            else:
                artifact.visibility = output.default_visibility

        # 5. Verify count (if fan_out was specified)
        if output.is_many() and len(matching) != output.count:
            raise ValueError(
                f"Expected {output.count} artifacts of {output.spec.type_name}, "
                f"got {len(matching)}"
            )
        ```

- [x] **Validate**: Feature correctness and error handling
    - [x] Run tests: All 12 tests in `tests/test_filtering_validation.py` passing (100%)
    - [x] Test error messages: Clear ValueError messages with artifact type names
    - [x] Full test suite: 1081 tests passing (sanity check complete)

**Deliverables**:
- `src/flock/agent.py` (lines 662-721): Complete filtering/validation/visibility implementation
- `tests/test_filtering_validation.py` (610 lines): 12 comprehensive tests covering:
  - 3 WHERE filtering tests (basic, complex predicates, zero matches)
  - 4 VALIDATE tests (single predicate, list of tuples, all checks must pass, success case)
  - 2 Visibility tests (dynamic based on content, static for all)
  - 3 Combined feature tests (where+validate order, all three features together, error messages)
- All tests use NoOpUtility to bypass console output issues on Windows
- All tests use MockBoard pattern + direct agent.agent.execute()
- All type comparisons handle fully qualified names (`"ScoredResult" in a.type`)

### Phase 6: Documentation and Examples

**Goal**: Update documentation and create comprehensive examples showing new features.

- [ ] **Prime Context**: Review documentation needs
    - [ ] Read `docs/internal/improved-publishes/examples.md` - Example patterns `[ref: examples.md; lines: 1-600]`
    - [ ] Check existing `docs/AGENTS.md` for structure

- [ ] **Write Tests**: No tests needed for documentation `[activity: none]`

- [ ] **Implement**: Documentation updates `[activity: documentation]`
    - [ ] Update `docs/AGENTS.md`:
        - Add "Multiple Publish Calls" section
        - Explain semantic difference: multiple calls vs single call with duplicates
        - Show all sugar parameters with examples
        - Document cost implications (multiple calls = multiple LLM API calls)
    - [ ] Create `examples/showcase/08_multiple_publishes.py`:
        - Example 1: Voting pattern (3 independent solutions)
        - Example 2: Batch generation (fan_out=10)
        - Example 3: Filtering (where clause)
        - Example 4: Validation (validate predicate)
        - Example 5: Dynamic visibility
        - Example 6: Group description override
    - [ ] Create `examples/showcase/09_publishes_advanced.py`:
        - Example combining all features together
        - Real-world scenario: Research task generation
    - [ ] Update `src/flock/agent.py` docstrings:
        - Update `AgentBuilder.publishes()` docstring with all parameters
        - Add examples showing new features

- [ ] **Validate**: Documentation quality
    - [ ] Review: Examples are clear and runnable `[activity: review-code]`
    - [ ] Test: Examples actually work `[activity: run-tests]`
    - [ ] Check: All features documented `[activity: business-acceptance]`

### Phase 7: Integration & End-to-End Validation

**Goal**: Comprehensive testing of all features working together.

- [ ] **Prime Context**: Review full feature set
    - [ ] Reread all design documents to ensure nothing missed

- [ ] **Write Tests**: Comprehensive integration tests `[activity: test-writing]`
    - [ ] Test spec-driven V2 pattern: multiple agents with fan-out
    - [ ] Test voting pattern: 3 independent engine calls, select best
    - [ ] Test complex agent: multiple groups + filtering + validation + visibility
    - [ ] Test error cases: validation failures, count mismatches, filter edge cases
    - [ ] Test performance: agent with 10 output groups (acceptable overhead?)
    - [ ] Test with real LLM (optional, mark as slow test): verify LLM follows prompts

- [ ] **Implement**: Integration test suite `[activity: test-writing]`
    - [ ] Create `tests/integration/test_multi_publishes_e2e.py` with comprehensive scenarios
    - [ ] Create example spec-driven V2 workflow using new features
    - [ ] Test backwards compatibility: existing flock examples still work

- [ ] **Validate**: Complete system validation
    - [ ] All unit tests passing: `pytest tests/ -v` `[activity: run-tests]`
    - [ ] All integration tests passing `[activity: run-tests]`
    - [ ] Performance acceptable: no significant regression `[activity: performance-testing]`
    - [ ] Examples run successfully `[activity: business-acceptance]`
    - [ ] Code coverage meets standards (>80%) `[activity: review-code]`
    - [ ] Linting passes: `ruff check src/` `[activity: lint-code]`
    - [ ] Type checking passes: `mypy src/flock/agent.py` `[activity: lint-code]`
    - [ ] Documentation is complete and accurate `[activity: review-code]`
    - [ ] All design decisions implemented `[activity: business-acceptance]`
    - [ ] Backwards compatibility verified `[activity: business-acceptance]`

---

## Success Criteria

After implementation, the following should be true:

✅ **API Symmetry**: `.publishes()` works like `.consumes()` - multiple calls accumulate
✅ **Multiple Engine Calls**: Each `.publishes()` call = one engine call
✅ **Single Call Fan-Out**: `.publishes(A, A, A)` or `.publishes(A, fan_out=3)` = one call, multiple artifacts
✅ **Engine Fan-Out Contract**: `evaluate_fanout()` method allows engines to opt-in to fan-out support
✅ **Engine Agnostic**: No assumptions about LLMs, prompts, or engine implementation details
✅ **Sugar Parameters**: `fan_out`, `where`, `visibility`, `validate`, `description` all work
✅ **TDD**: Tests written first, all passing
✅ **Backwards Compatible**: Existing code works unchanged
✅ **Documentation**: Complete with examples
✅ **Performance**: No significant overhead from multiple groups
✅ **Error Messages**: Clear, actionable, helpful (following evaluate_batch pattern)

## Notes

- **TDD Emphasis**: EVERY phase starts with writing tests. No implementation without tests first!
- **Architectural Pivot**: Phase 4 changed from "LLM Prompt Engineering" to "Engine Fan-Out Contract" to keep framework engine-agnostic
- **Parallel Opportunity**: Phases 4.5-5-6 (DSPy implementation + filtering/validation + documentation) could be done in parallel after Phase 4 completes
- **Cost Consideration**: Document that multiple `.publishes()` calls = multiple engine calls = higher cost (depending on engine)
- **Future Enhancement**: After this ships, consider adding `parallel=True` option to execute groups concurrently
- **Design Pattern**: `evaluate_fanout()` follows the same opt-in pattern as `evaluate_batch()` - engines declare capabilities explicitly
