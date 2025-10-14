---
title: Contributing to Flock
description: Learn how to contribute to Flock - setup, development workflow, testing, and pull request process
tags:
  - contributing
  - development
  - community
search:
  boost: 1.2
---

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
cd src/flock/frontend && npm test

# You're ready to contribute! 🚀
```

## 📋 Prerequisites

### Required Software

- **Python 3.10+** - Modern Python with async features
- **UV Package Manager** - Fast, reliable dependency management (NOT pip!)
- **Node.js 18+** (22+ recommended) - For frontend development
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
cd src/flock/frontend && npm install      # Install frontend deps
```

### 3. Set Up Environment Variables

```bash
# Copy environment template
cp .envtemplate .env

# Edit .env and add your API keys
export OPENAI_API_KEY="sk-..."
export DEFAULT_MODEL="openai/gpt-4.1"
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
cd src/flock/frontend && npm test

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
    orchestrator = Flock("openai/gpt-4.1")

    # Act
    result = await orchestrator.do_something()

    # Assert
    assert result is not None
```

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

## 📝 Code Style

### Python

- **Formatter**: Ruff (auto-formats on commit)
- **Linter**: Ruff with comprehensive rules
- **Type Checker**: mypy

```python
# ✅ Good: Type hints everywhere
async def execute(self, ctx: Context, artifacts: List[Artifact]) -> List[Artifact]:
    """Execute the agent with given artifacts.

    Args:
        ctx: Execution context
        artifacts: Input artifacts

    Returns:
        List of output artifacts
    """
    ...

# ✅ Good: Pydantic models with Field descriptions
@flock_type
class Movie(BaseModel):
    """Movie information."""

    title: str = Field(description="Movie title in CAPS")
    runtime: int = Field(ge=60, le=400, description="Runtime in minutes")
```

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

### Code Organization

- Keep files under 500 lines
- Use modular design patterns
- Separate concerns clearly
- Maintain clean architecture

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

### Optional but Recommended

- [ ] Added examples for new features
- [ ] Updated AGENTS.md if workflow changed
- [ ] Added integration tests
- [ ] Performance considerations documented

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
uv run python examples/03-the-dashboard/01_declarative_pizza.py

# Terminal 2: Frontend (if developing)
cd src/flock/frontend
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
uv run pytest tests/test_orchestrator.py --cov=src/flock/orchestrator.py
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
cd src/flock/frontend && npm install
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

## 📚 Additional Resources

### Documentation

- **[Getting Started](../getting-started/installation.md)** - Installation and quick start
- **[Core Concepts](../getting-started/concepts.md)** - Understanding Flock's architecture
- **[Tutorials](../tutorials/index.md)** - Step-by-step learning path
- **[API Reference](../reference/api.md)** - Complete API documentation

### Examples

- **[Showcase Examples](https://github.com/whiteducksoftware/flock/tree/main/examples/showcase/)** - Production-ready examples
- **[Feature Examples](https://github.com/whiteducksoftware/flock/tree/main/examples/features/)** - Feature demonstrations

## 🤝 Getting Help

- **Issues**: [GitHub Issues](https://github.com/whiteducksoftware/flock/issues)
- **Discussions**: [GitHub Discussions](https://github.com/whiteducksoftware/flock/discussions)
- **Documentation**: [docs.flock.whiteduck.de](https://docs.flock.whiteduck.de)

## 🎉 Recognition

Contributors who make significant contributions will be:
- Added to the contributors list
- Mentioned in release notes
- Invited to join the core team (for ongoing contributors)

## 📜 License

By contributing to Flock, you agree that your contributions will be licensed under the same license as the project.

---

**Thank you for contributing to Flock!** 🚀

Every contribution, no matter how small, helps build the future of AI agent orchestration.

---

**Next Steps:**
- **[Roadmap](roadmap.md)** - See what's planned for future releases
- **[Changelog](changelog.md)** - View recent changes and updates
- **[Quick Start](../getting-started/quick-start.md)** - Build your first agent
