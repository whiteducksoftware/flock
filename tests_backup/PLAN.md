Okay, let's create a comprehensive implementation plan for building out the test suite for the Flock framework. This plan aims for broad coverage, including unit, integration, and end-to-end tests, addressing the modular nature of the framework.

**Goal:** Establish a robust, maintainable, and comprehensive test suite for the Flock framework to ensure correctness, reliability, and facilitate future development.

**Guiding Principles:**

1.  **Isolation:** Unit tests should test components in isolation, mocking dependencies.
2.  **Interaction:** Integration tests should verify the collaboration between components.
3.  **Realism:** E2E tests should simulate user workflows, potentially using mocked or real (optional) external services like LLMs and Temporal.
4.  **Maintainability:** Tests should be clear, well-organized, and easy to update as the framework evolves.
5.  **Automation:** Tests should be runnable automatically, ideally within a CI/CD pipeline.
6.  **Coverage:** Aim for high code coverage, focusing on critical paths and complex logic.

**Tools & Frameworks:**

*   **Testing Framework:** `pytest` (already in `pyproject.toml`)
*   **Async Testing:** `pytest-asyncio` (already in `pyproject.toml`)
*   **Mocking:** `unittest.mock` (built-in), `pytest-mock` (pytest fixture)
*   **API Testing:** `httpx` (for testing `FlockAPI`)
*   **CLI Testing:** `Typer`'s `CliRunner` or similar.
*   **Coverage:** `pytest-cov` (already in `pyproject.toml`)
*   **(Optional) Property-Based Testing:** `Hypothesis`
*   **(Optional) Test Data Generation:** `Faker`

**Proposed Test Directory Structure:**

```
tests/
├── unit/          # Unit tests for individual components
│   ├── core/
│   ├── modules/
│   ├── evaluators/
│   ├── routers/
│   ├── utils/
│   └── ...
├── integration/   # Tests for interactions between components
│   ├── core/
│   ├── modules/
│   ├── temporal/
│   └── ...
├── e2e/           # End-to-end workflow tests
│   ├── local/
│   └── temporal/
├── cli/           # Tests for the command-line interface
├── api/           # Tests for the REST API server
└── fixtures/      # Reusable test data and fixtures
    ├── data/
    └── __init__.py
```

---

**Implementation Plan Phases:**

**Phase 0: Setup & Foundations (1 Week)**

*   **Objective:** Establish the testing environment, conventions, and basic tooling.
*   **Tasks:**
    *   Confirm `pytest` and necessary plugins (`pytest-asyncio`, `pytest-cov`, `pytest-mock`) are correctly configured.
    *   Define testing conventions (naming, structure, fixture usage) in `CONTRIBUTING.md` or a dedicated testing guide.
    *   Set up basic `conftest.py` for common fixtures (e.g., event loop policies, basic `Flock` instances).
    *   Implement a basic mocking strategy for LLM calls (e.g., a fixture that returns predictable responses).
    *   Set up initial code coverage reporting configuration.
    *   Define markers for different test types (e.g., `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.llm`, `@pytest.mark.temporal`).
*   **Success Criteria:** Basic `pytest` runs succeed, coverage reporting is set up, simple mock LLM fixture exists.

**Phase 1: Core Component Unit Tests (2-3 Weeks)**

*   **Objective:** Ensure the fundamental building blocks work correctly in isolation.
*   **Key Components:** `FlockAgent`, `FlockContext`, `Registry`, `Flock` (initialization, agent/tool registration).
*   **Types of Tests:** Unit tests.
*   **Specific Tasks:**
    *   **FlockAgent:**
        *   Initialization with various parameters.
        *   `to_dict`/`from_dict` serialization/deserialization (including callables with `cloudpickle`). Test `SecureSerializer` usage if applicable.
        *   Adding/removing/getting modules.
        *   Lifecycle hook invocation (mock callbacks/modules to verify they are called).
        *   Basic `run_async` logic (mocking `evaluate`, `initialize`, `terminate`, `on_error`).
        *   DSPy mixin methods (if still relevant) or replacement system methods.
        *   Type hint parsing (`_build_clean_signature`, `_parse_key_descriptions` if kept, or new parsing logic).
    *   **FlockContext:**
        *   `set_variable`/`get_variable`.
        *   `record` method and history management.
        *   Agent definition storage/retrieval.
        *   Serialization (`to_dict`/`from_dict`).
    *   **Registry:**
        *   Registering/getting agents and tools.
        *   Handling non-existent items.
    *   **Flock:**
        *   Initialization logic (debug vs. temporal flags, logging setup).
        *   `add_agent` logic (new vs. existing, model defaulting, tool registration).
        *   `add_tool` logic.
        *   `save_to_file`/`load_from_file`.
*   **Mocking:** Mock `evaluate` in `FlockAgent`, LLM calls, file I/O, Temporal client, `cloudpickle`.
*   **Success Criteria:** High unit test coverage for core classes, demonstrating correct isolated behavior.

**Phase 2: Module, Evaluator, Router Unit Tests (3-4 Weeks)**

*   **Objective:** Test the core logic of each pluggable component type and their specific implementations.
*   **Key Components:**
    *   Base classes: `FlockModule`, `FlockEvaluator`, `FlockRouter`.
    *   Modules: `MemoryModule`, `MetricsModule`, `OutputModule`, `ZepModule`, `CallbackModule`, `HierarchicalMemoryModule`.
    *   Evaluators: `DeclarativeEvaluator`, `NaturalLanguageEvaluator`, `MemoryEvaluator`, `ZepEvaluator`, `HierarchicalMemoryEvaluator`.
    *   Routers: `DefaultRouter`, `LLMRouter`, `AgentRouter`, `HandoffAgent`.
*   **Types of Tests:** Unit tests.
*   **Specific Tasks:**
    *   **Base Classes:** Test default behavior, configuration handling.
    *   **Modules:**
        *   Test each lifecycle hook implementation individually (mock agent/context).
        *   Test configuration parsing and application.
        *   **MemoryModule:** Test add/retrieve logic, concept graph updates, serialization, different splitting modes, memory mapping parsing (`MemoryMappingParser`). Test `FlockMemoryStore` separately (add/retrieve, scoring, decay, clustering, serialization).
        *   **MetricsModule:** Test metric recording, aggregation (if any), storage (mock file/prometheus), alerting conditions.
        *   **OutputModule:** Test formatting logic (tables, themes), file writing, custom formatters.
        *   **Zep/Azure Modules:** Test interaction logic by mocking the respective clients (`Zep`, `SearchClient`, etc.).
    *   **Evaluators:**
        *   Test the `evaluate` method logic for each type.
        *   **DeclarativeEvaluator:** Mock LLM calls, test prompt generation based on agent signatures, test result processing.
        *   **NaturalLanguageEvaluator:** Test prompt template rendering, LLM interaction.
        *   **Memory/Zep/Hierarchical Evaluators:** Mock underlying storage/client, test query/data handling logic.
    *   **Routers:**
        *   Test the `route` method for each type.
        *   **DefaultRouter:** Test static, callable, and `HandOffRequest` handoffs.
        *   **LLMRouter:** Mock LLM, test prompt creation, response parsing, scoring logic.
        *   **AgentRouter:** Mock `HandoffAgent.run_async`, test input preparation, decision handling, agent filtering.
        *   **HandoffAgent:** Test its specific `evaluate` logic (might need integration test if heavily reliant on LLM).
*   **Mocking:** Mock `FlockAgent`, `FlockContext`, LLM clients, external clients (Zep, Azure), file system, `datetime`, `time`, `cloudpickle`.
*   **Success Criteria:** Core logic of each module, evaluator, and router implementation is verified. Configuration options are tested.

**Phase 3: Utility and Supporting Component Tests (1-2 Weeks)**

*   **Objective:** Ensure helper functions, factories, and other supporting code work correctly.
*   **Key Components:** `FlockFactory`, `input_resolver.py`, `serialization.py`, `tools` (basic, Azure, GitHub), `logging.py`, `telemetry.py`, `cli_helper.py`.
*   **Types of Tests:** Unit tests.
*   **Specific Tasks:**
    *   **FlockFactory:** Test `create_default_agent` creates agents with expected modules and configurations.
    *   **Input Resolver:** Test `resolve_inputs`, `split_top_level`, `top_level_to_keys` with various spec strings and context states.
    *   **Serialization:** Test `Serializable` methods, `SecureSerializer` logic (safety checks, allow flags).
    *   **Tools:** Unit test individual tools, mocking external calls (`httpx`, `TavilyClient`, `DDGS`, GitHub API). Test argument handling and return values.
    *   **Logging/Telemetry:** Test logger initialization, context adaptation (local vs. workflow), formatter logic, telemetry setup, span processor logic.
*   **Mocking:** Mock external APIs, file system, `datetime`, `opentelemetry` components where necessary.
*   **Success Criteria:** Utility functions and supporting components are reliable.

**Phase 4: Integration Tests (3-4 Weeks)**

*   **Objective:** Verify that different components of Flock work together as expected.
*   **Key Interactions:**
    *   `Flock` + `FlockAgent` + `DeclarativeEvaluator` + `LLM (Mocked)`.
    *   `FlockAgent` + `MemoryModule` (add data in one step, retrieve in another).
    *   `FlockAgent` + `MetricsModule` (verify metrics are recorded).
    *   `FlockAgent` + `OutputModule` (verify output formatting).
    *   Agent Chaining (`DefaultRouter`): Agent A -> Agent B. Verify data flow.
    *   Agent Chaining (`LLMRouter`/`AgentRouter` Mocked): Agent A -> Router -> Agent B/C. Verify routing decision and data flow.
    *   `FlockAgent` + `Tools` (mock the tool's external effect, verify it's called).
    *   `FlockContext` updates across agent steps.
*   **Types of Tests:** Integration tests (`tests/integration/`).
*   **Mocking:** Mock LLMs, external APIs (Zep, Azure, GitHub), Temporal client. Focus on interaction points.
*   **Success Criteria:** Key component interactions function correctly, data flows as expected between agents and through modules.

**Phase 5: End-to-End Tests (3-4 Weeks)**

*   **Objective:** Validate complete user scenarios and workflows.
*   **Key Scenarios:**
    *   Simple single-agent execution (Local).
    *   Multi-agent chain execution (Local, using `DefaultRouter`).
    *   Dynamic routing workflow (Local, using mocked `LLMRouter`/`AgentRouter`).
    *   Workflow involving memory (write then read).
    *   Workflow involving tools (e.g., search then summarize).
    *   Repeat key scenarios using Temporal execution (requires Temporal test environment).
*   **Types of Tests:** E2E tests (`tests/e2e/`).
*   **Mocking/Environment:**
    *   **Local:** Mock external APIs. Use mocked or (selectively marked) real LLMs.
    *   **Temporal:** Requires a running Temporal test server (`temporalite`) or dedicated namespace. Mock external APIs/LLMs. Test workflow completion, activity execution, basic error handling/retries.
*   **Success Criteria:** Representative workflows complete successfully in both local and Temporal modes, producing expected final outputs.

**Phase 6: CLI & API Tests (1-2 Weeks)**

*   **Objective:** Ensure the command-line interface and REST API work correctly.
*   **Key Components:** `src/flock/cli/`, `FlockAPI`.
*   **Types of Tests:** CLI tests (`tests/cli/`), API tests (`tests/api/`).
*   **Specific Tasks:**
    *   **CLI:** Use `CliRunner` to invoke `flock` commands (`load_flock`, `theme_builder`, etc.). Test options, arguments, output, exit codes. Mock file system operations.
    *   **API:** Use `httpx.AsyncClient` to send requests to a test instance of the `FlockAPI` (`FastAPI`'s `TestClient`). Test endpoints (`/run/agent`, `/run/flock`, `/run/{run_id}`, `/agents`). Verify request/response schemas, status codes, sync/async behavior. Mock the underlying `Flock.run_async` calls.
*   **Mocking:** Mock `Flock` methods, file system, `questionary`.
*   **Success Criteria:** CLI commands and API endpoints function as documented.

**Phase 7: Continuous Improvement (Ongoing)**

*   **Objective:** Maintain and enhance the test suite.
*   **Tasks:**
    *   Integrate tests into a CI/CD pipeline (e.g., GitHub Actions).
    *   Monitor code coverage and add tests for uncovered areas.
    *   Add tests for new features and bug fixes.
    *   Refactor tests for clarity and maintainability.
    *   Periodically run tests against real LLMs/APIs (marked suite).
    *   Add performance/load tests (optional).
    *   Document the testing strategy and how to run tests.

---

**Handling Dependencies:**

*   **LLMs:** Primarily use mocks. Create a fixture `mock_llm` that can be configured to return specific responses based on the prompt or input. Mark tests requiring real LLMs with `@pytest.mark.llm`.
*   **Temporal:** For unit/integration, mock `temporalio.client.Client` and activity/workflow decorators. For E2E, use `temporalite` or a test namespace. Mark Temporal E2E tests with `@pytest.mark.temporal`.
*   **External APIs (Azure, GitHub, Zep):** Mock the respective client libraries (`azure-search-documents`, `httpx`, `zep-python`) or use `vcrpy`/`pytest-recording`. Mark integration tests needing real credentials with `@pytest.mark.integration`.

**Estimated Timeline:**

This is a significant effort. Assuming 1-2 developers dedicated to testing:

*   Phase 0: 1 week
*   Phase 1: 2-3 weeks
*   Phase 2: 3-4 weeks
*   Phase 3: 1-2 weeks
*   Phase 4: 3-4 weeks
*   Phase 5: 3-4 weeks
*   Phase 6: 1-2 weeks
*   **Total Estimated:** ~14-22 weeks

This timeline is rough and depends heavily on developer familiarity with the codebase and testing tools. It's an iterative process; some phases can overlap, and priorities might shift. The most crucial phases initially are 0, 1, 2, and 4 to build a solid foundation.