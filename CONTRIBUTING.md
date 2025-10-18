# Contributing to Flock

Welcome to Flock! We're excited to have you contribute to the future of AI agent orchestration. This guide will help you get set up and contributing quickly.

## 🎯 Quick Start

```bash
# 1. Fork and clone the repository
git clone https://github.com/yourusername/flock-flow.git
cd flock-flow

# 2. Install all dependencies
poe install

# 3. Install pre-commit hooks
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push

# 4. Verify setup
poe test
cd frontend && npm test

# You're ready to contribute! 🚀
```

## 📋 Prerequisites

### Required Software

- **Python 3.10+** - Modern Python with async features
- **UV Package Manager** - Fast, reliable dependency management (NOT pip!)
- **Node.js 22+** - For frontend development
- **Git** - Version control

### Recommended Tools

- **VS Code** - With Python and TypeScript extensions
- **DevContainer** - For consistent development environment
- **pre-commit** - Automated quality checks

## 🛠️ Development Environment Setup

### 1. Install UV Package Manager

```bash
# Install UV (NOT pip!)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

**⚠️ IMPORTANT**: Always use `uv add` instead of `pip install` to maintain lock file consistency.

### 2. Install Project Dependencies

```bash
# Full installation workflow (recommended)
poe install

# Or manually:
uv sync --dev --all-groups --all-extras  # Install Python deps
cd frontend && npm install                # Install frontend deps
```

### 3. Set Up Environment Variables

```bash
# Copy environment template
cp .envtemplate .env

# Edit .env and add your API keys
export OPENAI_API_KEY="sk-..."
export DEFAULT_MODEL="openai/gpt-4o-mini"
```

### 4. Install Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Or use UV
uv add --dev pre-commit

# Install git hooks
pre-commit install
pre-commit install --hook-type pre-push

# Verify installation
pre-commit run --all-files
```

## 🔄 Development Workflow

### Typical Contribution Flow

```bash
# 1. Create a feature branch
git checkout -b feature/your-feature-name

# 2. Make your changes
vim src/flock/your_file.py

# 3. Run tests locally
poe test

# 4. Lint and format
poe format
poe lint

# 5. Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: add your feature"

# If hooks auto-fix issues, re-commit
git add .
git commit -m "feat: add your feature"

# 6. Bump version if needed
poe version-check  # See what would be bumped
poe version-minor  # Bump version

# 7. Commit version bump
git add pyproject.toml src/flock/frontend/package.json
git commit -m "chore: bump version to 0.2.0"

# 8. Push (build checks run)
git push origin feature/your-feature-name

# 9. Create Pull Request
# Use GitHub UI or: gh pr create
```

### Pre-commit Hooks

Hooks run automatically on commit and push:

**Pre-commit (fast - runs on every commit)**:
- Ruff linting and formatting
- mypy type checking
- File validation (YAML, TOML, JSON)
- Security scans (secrets, vulnerabilities)
- Fast tests only

**Pre-push (comprehensive - runs on push)**:
- Frontend build check
- Backend build check
- Version bump validation (warning only)

**To skip hooks (emergency only)**:
```bash
git commit --no-verify -m "emergency fix"
```

**Note**: CI will still run all checks!

## 🧪 Testing Requirements

### Test Categories

1. **Unit Tests** - Individual component testing
2. **Contract Tests** - System behavior contracts
3. **Integration Tests** - Component interaction
4. **E2E Tests** - Full workflow validation
5. **Frontend Tests** - React component testing

### Running Tests

```bash
# Run all tests
poe test

# Run with coverage
poe test-cov

# Coverage with failure threshold (80%+)
poe test-cov-fail

# Critical path tests (100% coverage required)
poe test-critical

# Frontend tests
cd frontend && npm test

# E2E tests
poe test-e2e

# Determinism test (10 consecutive runs)
poe test-determinism
```

### Coverage Requirements

- **Overall**: 75%+ minimum (currently 77.65%)
- **Critical Paths**: 100% (orchestrator, subscription, visibility, agent)
- **Frontend**: 80%+ recommended

### Writing Tests

```python
# tests/test_your_feature.py
import pytest
from flock import Flock

@pytest.mark.asyncio
async def test_your_feature():
    """Test description following docstring conventions."""
    # Arrange
    orchestrator = Flock("openai/gpt-4o-mini")

    # Act
    result = await orchestrator.do_something()

    # Assert
    assert result is not None
```

**Best Practices:**
- Follow patterns in [`docs/patterns/error_handling.md`](docs/patterns/error_handling.md)
- Use async patterns from [`docs/patterns/async_patterns.md`](docs/patterns/async_patterns.md)
- Verify error messages with `pytest.raises()`
- Test edge cases and error conditions

## 📦 Versioning

Flock uses **smart versioning** that only bumps versions for components that actually changed.

### Quick Reference

```bash
# Check what would be bumped
poe version-check

# Bump versions
poe version-patch   # 0.1.18 → 0.1.19 (bug fixes)
poe version-minor   # 0.1.18 → 0.2.0 (new features)
poe version-major   # 0.1.18 → 1.0.0 (breaking changes)
```

### Smart Detection

- ✅ **Backend changes** (`src/`, `tests/`) → Bump `pyproject.toml`
- ✅ **Frontend changes** (`frontend/`) → Bump `package.json`
- ❌ **Docs changes** (`docs/`, `README.md`) → No version bump

### Semantic Versioning Guidelines

**Patch (0.1.18 → 0.1.19)**:
- Bug fixes
- Performance improvements
- Documentation updates (if code also changed)
- Internal refactoring

**Minor (0.1.18 → 0.2.0)**:
- New features (backward compatible)
- New API endpoints
- New components or modules
- Deprecations (with backward compatibility)

**Major (0.1.18 → 1.0.0)**:
- Breaking API changes
- Removed deprecated features
- Major architectural changes
- First stable release (0.x.x → 1.0.0)

See [`docs/VERSIONING.md`](docs/VERSIONING.md) for complete guide.

## 📝 Code Style & Patterns

### Python Best Practices

- **Formatter**: Ruff (auto-formats on commit)
- **Linter**: Ruff with comprehensive rules
- **Type Checker**: mypy
- **Error Handling**: Follow [`docs/patterns/error_handling.md`](docs/patterns/error_handling.md)
- **Async Patterns**: Follow [`docs/patterns/async_patterns.md`](docs/patterns/async_patterns.md)

```python
# ✅ Good: Type hints everywhere
async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
    """Execute the agent with given artifacts.

    Args:
        ctx: Execution context
        artifacts: Input artifacts

    Returns:
        List of output artifacts

    Raises:
        ValueError: If artifacts list is empty
    """
    if not artifacts:
        raise ValueError("Artifacts list cannot be empty")
    ...

# ✅ Good: Pydantic models with Field descriptions
@flock_type
class Movie(BaseModel):
    """Movie information."""

    title: str = Field(description="Movie title in CAPS")
    runtime: int = Field(ge=60, le=400, description="Runtime in minutes")

# ✅ Good: Error handling with context
try:
    result = await engine.evaluate(inputs)
except ValueError as e:
    logger.exception("Evaluation failed: agent=%s", agent.name)
    raise RuntimeError(f"Engine failed for {agent.name}") from e
```

### Error Handling Patterns

**See [`docs/patterns/error_handling.md`](docs/patterns/error_handling.md) for complete guide**

Key principles:
- ✅ Catch specific exceptions, not broad `Exception`
- ✅ Add context with `logger.exception()` and `from e`
- ✅ Use component error hooks for reusable error handling
- ❌ Never silent failures (empty `except` blocks)
- ❌ Never lose error context

### Async Patterns

**See [`docs/patterns/async_patterns.md`](docs/patterns/async_patterns.md) for complete guide**

Key principles:
- ✅ Use sequential operations when order matters
- ✅ Use `asyncio.gather()` for parallel independent operations
- ✅ Use `asyncio.TaskGroup` for automatic cancellation (Python 3.11+)
- ✅ Handle `asyncio.CancelledError` in background tasks
- ❌ Never block with synchronous operations in async functions
- ❌ Never create tasks without tracking them

### TypeScript/React

- **Type Safety**: Full TypeScript typing
- **Framework**: React 19 with hooks
- **State**: Zustand for global state
- **Testing**: Vitest + React Testing Library

```typescript
// ✅ Good: Type-safe components
interface DashboardLayoutProps {
  children: React.ReactNode;
}

const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  // Component implementation
};

// ✅ Good: Custom hooks with proper typing
const useWebSocket = (url: string): WebSocketState => {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  // Hook implementation
};
```

## 🏗️ Module Organization

### Where to Add New Code

**See [`docs/architecture.md`](docs/architecture.md) for complete system overview**

```
src/flock/
├── core/                   # Core orchestration and agents
│   ├── orchestrator.py     # Flock orchestrator
│   └── agent.py            # Agent and AgentBuilder
│
├── orchestrator/           # Orchestrator modules (Phase 3+5A)
│   ├── scheduler.py        # Agent scheduling
│   ├── artifact_manager.py # Publishing and persistence
│   ├── component_runner.py # Component hook execution
│   └── ...                 # More specialized modules
│
├── agent/                  # Agent modules (Phase 4)
│   ├── output_processor.py     # Output artifact creation
│   ├── mcp_integration.py      # MCP tool access
│   └── ...                      # More agent modules
│
├── components/             # Component library
│   ├── agent/              # Agent components
│   └── orchestrator/       # Orchestrator components
│
├── engines/                # Engine implementations
│   ├── dspy_engine.py      # DSPy LLM engine
│   └── dspy/               # DSPy engine modules
│
├── storage/                # Storage backends
│   ├── sqlite/             # SQLite implementation
│   └── in_memory/          # In-memory implementation
│
└── utils/                  # Utility modules (Phase 1)
    ├── validation.py       # Input validation
    ├── formatting.py       # String formatting
    └── ...                 # More utilities
```

### File Organization Guidelines

- **Keep files under 500 lines** - Extract modules when approaching this limit
- **One responsibility per module** - Clear separation of concerns
- **Use descriptive names** - Module name should indicate purpose
- **Group related code** - Components, orchestrator modules, agent modules
- **Public API in `__init__.py`** - Export only public interfaces

**When to create a new module:**
- File approaching 500 LOC
- Distinct responsibility can be extracted
- Code would be reusable elsewhere
- Module would improve testability

**Examples:**
```python
# ✅ Good: Focused module
# src/flock/orchestrator/scheduler.py (189 LOC)
class AgentScheduler:
    """Schedules agents for execution."""
    ...

# ✅ Good: Utility extraction
# src/flock/utils/validation.py
def validate_subscription(subscription: Subscription) -> None:
    """Validate subscription configuration."""
    ...

# ❌ Bad: Monolithic file
# src/flock/everything.py (2000 LOC)
# Too large, extract modules!
```

## ✅ Quality Checklist

Before submitting a pull request, ensure:

### Required Checks

- [ ] All tests pass (`poe test`)
- [ ] Coverage requirements met (`poe test-cov-fail`)
- [ ] Code is properly formatted (`poe format`)
- [ ] Linting passes (`poe lint`)
- [ ] Type checking passes (`uv run mypy src/flock/`)
- [ ] Frontend tests pass (`cd frontend && npm test`)
- [ ] **Backend builds without errors** (`uv build`) ⚠️ **REQUIRED**
- [ ] **Frontend builds without errors** (`cd frontend && npm run build`) ⚠️ **REQUIRED**
- [ ] Documentation is updated
- [ ] No hardcoded secrets
- [ ] Versions bumped if needed (`poe version-check`)
- [ ] **Error handling follows patterns** ([docs/patterns/error_handling.md](docs/patterns/error_handling.md))
- [ ] **Async code follows patterns** ([docs/patterns/async_patterns.md](docs/patterns/async_patterns.md))

### Optional but Recommended

- [ ] Added examples for new features
- [ ] Updated AGENTS.md if workflow changed
- [ ] Added integration tests
- [ ] Performance considerations documented
- [ ] Module stays under 500 LOC

## 📤 Submitting Changes

### Commit Message Convention

Follow conventional commits:

```bash
# Feature
git commit -m "feat: add dashboard event streaming"

# Bug fix
git commit -m "fix: resolve WebSocket reconnection issue"

# Documentation
git commit -m "docs: update AGENTS.md with versioning info"

# Tests
git commit -m "test: add E2E tests for dashboard controls"

# Performance
git commit -m "perf: optimize graph rendering performance"

# Chore (dependencies, build, etc.)
git commit -m "chore: bump version to 0.2.0"

# Refactoring
git commit -m "refactor: extract scheduler module from orchestrator"

# Breaking change
git commit -m "feat!: redesign agent API (BREAKING CHANGE)"
```

### Pull Request Process

1. **Create PR** with descriptive title and body
2. **Link related issues** if applicable
3. **Request review** from maintainers
4. **Address feedback** promptly
5. **Wait for CI** to pass (all quality checks)
6. **Merge** after approval

### PR Description Template

```markdown
## Summary
Brief description of changes and motivation

## Changes
- Added X feature
- Fixed Y bug
- Updated Z documentation

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manually tested feature

## Breaking Changes
None / Describe breaking changes

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Version bumped (if applicable)
- [ ] Follows error handling patterns
- [ ] Follows async patterns
```

## 🔧 Common Tasks

### Add a New Backend Dependency

```bash
# Production dependency
uv add package-name

# Development dependency
uv add --dev package-name

# Verify lock file updated
git diff uv.lock
```

### Add a New Frontend Dependency

```bash
cd frontend

# Production dependency
npm install package-name

# Development dependency
npm install --save-dev package-name

# Verify lock file updated
git diff package-lock.json
```

### Run Dashboard Locally

```bash
# Terminal 1: Backend
uv run python examples/02-dashboard/01_declarative_pizza.py

# Terminal 2: Frontend (if developing)
cd frontend
npm run dev

# Dashboard opens at http://localhost:8344
```

### Debug Tests

```bash
# Run specific test file
uv run pytest tests/test_orchestrator.py -v

# Run with debugging
uv run pytest -s -vv tests/test_specific.py

# Run only failing tests
uv run pytest --lf

# Run with coverage for specific module
uv run pytest tests/test_orchestrator.py --cov=src/flock/core/orchestrator.py
```

### Update Documentation

```bash
# Build docs locally
poe docs

# Docs served at http://127.0.0.1:8344
```

## 🚨 Troubleshooting

### Pre-commit hooks failing

**Problem**: Hooks fail with "command not found"

**Solution**: Install dependencies
```bash
poe install
cd frontend && npm install
```

### UV not found

**Problem**: `uv: command not found`

**Solution**: Install UV
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"
```

### Tests failing

**Problem**: Tests fail with import errors

**Solution**: Rebuild and reinstall
```bash
poe build
```

### Version check warning

**Problem**: Pre-push warns about version bump

**Solution**: This is just a reminder, not blocking
```bash
# Check what needs bumping
poe version-check

# Bump if needed
poe version-minor

# Or push anyway (warning only)
git push
```

### Import errors after refactoring

**Problem**: `ImportError: cannot import name 'Flock' from 'flock.orchestrator'`

**Solution**: Use new public API imports
```python
# ❌ Old (deprecated):
from flock.orchestrator import Flock

# ✅ New (correct):
from flock import Flock
```

## 📚 Additional Resources

### Architecture & Patterns

- **[Architecture Overview](docs/architecture.md)** - Complete system architecture
- **[Error Handling Patterns](docs/patterns/error_handling.md)** - Error handling best practices
- **[Async Patterns](docs/patterns/async_patterns.md)** - Async/await patterns and anti-patterns

### Documentation

- **Project Overview**: [`README.md`](README.md)
- **Agent Guide**: [`AGENTS.md`](AGENTS.md)
- **Versioning Guide**: [`docs/VERSIONING.md`](docs/VERSIONING.md)
- **Pre-commit Hooks**: [`docs/PRE_COMMIT_HOOKS.md`](docs/PRE_COMMIT_HOOKS.md)

### Examples

- **CLI Examples**: [`examples/01-cli/`](examples/01-cli/)
- **Dashboard Examples**: [`examples/02-dashboard/`](examples/02-dashboard/)
- **Claude's Workshop**: [`examples/03-claudes-workshop/`](examples/03-claudes-workshop/)
- **Pattern Examples**: [`examples/00-patterns/`](examples/00-patterns/)

## 🤝 Getting Help

- **Issues**: [GitHub Issues](https://github.com/whiteducksoftware/flock-flow/issues)
- **Discussions**: [GitHub Discussions](https://github.com/whiteducksoftware/flock-flow/discussions)
- **Documentation**: [docs/](docs/)

## 🎉 Recognition

Contributors who make significant contributions will be:
- Added to the contributors list
- Mentioned in release notes
- Invited to join the core team (for ongoing contributors)

## 📜 License

By contributing to Flock, you agree that your contributions will be licensed under the same license as the project.

---

## 🏆 Code Quality Principles

Following these principles ensures Flock remains maintainable and scalable:

1. **Modularity** - Files under 500 LOC, clear separation of concerns
2. **Testability** - Isolated modules with clear contracts, high test coverage
3. **Type Safety** - Full type hints, mypy validation
4. **Error Handling** - Follow documented patterns, add context to errors
5. **Async Correctness** - Proper task lifecycle, avoid blocking operations
6. **Documentation** - Comprehensive docstrings, pattern documentation
7. **Zero Regressions** - All tests must pass, no breaking changes without major version

---

**Thank you for contributing to Flock!** 🚀

Every contribution, no matter how small, helps build the future of AI agent orchestration.

---

*Last updated: October 19, 2025*
