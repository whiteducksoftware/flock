# Development Workflow Guide

This document outlines the development workflow, testing patterns, build processes, and development tooling used in the Flock-Flow project to help agents work effectively with the codebase.

## 🛠️ Development Environment

### Package Management

The project uses **UV** as the primary package manager for fast, reliable dependency management.

```bash
# Install dependencies (development + production)
poe install

# Manual sync with UV
uv sync --dev --all-groups --all-extras

# Install in development mode
uv pip install -e .
```

### Containerized Development

Development is containerized using VS Code DevContainers with Python 3.12 and Node.js 22:

```json
{
  "image": "ghcr.io/astral-sh/uv:python3.12-bookworm",
  "features": {
    "ghcr.io/devcontainers/features/node:1": {
      "version": "22"
    }
  }
}
```

### Environment Configuration

- Environment template: `.envtemplate`
- Required variables: `OPENAI_API_KEY`, `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION`
- Development environment file: `.env` (gitignored)

## 🏗️ Project Structure

```
flock-flow/
├── src/flock/           # Main source code
│   ├── agent.py             # Agent implementation
│   ├── orchestrator.py      # Core orchestration logic
│   ├── api/                 # REST API endpoints
│   ├── dashboard/           # Web dashboard
│   ├── engines/             # LLM engine implementations
│   ├── mcp/                 # MCP (Model Context Protocol) support
│   └── ...
├── tests/                   # Test suite
│   ├── contract/           # Contract tests (system behavior contracts)
│   ├── integration/        # Integration tests
│   ├── e2e/               # End-to-end tests
│   └── conftest.py        # Shared test fixtures
├── docs/                   # Documentation
├── frontend/              # React dashboard frontend
└── scripts/              # Utility scripts
```

## 🧪 Testing Strategy

### Test Categories

1. **Unit Tests**: Individual component testing
2. **Contract Tests**: System behavior contracts (`tests/contract/`)
3. **Integration Tests**: Component interaction testing (`tests/integration/`)
4. **End-to-End Tests**: Full workflow testing (`tests/e2e/`)

### Testing Configuration

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Quality Standards

- **Overall Coverage**: 80%+ minimum
- **Critical Path Coverage**: 100% (orchestrator, subscription, visibility, agent)
- **Test Determinism**: 10 consecutive runs must pass

### Test Execution

```bash
# Run all tests
poe test

# Run with coverage report
poe test-cov

# Run with coverage failure threshold
poe test-cov-fail

# Run critical path tests (100% coverage required)
poe test-critical

# Watch mode for development
poe test-watch

# Determinism test (10 consecutive runs)
poe test-determinism
```

### Test Fixtures

Key fixtures available in `conftest.py`:

- `orchestrator`: Clean orchestrator with in-memory store
- `sample_artifact`: Sample artifact for testing
- `sample_agent_identity`: Sample agent identity
- `mock_llm`: Mock LLM API calls
- `fixed_time`: Fixed time for deterministic tests
- `fixed_uuid`: Fixed UUID generation

## 🔧 Code Quality & Tooling

### Linting & Formatting

```bash
# Lint code
poe lint  # Equivalent to: ruff check src/flock/ tests/

# Format code
poe format  # Equivalent to: ruff format src/flock/ tests/
```

### Type Checking

```bash
# Run mypy type checker
uv run mypy src/flock/
```

### Code Style

- **Formatter**: Ruff (configured in pyproject.toml)
- **Linter**: Ruff with comprehensive rule set
- **Type Checker**: mypy
- **Auto-format on save**: Enabled in VS Code devcontainer

## 📦 Build Process

### Build Tasks

```bash
# Full build pipeline
poe build

# Individual steps:
uv build          # Build package
uv pip install -e .  # Install in development mode
```

### Distribution

- **Build Backend**: Hatchling
- **Package Format**: Wheel
- **Source Distribution**: Enabled

## 🎯 Development Guidelines for Agents

### 1. Code Organization

- Keep files under 500 lines
- Use modular design patterns
- Separate concerns clearly
- Maintain clean architecture

### 2. Testing Requirements

- **Test-First Development**: Write tests before implementation
- **Coverage Requirements**: Maintain 80%+ overall coverage
- **Critical Paths**: 100% coverage for core components
- **Deterministic Tests**: Use fixtures for consistent results

### 3. Development Workflow

1. **Setup**: Ensure environment is properly configured
2. **Analysis**: Understand existing patterns and contracts
3. **Implementation**: Follow established architectural patterns
4. **Testing**: Write comprehensive tests before code
5. **Quality**: Run linting and formatting
6. **Validation**: Ensure all tests pass

### 4. Environment Safety

- **Never hardcode secrets**: Use environment variables
- **Secure API Keys**: Store in `.env` file
- **Validate Input**: Always validate external inputs
- **Error Handling**: Implement proper error handling

### 5. Documentation

- **Docstrings**: Include comprehensive docstrings
- **Type Hints**: Use Python type hints consistently
- **Examples**: Provide usage examples in docstrings
- **Changelog**: Document significant changes

## 🚀 Available Development Commands

### Core Commands

```bash
# Environment setup
poe install          # Install all dependencies

# Development
poe build           # Build project
poe lint            # Lint code
poe format          # Format code

# Testing
poe test            # Run tests
poe test-cov        # Run with coverage
poe test-critical   # Run critical path tests

# Documentation
poe docs            # Serve documentation locally

# Cleanup
poe clean           # Clean build artifacts
```

### Manual UV Commands

```bash
# Dependency management
uv sync --dev --all-groups --all-extras
uv add <package>  # Add dependency
uv add --dev <package>  # Add dev dependency

# Execution
uv run pytest
uv run mypy
uv run ruff check
```

## 📊 Coverage Configuration

```toml
[tool.coverage.run]
source = ["src/flock"]
omit = [
    "tests/*",
    "examples/*",
    "*/themes/*",
    "*/__pycache__/*"
]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstract",
]
precision = 2
show_missing = true
```

## 🔍 Debugging & Development Tips

### 1. Test Debugging

```bash
# Run specific test file
uv run pytest tests/test_orchestrator.py -v

# Run with debugging
uv run pytest -s -vv tests/test_specific.py

# Run failing test only
uv run pytest --lf
```

### 2. Performance Profiling

```bash
# Profile test execution
uv run pytest --profile-svg

# Coverage with branch analysis
uv run pytest --cov=src/flock --cov-branch
```

### 3. Development Server

```bash
# Start development dashboard
cd frontend && npm start

# Start API server
uvicorn src.flock.api.main:app --reload
```

## 📋 Agent Development Checklist

Before submitting changes, ensure:

- [ ] All tests pass (`poe test`)
- [ ] Coverage requirements met (`poe test-cov-fail`)
- [ ] Code is properly formatted (`poe format`)
- [ ] Linting passes (`poe lint`)
- [ ] Type checking passes (`uv run mypy`)
- [ ] Documentation is updated
- [ ] Examples are tested
- [ ] No hardcoded secrets
- [ ] Error handling is implemented
- [ ] Logging is appropriate

## 🔄 Continuous Integration

The project uses automated quality gates:

- **Test Execution**: All tests must pass
- **Coverage Threshold**: 80%+ overall, 100% critical paths
- **Code Quality**: Linting and formatting checks
- **Type Safety**: mypy type checking
- **Build Verification**: Package builds successfully

## 📚 Additional Resources

- **Project README**: `/README.md` - Project overview and quick start
- **Agent Documentation**: `/AGENTS.md` - Agent-specific guidelines
- **Architecture Docs**: `/docs/architecture/` - System architecture
- **API Documentation**: Generated from docstrings
- **Examples**: `/examples/` - Usage examples

---

This workflow documentation ensures consistent development practices and helps agents understand the project's development processes, tooling, and quality standards.
