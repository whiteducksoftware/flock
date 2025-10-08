# Pre-commit Hooks Setup Guide

This document explains the pre-commit hook system for Flock Flow, designed to maintain code quality and prevent broken builds from being committed.

## 🎯 Overview

The pre-commit hook system enforces quality standards before code is committed, ensuring:
- **Code Quality**: Linting, formatting, and type checking
- **Security**: Detection of secrets and security vulnerabilities
- **Build Integrity**: Backend and frontend builds pass successfully
- **Test Coverage**: Critical paths maintain 100% coverage
- **Performance**: Fast feedback during development

## 📋 Quality Standards

Based on the development workflow outlined in `docs/patterns/development-workflow.md`, our quality gates include:

### Backend Requirements
- ✅ **Ruff linting** - Code quality and style
- ✅ **Ruff formatting** - Consistent code formatting
- ✅ **mypy type checking** - Type safety
- ✅ **pytest** - Test execution
- ✅ **Coverage ≥80%** - Overall test coverage
- ✅ **Coverage =100%** - Critical path coverage (orchestrator, subscription, visibility, agent)
- ✅ **UV build** - Package builds successfully
- ✅ **Bandit security scan** - Security vulnerability detection

### Frontend Requirements
- ✅ **TypeScript type check** - Type safety
- ✅ **npm build** - Production build succeeds
- ✅ **Vitest** - Component tests pass

## 🚀 Installation

### 1. Install pre-commit

```bash
# Using pip
pip install pre-commit

# Or using UV (recommended)
uv add --dev pre-commit
```

### 2. Install Git hooks

```bash
# Install pre-commit hooks
pre-commit install

# Optional: Install pre-push hooks for expensive checks
pre-commit install --hook-type pre-push
```

### 3. Verify installation

```bash
# Run hooks on all files to verify setup
pre-commit run --all-files
```

## ⚡ Hook Stages

### Pre-commit (Fast - runs on every commit)
- Ruff linting and formatting
- mypy type checking
- YAML/TOML/JSON validation
- Trailing whitespace and end-of-file fixes
- Merge conflict detection
- Private key detection
- Fast tests only
- Critical path tests (if files changed)

### Pre-push (Comprehensive - runs on git push)
- Frontend build check
- Backend build check
- Full test suite with coverage
- Security scan

## 🔧 Usage

### Normal commit workflow

```bash
git add .
git commit -m "feat: add new feature"

# Hooks run automatically
# - If hooks pass: commit succeeds
# - If hooks fail: commit is blocked, fix issues and retry
```

### Skip hooks (emergency only)

```bash
# Skip pre-commit hooks (NOT RECOMMENDED)
git commit --no-verify -m "emergency fix"

# Note: CI will still run all checks!
```

### Run hooks manually

```bash
# Run all hooks on staged files
pre-commit run

# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff
pre-commit run mypy
pre-commit run pytest-critical
```

## 📊 Hook Details

### Ruff (Linting & Formatting)

**Purpose**: Fast Python linting and formatting
**Speed**: Very fast (~100ms)
**Auto-fix**: Yes

```yaml
- id: ruff
  args: [--fix]  # Automatically fixes issues

- id: ruff-format
  # Formats code consistently
```

### mypy (Type Checking)

**Purpose**: Static type checking for Python
**Speed**: Fast (~2s)
**Auto-fix**: No

```yaml
- id: mypy
  args: [--config-file=pyproject.toml]
  files: ^src/flock/
```

### Bandit (Security Scanning)

**Purpose**: Detect common security issues
**Speed**: Fast (~1s)
**Auto-fix**: No

```yaml
- id: bandit
  args: [-c, pyproject.toml, -r, src/flock/]
```

### TypeScript Type Check

**Purpose**: Ensure TypeScript types are correct
**Speed**: Medium (~5s)
**Auto-fix**: No

```yaml
- id: tsc
  entry: bash -c 'cd frontend && npm run type-check'
```

### Build Checks

**Purpose**: Ensure code builds successfully
**Speed**: Slow (~30s each)
**Stage**: Pre-push only

```yaml
- id: frontend-build
  entry: bash -c 'cd frontend && npm run build'
  stages: [push]

- id: uv-build
  entry: bash -c 'uv build'
  stages: [push]
```

### Critical Path Tests

**Purpose**: Ensure critical code paths maintain 100% coverage
**Speed**: Fast (~3s)
**Trigger**: Only when critical files are modified

```yaml
- id: pytest-critical
  entry: bash -c 'poe test-critical'
  files: ^src/flock/(orchestrator|subscription|visibility|agent)\.py$
```

## 🎯 Best Practices

### 1. Run hooks before committing

```bash
# Good practice: run hooks before staging
pre-commit run --all-files

# Then commit
git add .
git commit -m "feat: implement feature"
```

### 2. Fix issues incrementally

```bash
# If hooks fail, fix one issue at a time
pre-commit run ruff          # Fix linting issues first
pre-commit run mypy          # Then type issues
pre-commit run pytest-fast   # Then test failures
```

### 3. Use auto-fix hooks

Many hooks auto-fix issues. After running:

```bash
git add .  # Re-stage auto-fixed files
git commit -m "feat: implement feature"
```

### 4. Keep hooks updated

```bash
# Update hooks to latest versions
pre-commit autoupdate

# Run updated hooks
pre-commit run --all-files
```

## 🚨 Troubleshooting

### Hook fails with "command not found"

**Solution**: Ensure dependencies are installed

```bash
# Install all dependencies
poe install

# Or manually
uv sync --dev --all-groups --all-extras
cd frontend && npm install
```

### Hook is slow

**Solution**: Move slow hooks to pre-push stage

Edit `.pre-commit-config.yaml`:

```yaml
- id: slow-hook
  stages: [push]  # Only run on push, not commit
```

### Hook always fails

**Solution**: Debug the hook

```bash
# Run hook with verbose output
pre-commit run hook-name --verbose

# Or skip hook temporarily
SKIP=hook-name git commit -m "message"
```

### Want to disable specific hook

Edit `.pre-commit-config.yaml` and comment out the hook:

```yaml
# - id: hook-to-disable
#   name: disabled hook
```

## 📈 CI/CD Integration

Pre-commit hooks also run in GitHub Actions CI/CD pipeline (`.github/workflows/quality.yml`).

**Workflow**:
1. Developer commits code → pre-commit hooks run locally
2. Developer pushes code → pre-push hooks run
3. GitHub receives push → CI/CD runs all quality checks
4. PR requires all checks to pass before merge

This ensures:
- Fast feedback locally
- Comprehensive validation in CI
- No broken code reaches main branch

## 🔄 Updating Hooks

When new quality requirements are added:

1. Update `.pre-commit-config.yaml`
2. Update `.github/workflows/quality.yml`
3. Run `pre-commit run --all-files` to verify
4. Commit changes

## 📚 Additional Resources

- **pre-commit documentation**: https://pre-commit.com/
- **Ruff documentation**: https://docs.astral.sh/ruff/
- **Development workflow**: `docs/patterns/development-workflow.md`
- **Quality standards**: `AGENTS.md` (lines 442-469)

---

**Maintain quality at startup speed!** 🚀
