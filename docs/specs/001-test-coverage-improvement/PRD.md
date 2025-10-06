# Product Requirements Document

## Validation Checklist
- [ ] Product Overview complete (vision, problem, value proposition)
- [ ] User Personas defined (at least primary persona)
- [ ] User Journey Maps documented (at least primary journey)
- [ ] Feature Requirements specified (must-have, should-have, could-have, won't-have)
- [ ] Detailed Feature Specifications for complex features
- [ ] Success Metrics defined with KPIs and tracking requirements
- [ ] Constraints and Assumptions documented
- [ ] Risks and Mitigations identified
- [ ] Open Questions captured
- [ ] Supporting Research completed (competitive analysis, user research, market data)
- [ ] No [NEEDS CLARIFICATION] markers remain
- [ ] No technical implementation details included

---

## Product Overview

### Vision
Achieve 80% test coverage with zero technical debt by eliminating API drift, removing code smells, and building a comprehensive test suite that ensures Flock Flow's reliability and maintainability.

### Problem Statement
The Flock Flow test suite is currently at 58% coverage (target: 80%), contains 52 instances of deprecated/legacy API usage creating test/implementation drift, and exhibits multiple code smells including real LLM connections in tests, broken mocks, and extensive code duplication. This creates three critical problems:

1. **Coverage Gap (22%)**: 35 source files lack dedicated tests, critical modules like `dspy_engine.py` (25% coverage) and `mcp/client.py` (19% coverage) are largely untested
2. **API Drift**: Tests use deprecated `publish_external()` and legacy `arun()` methods while implementation has moved to `publish()` and `invoke()`, including production code using deprecated APIs
3. **Quality Issues**: Tests contain real LLM model strings, broken mocks that always pass, 39 duplicate setup patterns, and unused fixtures

The consequences: CI/CD pipeline fails at 80% coverage threshold, tests don't validate current API behavior, potential production bugs in untested critical paths, and slow/flaky tests from improper mocking.

### Value Proposition
A robust test suite that:
- **Meets CI/CD Requirements**: Achieves 80% coverage to pass GitHub pipeline checks
- **Validates Current Behavior**: Tests use current API (`publish()`, `invoke()`) matching production code
- **Fast & Reliable**: Proper mocking eliminates slow LLM calls and flaky test failures
- **Maintainable**: Consolidated fixtures and zero duplication reduce maintenance burden
- **Production-Ready**: Comprehensive coverage of critical paths ensures reliability

## User Personas

### Primary Persona: Core Framework Developer
- **Demographics:** Senior Python developer, 5+ years experience, deep expertise in async patterns and testing frameworks
- **Goals:** Maintain high code quality, ensure framework reliability, pass CI/CD checks, prevent regressions in critical paths
- **Pain Points:**
  - CI/CD pipeline failing due to coverage threshold
  - Tests don't catch bugs because they test deprecated APIs
  - Slow test suite due to improper mocking
  - Difficulty maintaining duplicate test code across files

### Secondary Personas: Contributing Developer
- **Demographics:** Mid-level developer, 2-4 years experience, contributing to open source
- **Goals:** Add features without breaking existing functionality, follow established patterns, get PRs merged quickly
- **Pain Points:**
  - Unclear which API methods to use in tests (deprecated vs current)
  - Pre-commit hooks fail due to coverage drops
  - Difficult to write tests when fixtures are inconsistent

## User Journey Maps

### Primary User Journey: Test Suite Improvement
1. **Awareness:** Developer runs `poe test-cov` and sees 58% coverage failing GitHub pipeline requirements
2. **Consideration:** Reviews test-improvement-roadmap.md analysis showing 22% gap, 52 drift issues, multiple code smells
3. **Adoption:** Decides to follow phased approach: Foundation Repair → Critical Coverage → Dashboard Polish
4. **Usage:**
   - Phase 1: Fixes production code drift, consolidates fixtures, migrates deprecated API usage
   - Phase 2: Creates test files for dspy_engine, mcp_client, telemetry, mcp_manager, mcp_config
   - Phase 3: Expands dashboard service tests, adds WebSocket edge cases
5. **Retention:** CI/CD passes, tests are fast and reliable, new features confidently tested using established patterns

## Feature Requirements

**Reference:** Detailed analysis in `docs/domain/test-improvement-roadmap.md`

### Must Have Features

#### Feature 1: API Drift Elimination
- **User Story:** As a developer, I want all tests to use current API methods (`publish()`, `invoke()`) so that tests validate actual production behavior
- **Acceptance Criteria:**
  - [ ] Zero instances of deprecated `publish_external()` in tests (currently 21)
  - [ ] Zero instances of legacy `arun()` in tests (currently 29)
  - [ ] Zero instances of internal `direct_invoke()` in tests (currently 4)
  - [ ] Production code `service.py:37` uses current `publish()` API
  - [ ] All tests pass after migration

#### Feature 2: Test Infrastructure Quality
- **User Story:** As a developer, I want consolidated fixtures and proper mocking so that tests are fast, reliable, and maintainable
- **Acceptance Criteria:**
  - [ ] All orchestrator fixtures consolidated in `conftest.py` (remove 7 duplicates)
  - [ ] Collector fixture added to `conftest.py` (eliminate 12 duplicates)
  - [ ] Zero LLM model strings in test files
  - [ ] `mock_llm` fixture either used or removed
  - [ ] Broken mock test in `test_engines.py` fixed or removed
  - [ ] Zero inline `Flock()` instantiations (replace 39 with fixture usage)

#### Feature 3: Critical Module Test Coverage
- **User Story:** As a developer, I want comprehensive tests for critical modules so that core framework functionality is validated
- **Acceptance Criteria:**
  - [ ] `tests/test_dspy_engine.py` created with 80%+ coverage (currently 25.43%)
  - [ ] `tests/test_mcp_client.py` created with 80%+ coverage (currently 18.88%)
  - [ ] `tests/test_telemetry.py` created with 80%+ coverage (currently 0%)
  - [ ] `tests/test_mcp_manager.py` created with 80%+ coverage (currently 21.15%)
  - [ ] `tests/test_mcp_config.py` created with 80%+ coverage (currently 39.06%)

#### Feature 4: 80% Overall Coverage Achievement
- **User Story:** As a developer, I want to achieve 80% test coverage so that CI/CD pipeline passes and framework reliability is ensured
- **Acceptance Criteria:**
  - [ ] Overall test coverage ≥ 80% (currently 56.81%)
  - [ ] `poe test-cov` command passes
  - [ ] GitHub pipeline coverage check passes
  - [ ] No coverage regressions in future PRs

### Should Have Features

#### Feature 5: Dashboard Service Test Expansion
- **User Story:** As a developer, I want comprehensive dashboard API tests so that the real-time dashboard is reliable
- **Acceptance Criteria:**
  - [ ] `/api/artifact-types` endpoint tested
  - [ ] `/api/agents` endpoint tested
  - [ ] `/api/control/publish` endpoint tested with validation
  - [ ] `/api/control/invoke` endpoint tested with validation
  - [ ] Theme endpoints tested
  - [ ] `dashboard/service.py` coverage ≥ 80% (currently 39.29%)

#### Feature 6: WebSocket Edge Case Coverage
- **User Story:** As a developer, I want WebSocket edge case tests so that real-time features are robust
- **Acceptance Criteria:**
  - [ ] Connection error handling tested
  - [ ] Heartbeat timeout tested
  - [ ] Concurrent connections tested
  - [ ] Message ordering tested
  - [ ] `dashboard/websocket.py` coverage ≥ 80% (currently 67.19%)

### Could Have Features

- Utility component tests (`utilities.py` from 61.94% to 80%+)
- CLI helper tests (`cli_helper.py` from 65.62% to 80%+)
- Runtime tests (`runtime.py` from 67.27% to 80%+)

### Won't Have (This Phase)

- Frontend test coverage improvements (separate initiative)
- E2E test expansion beyond current scope
- Performance test suite creation
- Mutation testing implementation
- Test automation for manual QA scenarios

## Detailed Feature Specifications

### Feature: Critical Module Test Coverage (Feature 3)
**Description:** Create comprehensive test files for the five most impactful untested modules to achieve maximum coverage gain with minimum effort. These modules represent the core engine (DSPy), external protocol support (MCP), and observability infrastructure (telemetry).

**User Flow:**
1. Developer creates new test file (e.g., `tests/test_dspy_engine.py`)
2. Developer implements test scenarios covering uncovered line ranges
3. Developer runs `poe test-cov` to validate coverage increase
4. System reports module coverage percentage
5. Developer iterates until module reaches 80%+ coverage

**Business Rules:**
- Rule 1: Each test file MUST use consolidated fixtures from `conftest.py`
- Rule 2: Each test MUST use current API methods (`publish()`, `invoke()`)
- Rule 3: All LLM calls MUST be mocked (no real API connections)
- Rule 4: Test scenarios MUST cover happy path, edge cases, and error handling
- Rule 5: Module coverage MUST reach 80%+ to be considered complete

**Edge Cases:**
- Scenario 1: DSPy streaming disabled in pytest → Expected: Tests verify auto-detection and handle both streaming modes
- Scenario 2: MCP client connection fails → Expected: Tests verify lazy connection and proper error handling
- Scenario 3: Telemetry config missing env vars → Expected: Tests verify sensible defaults and config validation
- Scenario 4: Mock fixture not applied correctly → Expected: Test fails fast with clear error message
- Scenario 5: Coverage report shows false positives → Expected: Manual review of uncovered critical paths

## Success Metrics

### Key Performance Indicators

- **Coverage Achievement:** ≥ 80% overall test coverage (from 56.81%)
- **Drift Elimination:** 0 instances of deprecated API usage (from 52)
- **Quality Improvement:** 0 code smells (LLM strings, broken mocks, duplicates)
- **CI/CD Success:** 100% GitHub pipeline pass rate on coverage checks
- **Test Execution Speed:** <2 minutes for full test suite (baseline measurement needed)
- **Test Reliability:** 0 flaky tests (tests that fail/pass intermittently)

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Coverage report generation | Overall %, per-module %, missing lines | Track progress toward 80% goal |
| Test suite execution | Duration, pass/fail count, flaky tests | Monitor test performance and reliability |
| API usage scan | Count of deprecated methods | Validate drift elimination |
| CI/CD pipeline runs | Coverage check pass/fail | Validate production readiness |
| Code smell detection | LLM strings, duplicates, broken mocks | Track quality improvements |

## Constraints and Assumptions

### Constraints
- **Timeline:** 4 weeks (82-116 hours estimated effort)
- **Resources:** Single developer or small team following phased approach
- **Technical:** Must maintain backward compatibility during API migration phase
- **CI/CD:** Cannot merge PRs that drop coverage below 80% after implementation
- **Dependencies:** Existing test framework (pytest), mocking library (pytest-mock), coverage tooling

### Assumptions
- **About Developers:** Have Python testing experience, understand async patterns, familiar with pytest
- **About Codebase:** Current tests are functionally correct despite using deprecated APIs
- **About Infrastructure:** Test environment properly mocks external services, no actual LLM API keys needed in CI/CD
- **About Timing:** All three phases can be executed sequentially without major codebase changes interfering

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| API migration breaks existing tests | High | Medium | Phase 1 migrates incrementally; run full test suite after each file |
| Coverage improvements introduce new bugs | High | Low | Focus on mocking and isolation; validate with existing E2E tests |
| Timeline overrun (Phase 2 complexity) | Medium | Medium | Prioritize highest-impact modules first; Phase 3 is optional for 80% |
| Deprecated APIs removed before migration complete | High | Low | Check framework roadmap; complete Phase 1 before v2.0 release |
| Mock fixtures don't match real behavior | Medium | Medium | Validate mock contracts against actual implementations |
| Effort estimates too optimistic | Medium | High | Track actual hours per module; adjust plan after Phase 1 baseline |

## Open Questions

- [ ] Should `mock_llm` fixture be auto-use or explicit parameter?
- [ ] What is acceptable test execution time threshold?
- [ ] Should we measure test flakiness before/after improvements?
- [ ] Are there any planned framework changes that would conflict with migration?
- [ ] Should we create test coverage dashboard/monitoring?

## Supporting Research

### Competitive Analysis

**Reference:** Complete analysis in `docs/domain/test-improvement-roadmap.md`

**Industry Standards:**
- Most Python frameworks target 80-90% coverage minimum
- Django: 94%+ coverage, strict coverage requirements in CI/CD
- FastAPI: 100% coverage goal, extensive test suite
- Pytest itself: 90%+ coverage with comprehensive integration tests

**Best Practices Observed:**
- Consolidated fixtures in conftest.py (industry standard)
- Proper mocking of external dependencies (universal requirement)
- API versioning with deprecation warnings (learned from analysis)
- Phased migration approach (reduce risk)

### User Research

**Analysis Findings (October 5, 2025):**
- **Coverage Gap Analysis:** Identified 35 untested source files, 23 modules below 80%
- **Drift Analysis:** Found 52 instances of deprecated/legacy API usage across 6 test files
- **Code Smell Analysis:** Detected real LLM connections, broken mocks, 39 duplicate setups

**Key Insights:**
- Tests were written for earlier API version (drift occurred during evolution)
- No systematic fixture strategy led to duplication
- Missing LLM mocking strategy caused potential slow/flaky tests

### Market Data

**Project-Specific Data:**
- Current: 56.81% coverage (4,137 statements, 1,587 missed)
- Target: 80% coverage requirement from GitHub pipeline
- Gap: 22% coverage increase needed
- Impact: CI/CD currently failing, blocking releases
