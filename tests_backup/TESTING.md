# Flock Testing Guide

This document outlines the structure and conventions for testing the Flock framework.

## Directory Structure

The `tests/` directory is organized as follows:
```

tests/
├── unit/ # Unit tests for individual components (isolated)
│ ├── core/
│ ├── modules/
│ ├── evaluators/
│ ├── routers/
│ └── ... # Subdirectories mirroring src/flock/
├── integration/ # Tests verifying interactions between components
│ ├── core/
│ ├── modules/
│ └── ...
├── e2e/ # End-to-end workflow tests (simulating user scenarios)
│ ├── local/ # E2E tests using the local executor
│ └── temporal/ # E2E tests using the Temporal executor
├── cli/ # Tests for the command-line interface
├── api/ # Tests for the REST API server
├── fixtures/ # Reusable test data and fixtures
│ ├── data/
│ └── init.py
├── conftest.py # Global pytest fixtures and hooks
└── pytest.ini # Pytest configuration (markers, coverage, etc.)
└── TESTING.md # This guide

```


## Running Tests

1.  **Install Development Dependencies:**
    Ensure you have installed the necessary development dependencies. If using `uv`, you can typically do this with:
    ```bash
    uv sync --all-groups --all-extras
    # or check pyproject.toml for the correct group name (e.g., dev, test)
    # uv sync --with dev
    ```
    Or with pip:
    ```bash
    pip install -e ".[dev]" # Adjust 'dev' if your group name differs
    ```

2.  **Run All Tests:**
    Navigate to the project root directory and run:
    ```bash
    pytest
    ```

3.  **Run Specific Test Types:**
    Use markers to run specific categories of tests:
    ```bash
    pytest -m unit
    pytest -m integration
    pytest -m e2e
    pytest -m local_e2e
    pytest -m temporal_e2e # Requires a running Temporal server/lite
    pytest -m llm        # Runs tests requiring real LLM calls (potentially slow/costly)
    pytest -m cli
    pytest -m api
    ```

4.  **Run Tests with Coverage:**
    ```bash
    pytest --cov=src/flock
    ```
    An HTML coverage report will be generated in the `htmlcov/` directory.

## Markers

We use the following `pytest` markers (defined in `pytest.ini`):

*   `@pytest.mark.unit`: Isolated tests for a single class or function.
*   `@pytest.mark.integration`: Tests involving interaction between multiple components (mocks may still be used for external services).
*   `@pytest.mark.e2e`: End-to-end tests simulating a full workflow.
*   `@pytest.mark.local_e2e`: E2E tests specifically for the local executor.
*   `@pytest.mark.temporal_e2e`: E2E tests specifically for the Temporal executor.
*   `@pytest.mark.llm`: Tests that require actual calls to an LLM service. Skipped by default unless explicitly run.
*   `@pytest.mark.temporal`: Tests that require a connection to a Temporal server/temporalite. Skipped by default unless explicitly run.
*   `@pytest.mark.cli`: Tests for the CLI (`flock` command).
*   `@pytest.mark.api`: Tests for the `FlockAPI` REST server.
*   `@pytest.mark.azure`: Tests requiring Azure credentials.
*   `@pytest.mark.github`: Tests requiring GitHub credentials.

## Mocking

*   **LLMs:** Most tests should use the `mock_llm` fixture defined in `conftest.py`, which patches `litellm.completion` and `litellm.acompletion`. Tests needing real LLM calls should be marked with `@pytest.mark.llm`.
*   **External Services (Temporal, Azure, GitHub, Zep):** Use `unittest.mock.patch` or `mocker` (from `pytest-mock`) to mock client libraries or specific API calls for unit and integration tests. E2E tests might require running instances (like `temporalite`) or specific markers (`@pytest.mark.temporal`, `@pytest.mark.azure`).
*   **File System:** Use `pyfakefs` fixture (install `pytest-pyfakefs`) or `unittest.mock.patch` for file operations.
*   **Time:** Use `freezegun` (install `freezegun`) or `unittest.mock.patch` for `datetime` and `time`.

## Conventions

*   Test filenames should start with `test_`.
*   Test function names should start with `test_`.
*   Use fixtures for setup and teardown where possible.
*   Keep unit tests focused and isolated.
*   Integration tests should clearly state which components are being tested together.
*   E2E tests should represent realistic user scenarios.
