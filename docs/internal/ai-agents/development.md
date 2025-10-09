# Development Workflow Guide for AI Agents

This document covers testing strategy, development workflow, and quality standards for AI agents working with Flock Flow.

## 🧪 Testing Strategy

### Test Coverage Goals

- **Overall Target:** 80%+ project-wide
- **Core Framework Modules:** 90-100% coverage
- **Critical Paths:** 100% coverage (security & correctness)
- **Frontend Components:** 80%+ coverage
- **Integration Tests:** Full E2E validation

### Test Categories

1. **Unit Tests** (`tests/test_*.py`) - Individual component testing
2. **Contract Tests** (`tests/contract/`) - System behavior contracts
3. **Integration Tests** (`tests/integration/`) - Component interaction testing
4. **End-to-End Tests** (`tests/e2e/`) - Full workflow testing
5. **Frontend Tests** (`frontend/src/test/**/*.test.tsx`) - React component testing

### Running Tests

```bash
# Run all tests
poe test

# Run with coverage report
poe test-cov

# Run critical path tests (100% coverage required)
poe test-critical

# Run frontend tests
cd frontend && npm test

# Run E2E tests
poe test-e2e

# Determinism test (10 consecutive runs)
poe test-determinism
```

### Current Test Status

- **Backend:** 750+ tests passing
- **Frontend:** 367 tests passing
- **E2E:** 6 tests passing
- **Total:** 1,100+ tests passing
- **Coverage:** Core modules 90-100%, overall 79%
- **100% Coverage Modules:** CLI, Components, Runtime, Store, MCP Tool, Helper CLI
- **Near-Perfect Coverage:** Logging (99.11%), Utilities (95.85%)

## 🔧 Development Workflow

### Quick Start for Contributors

```bash
# 1. Clone and setup
git clone https://github.com/yourusername/flock-flow.git
cd flock-flow
poe install

# 2. Install pre-commit hooks (quality automation)
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push

# 3. Create feature branch
git checkout -b feature/your-feature-name

# 4. Make changes...
# Write code, tests, documentation

# 5. Run quality checks (or let pre-commit do it automatically)
poe lint          # Lint code
poe format        # Format code
poe test          # Run tests
poe test-cov      # Check coverage

# 6. Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: Add your feature description"

# 7. Push (build checks and version validation run)
git push origin feature/your-feature-name
```

**📚 For detailed contribution guidelines, see [`CONTRIBUTING.md`](../../CONTRIBUTING.md)**

### Quality Standards

**Before submitting changes, ensure:**
- [ ] All tests pass (`poe test`)
- [ ] Coverage requirements met (`poe test-cov-fail`)
- [ ] Code is properly formatted (`poe format`)
- [ ] Linting passes (`poe lint`)
- [ ] Type checking passes (`uv run mypy src/flock/`)
- [ ] Frontend tests pass (`cd frontend && npm test`)
- [ ] **Backend builds without errors** (`uv build`) ⚠️ **REQUIRED**
- [ ] **Frontend builds without errors** (`cd frontend && npm run build`) ⚠️ **REQUIRED**
- [ ] Pre-commit hooks installed and passing
- [ ] Versions bumped if code changed (`poe version-check`)
- [ ] Documentation is updated
- [ ] No hardcoded secrets

**💡 Tip**: Pre-commit hooks automatically check most of these when you commit!

**🚨 CRITICAL BUILD REQUIREMENTS:**

For **UI/Frontend changes:**
- **MUST run `npm run build` successfully** before committing
- Fix all TypeScript compilation errors
- Fix all linting errors
- Ensure no runtime errors in production build

For **Backend/Python changes:**
- **MUST run `uv build` successfully** before committing
- Fix all type checking errors
- Fix all import errors
- Ensure package builds cleanly

**Failure to build is a blocking issue - do not commit broken builds!**

### Versioning

Flock Flow uses **smart versioning** that only bumps versions for components that actually changed:

```bash
# Check what would be bumped (dry run)
poe version-check

# Bump versions based on what changed
poe version-patch   # 0.1.18 → 0.1.19 (bug fixes)
poe version-minor   # 0.1.18 → 0.2.0 (new features)
poe version-major   # 0.1.18 → 1.0.0 (breaking changes)
```

**Smart detection**:
- ✅ Backend changes (`src/`, `tests/`) → Bump `pyproject.toml`
- ✅ Frontend changes (`frontend/`) → Bump `package.json`
- ❌ Docs changes (`docs/`, `README.md`) → No version bump

**Typical workflow**:
1. Make code changes and commit
2. Run `poe version-minor` (or patch/major)
3. Commit version bump: `git commit -m "chore: bump version to 0.2.0"`
4. Push (pre-push hook will validate)

See [`docs/VERSIONING.md`](../VERSIONING.md) for complete guide.

### Pre-commit Hooks

Automated quality checks run on every commit and push:

**Install hooks** (one-time setup):
```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

**What runs automatically:**
- **On commit**: Linting, formatting, type checking, security scans, fast tests
- **On push**: Build validation, comprehensive tests, version check

**Manual runs:**
```bash
pre-commit run --all-files  # Run all hooks
pre-commit run ruff         # Run specific hook
```

**Skip hooks** (emergency only):
```bash
git commit --no-verify -m "emergency fix"
```

See [`docs/PRE_COMMIT_HOOKS.md`](../PRE_COMMIT_HOOKS.md) for complete guide.

### Commit Message Convention

```bash
# Feature
git commit -m "feat: Add dashboard event streaming"

# Bug fix
git commit -m "fix: Resolve WebSocket reconnection issue"

# Documentation
git commit -m "docs: Update AGENTS.md with dashboard info"

# Tests
git commit -m "test: Add E2E tests for dashboard controls"

# Performance
git commit -m "perf: Optimize graph rendering performance"
```

---

*For more workflow details, see [docs/patterns/development-workflow.md](../patterns/development-workflow.md)*
