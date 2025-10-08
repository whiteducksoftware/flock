# Smart Versioning Guide for Flock Flow

This document explains the intelligent versioning system that only bumps versions for components that actually changed.

## 🎯 Philosophy

**Key Principle**: Only bump versions for code that changed.

- ✅ Backend changes (`src/`, `tests/`) → Bump `pyproject.toml`
- ✅ Frontend changes (`frontend/`) → Bump `package.json`
- ❌ Docs changes (`docs/`, `README.md`) → No version bump
- ❌ Config changes (`.github/`, `.gitignore`) → No version bump

## 🚀 Quick Start

### Bump versions for changed code

```bash
# Automatically detects what changed and bumps accordingly
poe version-patch   # 0.1.18 → 0.1.19 (bug fixes)
poe version-minor   # 0.1.18 → 0.2.0 (new features)
poe version-major   # 0.1.18 → 1.0.0 (breaking changes)
```

### Check what would be bumped (dry run)

```bash
poe version-check
```

Output example:
```
📦 Current versions:
   Backend:  0.1.18
   Frontend: 0.1.1

🔍 Detected changes:
   Changed files: 5
   Backend changed:  True
   Frontend changed: False

🚀 Bumping versions (patch):
   Backend:  0.1.18 → 0.1.19
   Frontend: 0.1.1 (unchanged)
```

## 📋 How It Works

### Change Detection

The script analyzes git diff to determine what changed:

**Backend paths** (trigger backend version bump):
```
src/
tests/
pyproject.toml
uv.lock
```

**Frontend paths** (trigger frontend version bump):
```
frontend/
```

**Excluded paths** (never trigger version bump):
```
docs/
README.md
AGENTS.md
.github/
.gitignore
.pre-commit-config.yaml
LICENSE
```

### Smart Examples

**Scenario 1: Only backend changed**
```bash
# Made changes to src/flock/agent.py
git add src/flock/agent.py

poe version-patch
# Output:
# ✅ Backend: 0.1.18 → 0.1.19 (pyproject.toml)
# ✅ Frontend: 0.1.1 (unchanged)
```

**Scenario 2: Only frontend changed**
```bash
# Made changes to frontend/src/components/Graph.tsx
git add frontend/src/components/Graph.tsx

poe version-patch
# Output:
# ✅ Backend: 0.1.18 (unchanged)
# ✅ Frontend: 0.1.1 → 0.1.2 (package.json)
```

**Scenario 3: Both changed**
```bash
# Added new API endpoint (backend) and UI for it (frontend)
git add src/flock/dashboard/service.py
git add frontend/src/components/settings/AdvancedSettings.tsx

poe version-minor
# Output:
# ✅ Backend: 0.1.18 → 0.2.0 (pyproject.toml)
# ✅ Frontend: 0.1.1 → 0.2.0 (package.json)
```

**Scenario 4: Only docs changed**
```bash
# Updated documentation
git add docs/VERSIONING.md README.md

poe version-patch
# Output:
# ✨ No code changes detected - only docs/config changed
#    No version bump needed!
```

## 🔧 Advanced Usage

### Force bump specific component

```bash
# Bump only backend, regardless of what changed
python scripts/bump_version.py patch --force-backend

# Bump only frontend, regardless of what changed
python scripts/bump_version.py minor --force-frontend

# Force bump both
python scripts/bump_version.py major --force-backend --force-frontend
```

### Dry run to see what would happen

```bash
# Check without modifying files
python scripts/bump_version.py patch --check
```

## 🔄 Typical Workflow

### Development workflow

```bash
# 1. Make changes to code
vim src/flock/orchestrator.py

# 2. Test changes
poe test

# 3. Commit code changes
git add src/flock/orchestrator.py
git commit -m "feat: add new orchestration feature"

# 4. Bump version based on change type
poe version-minor  # New feature = minor bump

# 5. Review version changes
git diff pyproject.toml

# 6. Commit version bump
git add pyproject.toml
git commit -m "chore: bump version to 0.2.0"

# 7. Push (pre-push hook will validate)
git push
```

### Release workflow

```bash
# 1. Ensure versions are bumped
poe version-check

# 2. Tag the release
git tag v0.2.0

# 3. Push with tags
git push origin main --tags

# 4. Build and publish (CI/CD handles this)
```

## ⚠️ Pre-Push Hook

A **non-blocking** warning runs before push to remind you if versions should be bumped:

```bash
git push

# Output:
# ⚠️  Version bump recommended:
#    ⚠️  Backend code changed but version not bumped in pyproject.toml
#
# 💡 To bump versions:
#    poe version-patch   # Patch version (0.1.18 → 0.1.19)
#    poe version-minor   # Minor version (0.1.18 → 0.2.0)
#    poe version-major   # Major version (0.1.18 → 1.0.0)
#
# This is just a reminder - push will continue.
```

**Note**: This is a **warning only** - it won't block your push. It's just a helpful reminder!

## 📊 Semantic Versioning Guidelines

Follow semantic versioning (semver) principles:

### Patch (0.1.18 → 0.1.19)
- Bug fixes
- Performance improvements
- Documentation updates (if code also changed)
- Internal refactoring without API changes

```bash
poe version-patch
```

### Minor (0.1.18 → 0.2.0)
- New features (backward compatible)
- New API endpoints
- New components or modules
- Deprecations (with backward compatibility)

```bash
poe version-minor
```

### Major (0.1.18 → 1.0.0)
- Breaking API changes
- Removed deprecated features
- Major architectural changes
- First stable release (0.x.x → 1.0.0)

```bash
poe version-major
```

## 🎯 Best Practices

### DO ✅

- **Bump versions after code changes**: Use `poe version-*` after committing code
- **Match bump type to change**: patch/minor/major based on semver
- **Keep frontend/backend in sync**: Bump both for coordinated releases
- **Check before pushing**: Run `poe version-check` before `git push`
- **Use semantic commit messages**: `feat:`, `fix:`, `chore:`, `breaking:`

### DON'T ❌

- **Don't bump for docs-only changes**: Script automatically skips these
- **Don't manually edit versions**: Use the script to keep things consistent
- **Don't bump in pre-commit hooks**: Versions are intentional, not automatic
- **Don't ignore the pre-push warning**: It's there to help you

## 🔍 Troubleshooting

### "No changed files detected"

**Problem**: Script says no changes even though you made changes.

**Solution**: Stage your changes first with `git add`

```bash
git add src/flock/agent.py
poe version-patch
```

### "Only docs/config changed"

**Problem**: Script won't bump version.

**Solution**: This is correct! Docs-only changes don't need version bumps. If you really need to bump anyway:

```bash
python scripts/bump_version.py patch --force-backend
```

### Versions out of sync

**Problem**: Backend is 0.1.18 but frontend is 0.1.1.

**Solution**: This is OK! They can have independent versions. But for major releases, sync them:

```bash
python scripts/bump_version.py minor --force-backend --force-frontend
```

## 📚 Script Reference

### `scripts/bump_version.py`

The main version bumping script.

**Arguments**:
- `patch|minor|major` - Type of version bump (required)
- `--check` - Dry run without modifying files
- `--force-backend` - Force bump backend version
- `--force-frontend` - Force bump frontend version

**Examples**:
```bash
# Smart bump (auto-detect what changed)
python scripts/bump_version.py patch

# Dry run
python scripts/bump_version.py minor --check

# Force backend only
python scripts/bump_version.py patch --force-backend
```

### `scripts/check_version_bump.py`

Pre-push hook that warns if versions should be bumped.

**Exit codes**:
- `0` - No warning needed
- `1` - Warning shown (non-blocking)

**Manual run**:
```bash
python scripts/check_version_bump.py
```

## 🎉 Summary

The smart versioning system:
- ✅ Only bumps versions for actual code changes
- ✅ Skips docs and config files automatically
- ✅ Keeps frontend and backend independent
- ✅ Provides helpful warnings (non-blocking)
- ✅ Supports forced bumps when needed
- ✅ Integrates with existing `poe` workflow

**Simple workflow**:
```bash
# Make changes → Commit → Bump → Commit → Push
git commit -m "feat: new feature"
poe version-minor
git add pyproject.toml package.json
git commit -m "chore: bump version"
git push
```

Happy versioning! 🚀
