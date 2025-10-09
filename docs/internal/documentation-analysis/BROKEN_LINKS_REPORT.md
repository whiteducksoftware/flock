# Broken Links Report - Phase 1 Audit

**Generated:** 2025-10-08
**Status:** CRITICAL - Blocks strict mode builds

## Summary

- **Total broken links:** 13
- **Severity:** High (prevents `mkdocs build --strict` from passing)
- **Root cause:** File migrations and references to old documentation structure

---

## Detailed Broken Links

### 1. `getting-started/installation.md`
**Line reference:** Check line containing link
**Broken link:** `../guides/tracing-quickstart.md`
**Issue:** File is actually at `guides/tracing/tracing-quickstart.md`
**Fix:** Change to `../guides/tracing/tracing-quickstart.md`

---

### 2. `guides/blackboard.md`
**Line reference:** 221
**Broken link:** `tracing/overview.md`
**Issue:** File doesn't exist, should be `tracing/index.md`
**Fix:** Change to `tracing/index.md`

---

### 3. `guides/tracing/how_to_use_tracing_effectively.md`
**Multiple broken links:**

**Link 1:** `AUTO_TRACING.md`
**Issue:** File doesn't exist in guides/tracing/, likely renamed to `auto-tracing.md`
**Fix:** Change to `auto-tracing.md`

**Link 2:** `../README.md`
**Issue:** README.md is in project root, not in guides/
**Fix:** Change to `../../README.md` or remove if not needed in docs site

**Link 3:** `../AGENTS.md`
**Issue:** AGENTS.md is in project root, not in guides/
**Fix:** Change to `../../AGENTS.md` or remove if not appropriate for user-facing docs

---

### 4. `guides/tracing/trace-module.md`
**Multiple broken links:**

**Link 1:** `AUTO_TRACING.md`
**Issue:** File doesn't exist, should be `auto-tracing.md`
**Fix:** Change to `auto-tracing.md`

**Link 2:** `../AGENTS.md` (appears twice)
**Issue:** AGENTS.md is in project root
**Fix:** Change to `../../AGENTS.md` or remove if not appropriate for user docs

**Link 3:** `../src/flock/frontend/README.md`
**Issue:** Points outside docs directory
**Fix:** Remove or replace with appropriate user-facing documentation

**Link 4:** `../src/flock/frontend/docs/DESIGN_SYSTEM.md`
**Issue:** Points outside docs directory
**Fix:** Remove or replace with appropriate user-facing documentation

---

### 5. `guides/tracing/unified-tracing.md`
**Multiple broken links:**

**Link 1:** `../AGENTS.md#observability--debugging-with-opentelemetry--duckdb`
**Issue:** AGENTS.md is in project root
**Fix:** Change to `../../AGENTS.md#observability--debugging-with-opentelemetry--duckdb`

**Link 2:** `AUTO_TRACING.md`
**Issue:** File should be `auto-tracing.md`
**Fix:** Change to `auto-tracing.md`

**Link 3:** `../AGENTS.md#duckdb-schema-reference`
**Issue:** AGENTS.md is in project root
**Fix:** Change to `../../AGENTS.md#duckdb-schema-reference`

---

## Fix Strategy

### Immediate Actions (Required for strict builds)

1. **Fix file name references:**
   - Change all `AUTO_TRACING.md` → `auto-tracing.md`
   - Change `tracing-quickstart.md` → `tracing/tracing-quickstart.md`
   - Change `tracing/overview.md` → `tracing/index.md`

2. **Fix project root references:**
   - Decide: Should AGENTS.md be linked from user docs?
     - If YES: Change `../AGENTS.md` → `../../AGENTS.md`
     - If NO: Remove these links (AGENTS.md is for AI agents, not end users)

3. **Fix source code references:**
   - Remove links to `../src/flock/frontend/` - these are internal dev docs
   - Replace with user-facing equivalents if needed

### Verification Command

```bash
mkdocs build --strict
```

Should complete without "Aborted" message.

---

## Recommendations

### For User-Facing Docs
**REMOVE links to:**
- `AGENTS.md` (AI agent development guide, not for end users)
- `../README.md` (project README, redundant with docs)
- `../src/flock/frontend/*` (internal developer documentation)

**REPLACE with:**
- Links to user-facing guides in docs/guides/
- Links to getting-started tutorials
- Links to reference documentation

### For Developer Docs (docs/internal/)
- Links to AGENTS.md are fine
- Links to src/ are fine
- But these won't be included in published site (excluded in mkdocs.yml)

---

## Testing Checklist

After fixes:
- [ ] `mkdocs build --strict` passes without errors
- [ ] All navigation links work in built site
- [ ] No 404s when clicking through documentation
- [ ] External links (GitHub, PyPI) still work

---

**Priority:** HIGH - Fix before Phase 2
**Estimated effort:** 30 minutes to fix all links
**Risk if not fixed:** Documentation build pipeline will fail
