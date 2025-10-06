# Project Configuration Analysis

## Overview

Flock-Flow is a Python-based AI agent framework that uses UV for dependency management and follows modern Python packaging standards. This document provides a comprehensive analysis of the project's technical setup, dependencies, tooling, and organizational structure for agent understanding.

## Project Structure

```
flock-flow/
├── pyproject.toml          # Main project configuration
├── uv.lock                 # UV dependency lockfile
├── src/flock/         # Main source code
├── examples/               # Example implementations
│   ├── features/          # Feature validation examples
│   └── showcase/          # Demonstration examples
├── tests/                 # Test suite
├── docs/                  # Documentation
├── scripts/               # Utility scripts
└── README.md              # Project documentation
```

## Core Dependencies

### Production Dependencies

The project requires **Python 3.10+** and uses these key dependencies:

**AI/LLM Integration:**
- `dspy==3.0.0` - DSPy framework for prompt programming
- `litellm==1.75.3` - LLM API abstraction layer

**Web Framework & API:**
- `fastapi>=0.117.1` - Modern web framework
- `uvicorn>=0.37.0` - ASGI server
- `httpx>=0.28.1` - Async HTTP client
- `websockets>=15.0.1` - WebSocket support

**Data & Validation:**
- `pydantic[email]>=2.11.9` - Data validation and settings
- `toml>=0.10.2` - TOML file parsing

**CLI & UX:**
- `typer>=0.19.2` - Modern CLI framework
- `rich>=14.1.0` - Rich text and beautiful formatting
- `devtools>=0.12.2` - Development tools for debugging

**Observability & Logging:**
- `opentelemetry-api>=1.30.0` - OpenTelemetry API
- `opentelemetry-exporter-jaeger>=1.21.0` - Jaeger exporter
- `opentelemetry-exporter-jaeger-proto-grpc>=1.21.0` - Jaeger gRPC exporter
- `opentelemetry-exporter-otlp>=1.30.0` - OTLP exporter
- `opentelemetry-instrumentation-logging>=0.51b0` - Logging instrumentation
- `opentelemetry-sdk>=1.30.0` - OpenTelemetry SDK
- `loguru>=0.7.3` - Structured logging

**Protocol Integration:**
- `mcp>=1.7.1` - Model Context Protocol support

**Build & Task Management:**
- `poethepoet>=0.30.0` - Task runner

### Development Dependencies

The project uses UV dependency groups for development tools:

**Testing:**
- `pytest>=8.3.3` - Testing framework
- `pytest-clarity>=1.0.1` - Enhanced test output
- `pytest-cov>=6.0.0` - Coverage reporting
- `pytest-sugar>=1.0.0` - Better test UX
- `pytest-asyncio>=0.24.0` - Async test support
- `pytest-mock>=3.14.0` - Mocking support
- `respx>=0.22.0` - HTTP mocking

**Code Quality:**
- `ruff>=0.7.2` - Linting and formatting
- `mypy>=1.15.0` - Type checking

**Documentation:**
- `mkdocs>=1.6.1` - Documentation generator
- `mkdocs-material>=9.6.3` - Material theme
- `mkdocstrings[python]>=0.28.0` - Python docstring integration

## Build System

**Build Backend:** `hatchling`
- Configuration: `[build-system]` section in pyproject.toml
- Package location: `src/flock/`

**Entry Point:** `flock-flow = "flock:main"`
- Command-line interface accessible via `flock-flow` command

## Development Tools Configuration

### Poe the Poet Tasks

The project uses Poe for task automation with these key tasks:

**Installation & Setup:**
- `install` - Complete installation workflow
- `build` - Sync dependencies, build, and install
- `_sync` - UV sync with all groups and extras
- `_build` - UV build
- `_install` - UV install in editable mode

**Code Quality:**
- `lint` - Run ruff linting on source and tests
- `format` - Run ruff formatting on source and tests

**Testing:**
- `test` - Basic test run
- `test-cov` - Tests with coverage reporting (HTML and terminal)
- `test-cov-fail` - Tests with coverage requirement (80% minimum)
- `test-critical` - Critical path tests with 100% coverage requirement
- `test-watch` - Watch mode for continuous testing
- `test-determinism` - Run tests 10 times to ensure deterministic behavior

**Documentation:**
- `docs` - Build and serve documentation locally

**Utilities:**
- `clean` - Clean build artifacts, cache, and temporary files

### Testing Configuration

**Pytest Settings:**
- Async mode: `auto`
- Test paths: `tests/`
- Coverage source: `src/flock`
- Coverage exclusions: tests, examples, themes, pycache
- Branch coverage: enabled
- Coverage precision: 2 decimal places
- Missing coverage lines: shown

**Coverage Requirements:**
- Overall: 80% minimum
- Critical paths: 100% (orchestrator, subscription, visibility, agent modules)

## Example Organization

The project maintains two distinct example categories:

### Features Examples (`examples/features/`)

**Purpose:** In-depth feature validation with explicit assertions
- Validate specific behaviors comprehensively
- Include explicit assertions to catch bugs
- Test edge cases and error handling
- Serve as executable documentation
- Prevent regressions

**Examples:**
- `feedback_prevention.py` - Agent self-trigger prevention and circuit breakers
- `subscription_predicates.py` - Subscription filtering mechanisms
- `visibility/public_visibility.py` - Visibility control examples

### Showcase Examples (`examples/showcase/`)

**Purpose:** Engaging demonstrations for workshops and demos
- Demonstrate real-world use cases
- Tell clear stories with narrative flow
- Provide visual output and progress indicators
- Minimize technical complexity
- Create "wow moments" for audiences

**Examples:**
- `01_hello_flock.py` - Movie creation pipeline demonstration
- `02_blog_review.py` - Iterative agent improvement cycles
- `03_mcp_tools.py` - MCP server integration
- `04_dashboard.py` - Real-time dashboard visualization
- `04b_dashboard_edge_cases.py` - Dashboard edge cases

## Key Technical Characteristics

### Dependency Management
- **UV** as primary dependency manager (version 0.8.22)
- **Lockfile-based** dependency resolution for reproducibility
- **Dependency groups** for development tools management
- **Python 3.10+** requirement for modern language features

### Code Quality Standards
- **Ruff** for linting and formatting (unified toolchain)
- **MyPy** for static type checking
- **Pytest** with comprehensive coverage requirements
- **Deterministic testing** (10-run validation)

### Observability Integration
- **OpenTelemetry** for distributed tracing
- **Jaeger** export for trace visualization
- **Structured logging** with Loguru
- **MCP** protocol support for tool integration

### Web & API Infrastructure
- **FastAPI** for REST APIs
- **WebSocket** support for real-time features
- **Dashboard** integration for visual monitoring
- **Async/await** patterns throughout

## Development Workflow

1. **Setup:** `poe install` (handles UV sync, build, and install)
2. **Development:** Make changes to source code
3. **Quality Check:** `poe lint` and `poe format`
4. **Testing:** `poe test-cov` for coverage-aware testing
5. **Documentation:** `poe docs` for local documentation server

## Compatibility Requirements

### Python Version Support
- **Minimum:** Python 3.10
- **Recommended:** Python 3.12+
- **Tested:** Multiple Python versions via UV resolution markers

### External Dependencies
- **LLM Providers:** LiteLLM supports multiple providers (OpenAI, Anthropic, etc.)
- **MCP Servers:** Compatible with MCP protocol 1.7.1+
- **Observability:** Jaeger and OTLP endpoint support required

## Agent Development Guidelines

When working with this project, agents should:

1. **Use UV** for all dependency operations
2. **Follow Python 3.10+** syntax and features
3. **Maintain 80%+** test coverage on new code
4. **Use type hints** and MyPy compliance
5. **Include observability** in new components
6. **Document changes** in both code and examples
7. **Test against both** feature and showcase examples
8. **Consider dashboard integration** for user-facing features

## Package Management Notes

- **Editable installs** used for development (`-e .`)
- **All dependency groups** synced for comprehensive development
- **Clean targets** available for cache management
- **Build artifacts** excluded from version control
- **Lockfile updates** should be committed for reproducibility

This configuration ensures a robust, maintainable development environment with comprehensive testing, observability, and documentation capabilities suitable for production AI agent systems.
