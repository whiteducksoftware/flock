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

- [ ] **Write Tests**: Test OutputGroup and enhanced AgentOutput data structures `[activity: test-writing]`
    - [ ] Test `OutputGroup` dataclass creation with multiple outputs
    - [ ] Test `AgentOutput` with `fan_out`, `where`, `visibility`, `validate`, `description` fields
    - [ ] Test that `OutputGroup.is_single_call()` returns True
    - [ ] Test validation: `fan_out >= 1` or raise ValueError
    - [ ] Test validation: `where` callable accepts BaseModel and returns bool
    - [ ] Test validation: `validate` callable or list of (callable, error_msg) tuples

- [ ] **Implement**: Create OutputGroup and enhance AgentOutput `[ref: architecture-changes.md; lines: 110-135]` `[activity: data-modeling]`
    - [ ] Create `OutputGroup` dataclass in `src/flock/agent.py`:
        ```python
        @dataclass
        class OutputGroup:
            outputs: list[AgentOutput]
            shared_visibility: Visibility
            group_description: str | None = None
        ```
    - [ ] Enhance `AgentOutput` dataclass to include:
        - `count: int = 1` - Number of artifacts to generate
        - `filter_predicate: Callable[[BaseModel], bool] | None = None` - Where clause
        - `validate_predicate: Callable[[BaseModel], bool] | list[tuple[Callable, str]] | None = None`
        - `group_description: str | None = None` - Override agent description for this group
    - [ ] Add `is_many()` method to AgentOutput: `return self.count > 1`

- [ ] **Validate**: Code quality and test passage
    - [ ] Run tests: `pytest tests/test_agent_builder.py -v` `[activity: run-tests]`
    - [ ] Lint code: Ensure dataclasses follow project style `[activity: lint-code]`
    - [ ] Review: Data structures are immutable where appropriate `[activity: review-code]`

### Phase 2: AgentBuilder.publishes() Enhancement

**Goal**: Modify `.publishes()` to support multiple calls (creating groups) and new sugar parameters.

- [ ] **Prime Context**: Understand current publishes() implementation
    - [ ] Read `src/flock/agent.py` - AgentBuilder.publishes() `[ref: agent.py; lines: 646-699]`
    - [ ] Read `docs/internal/improved-publishes/design.md` - API design `[ref: design.md; lines: 119-137]`

- [ ] **Write Tests**: Test enhanced .publishes() API `[activity: test-writing]`
    - [ ] Test single `.publishes(A, B, C)` creates ONE OutputGroup with 3 outputs
    - [ ] Test multiple `.publishes(A).publishes(B)` creates TWO OutputGroups (1 output each)
    - [ ] Test `.publishes(A, A, A)` counts duplicates → 1 group, 3 A's
    - [ ] Test `.publishes(A, fan_out=3)` creates 1 group with 3 A's (sugar syntax)
    - [ ] Test `.publishes(A, where=lambda x: x.valid)` stores filter predicate
    - [ ] Test `.publishes(A, visibility=lambda x: "public" if x.important else "private")` stores dynamic visibility
    - [ ] Test `.publishes(A, validate=lambda x: x.score > 0)` stores validation
    - [ ] Test `.publishes(A, description="Special instructions")` stores group description
    - [ ] Test combining parameters: `.publishes(A, fan_out=3, where=..., validate=...)`
    - [ ] Test that `fan_out=0` raises ValueError
    - [ ] Test backwards compatibility: existing `.publishes(A)` still works

- [ ] **Implement**: Enhanced AgentBuilder.publishes() method `[ref: architecture-changes.md; lines: 150-200]` `[activity: api-development]`
    - [ ] Change `Agent` class: replace `outputs: list[AgentOutput]` with `output_groups: list[OutputGroup]`
    - [ ] Update `AgentBuilder.publishes()` signature:
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
    - [ ] Implement duplicate counting when no `fan_out` provided (use `Counter`)
    - [ ] Apply `fan_out` to ALL types when specified
    - [ ] Create `OutputGroup` from outputs and append to `agent.output_groups`
    - [ ] Store predicates and descriptions in each `AgentOutput`
    - [ ] Validate `fan_out >= 1` if provided
    - [ ] Return `PublishBuilder` for chaining

- [ ] **Validate**: API correctness and backwards compatibility
    - [ ] Run tests: `pytest tests/test_agent_builder.py::test_publishes* -v` `[activity: run-tests]`
    - [ ] Verify backwards compatibility: existing code doesn't break `[activity: business-acceptance]`
    - [ ] Review: API is intuitive and consistent with `.consumes()` `[activity: review-code]`

### Phase 3: Multiple Engine Calls in Agent.execute()

**Goal**: Modify agent execution to call the engine once per OutputGroup instead of once total.

- [ ] **Prime Context**: Understand current execution flow
    - [ ] Read `src/flock/agent.py` - Agent.execute() and _run_engines() `[ref: agent.py; lines: 92-310]`
    - [ ] Read `docs/internal/improved-publishes/architecture-changes.md` - Execution changes `[ref: architecture-changes.md; lines: 240-300]`

- [ ] **Write Tests**: Test multiple engine call execution `[activity: test-writing]`
    - [ ] Test agent with `.publishes(A).publishes(B).publishes(C)` calls engine 3 times
    - [ ] Test agent with `.publishes(A, B, C)` calls engine 1 time
    - [ ] Test agent with `.publishes(A, fan_out=3)` calls engine 1 time, generates 3 artifacts
    - [ ] Test that each engine call receives group-specific context
    - [ ] Test that artifacts from all groups are collected
    - [ ] Test that engine calls are sequential (not parallel initially)
    - [ ] Test error handling: if one group fails, others don't execute
    - [ ] Mock engine to count calls and verify behavior

- [ ] **Implement**: Multiple engine calls per execution `[ref: architecture-changes.md; lines: 240-280]` `[activity: performance-optimization]`
    - [ ] Modify `Agent.execute()`:
        ```python
        all_outputs = []
        for group_idx, output_group in enumerate(self.output_groups):
            group_ctx = self._prepare_group_context(ctx, group_idx, output_group)
            result = await self._run_engines(group_ctx, eval_inputs)
            group_outputs = await self._make_outputs_for_group(group_ctx, result, output_group)
            all_outputs.extend(group_outputs)
        return all_outputs
        ```
    - [ ] Implement `_prepare_group_context()`:
        - Clone context for this group
        - Add group-specific outputs to context
        - Generate group-specific system prompt instructions
    - [ ] Implement `_make_outputs_for_group()`:
        - Extract artifacts matching THIS group's output types only
        - Apply `where` filtering if specified
        - Apply `validate` checks if specified
        - Apply visibility (static or dynamic callable)
        - Verify count matches expected (if fan_out specified)
    - [ ] Update `_build_group_prompt()` helper to generate LLM instructions for this group

- [ ] **Validate**: Execution correctness and performance
    - [ ] Run tests: `pytest tests/test_agent.py::test_multiple_engine_calls* -v` `[activity: run-tests]`
    - [ ] Test integration: End-to-end with real LLM (may skip for speed) `[activity: business-acceptance]`
    - [ ] Review: Error handling is robust `[activity: review-code]`
    - [ ] Performance: Multiple groups don't cause excessive overhead `[activity: performance-testing]`

### Phase 4: LLM Prompt Engineering

**Goal**: Generate appropriate system prompts for each OutputGroup to guide LLM artifact generation.

- [ ] **Prime Context**: Understand prompt generation
    - [ ] Read `src/flock/engines/` - How DSPyEngine generates prompts
    - [ ] Read `docs/internal/improved-publishes/implementation-guide.md` - Prompt guidance `[ref: implementation-guide.md; lines: 250-280]`

- [ ] **Write Tests**: Test prompt generation for groups `[activity: test-writing]`
    - [ ] Test prompt for single output: "Generate 1 Task artifact"
    - [ ] Test prompt for fan_out: "Generate 3 Task artifacts using EvalResult.from_objects()"
    - [ ] Test prompt for multiple types: "Generate TaskA, TaskB, TaskC"
    - [ ] Test prompt includes group description if provided
    - [ ] Test prompt includes validation requirements if specified
    - [ ] Verify prompt is clear and actionable

- [ ] **Implement**: Group-specific prompt generation `[ref: architecture-changes.md; lines: 310-340]` `[activity: component-development]`
    - [ ] Implement `_build_group_prompt()` method:
        ```python
        def _build_group_prompt(self, output_group: OutputGroup) -> str:
            prompt = "You must generate the following artifacts:\n\n"

            # Count outputs by type
            type_counts = Counter(o.spec.type_name for o in output_group.outputs)
            for type_name, count in type_counts.items():
                if count > 1:
                    prompt += f"- {count}x {type_name}\n"
                else:
                    prompt += f"- {type_name}\n"

            # Add usage instructions for multiple artifacts
            if len(output_group.outputs) > 1:
                prompt += "\nUse EvalResult.from_objects() to return all artifacts.\n"

            # Add group-specific description if provided
            if output_group.group_description:
                prompt += f"\nSpecial instructions: {output_group.group_description}\n"

            # Add validation requirements if any
            for output in output_group.outputs:
                if output.validate_predicate:
                    prompt += f"\nValidate {output.spec.type_name} artifacts before returning.\n"

            return prompt
        ```
    - [ ] Integrate prompt into `_prepare_group_context()` to modify engine instructions

- [ ] **Validate**: Prompt quality and LLM behavior
    - [ ] Run tests: `pytest tests/test_prompt_generation.py -v` `[activity: run-tests]`
    - [ ] Manual test: Verify LLM generates correct count `[activity: business-acceptance]`
    - [ ] Review: Prompts are clear and unambiguous `[activity: review-code]`

### Phase 5: Filtering, Validation, and Visibility

**Goal**: Implement `where`, `validate`, and dynamic `visibility` processing in `_make_outputs_for_group()`.

- [ ] **Prime Context**: Review filtering and validation requirements
    - [ ] Read `docs/internal/improved-publishes/additional_ideas.md` - Filtering ideas `[ref: additional_ideas.md; lines: 10-80]`
    - [ ] Read `docs/internal/improved-publishes/design.md` - Validation design `[ref: design.md; lines: 450-520]`

- [ ] **Write Tests**: Test filtering, validation, and visibility `[activity: test-writing]`
    - [ ] Test `where` filters out artifacts: fan_out=10, where filters to 3, only 3 published
    - [ ] Test `validate` rejects invalid artifacts: raise ValueError with clear message
    - [ ] Test `validate` with list of tuples: multiple checks with custom error messages
    - [ ] Test dynamic `visibility`: callable determines visibility per artifact
    - [ ] Test static `visibility`: all artifacts get same visibility
    - [ ] Test combining where + validate: both applied in order
    - [ ] Test error messages are helpful (include which check failed)

- [ ] **Implement**: Filtering, validation, visibility in _make_outputs_for_group() `[activity: component-development]`
    - [ ] In `_make_outputs_for_group()`, after collecting artifacts from engine result:
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

- [ ] **Validate**: Feature correctness and error handling
    - [ ] Run tests: `pytest tests/test_filtering_validation.py -v` `[activity: run-tests]`
    - [ ] Test error messages: Clear and actionable `[activity: review-code]`
    - [ ] Integration test: Real agent with filtering `[activity: business-acceptance]`

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
✅ **Sugar Parameters**: `fan_out`, `where`, `visibility`, `validate`, `description` all work
✅ **TDD**: Tests written first, all passing
✅ **Backwards Compatible**: Existing code works unchanged
✅ **Documentation**: Complete with examples
✅ **Performance**: No significant overhead from multiple groups
✅ **Error Messages**: Clear, actionable, helpful

## Notes

- **TDD Emphasis**: EVERY phase starts with writing tests. No implementation without tests first!
- **Parallel Opportunity**: Phases 5-6 (filtering/validation + documentation) could be done in parallel after Phase 4 completes
- **Cost Consideration**: Document that multiple `.publishes()` calls = multiple LLM API calls = higher cost
- **Future Enhancement**: After this ships, consider adding `parallel=True` option to execute groups concurrently
