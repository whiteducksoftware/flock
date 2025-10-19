# Breaking Changes - Flock Refactoring

**Last Updated:** 2025-10-18
**Refactoring Status:** Phase 7 (96% Complete)
**Impact Level:** 🔴 HIGH - All examples require updates

---

## 📋 Table of Contents

1. [Critical Import Path Changes](#critical-import-path-changes)
2. [Component Import Changes](#component-import-changes)
3. [Engine API Changes](#engine-api-changes)
4. [Context Provider Changes](#context-provider-changes)
5. [Fan-Out API Changes](#fan-out-api-changes)
6. [MCP API Changes](#mcp-api-changes)
7. [Migration Checklist](#migration-checklist)
8. [Examples Status](#examples-status)

---

## 🔴 Critical Import Path Changes

### **BREAKING:** Orchestrator Import Path

**Status:** ❌ **BREAKS ALL 51 EXAMPLES**

**Before:**
```python
from flock import Flock
```

**After (Option 1 - RECOMMENDED):**
```python
from flock import Flock  # Use public API
```

**After (Option 2 - Internal):**
```python
from flock.core import Flock  # Use core module directly
```

**Impact:**
- ❌ **51/51 examples** use old path `from flock import Flock`
- ✅ **Fix is simple:** Change to `from flock import Flock`
- ⚠️ **Backward compatibility:** Old path `flock.orchestrator` still exists but is deprecated

**Affected Examples:**
- `examples/01-cli/*.py` (15 files)
- `examples/02-dashboard/*.py` (16 files)
- `examples/03-claudes-workshop/*.py` (10 files)
- `examples/04-misc/*.py` (5 files)
- `examples/00-patterns/*.py` (5 files)

**Migration Script:**
```bash
# Update all examples (run from project root)
find examples/ -name "*.py" -exec sed -i '' 's/from flock.orchestrator import/from flock import/g' {} +
```

---

## ⚙️ Component Import Changes

### **BREAKING:** Component Base Classes Moved

**Before:**
```python
from flock.components import AgentComponent, EngineComponent, OrchestratorComponent
```

**After:**
```python
from flock.components.agent import AgentComponent, EngineComponent
from flock.components.orchestrator import OrchestratorComponent
```

**Recommended (Use Public API):**
```python
from flock.components.agent import AgentComponent, EngineComponent
from flock.components.orchestrator import OrchestratorComponent
```

**Impact:**
- ⚠️ **Low impact:** Most code imports from `flock` package, not `flock.components`
- ✅ **Public API unchanged:** `from flock.components.agent import AgentComponent` still works
- ✅ **Examples unaffected:** No examples import components directly

### **NEW:** Utility Components

**New Paths:**
```python
from flock.components.agent import OutputUtilityComponent
from flock.components.orchestrator import (
    CircuitBreakerComponent,
    DeduplicationComponent,
    CollectionComponent,
)
```

**Impact:** ✅ No breaking changes (new modules only)

---

## 🔧 Engine API Changes

### **BREAKING:** Engine Evaluation Methods Simplified

**Status:** 🟡 **SEMI-BREAKING** - Old methods removed, new pattern simpler

**Before (Old Engine API):**
```python
class MyEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Single artifact evaluation
        return EvalResult(artifacts=[artifact])

    async def evaluate_batch(self, agent, ctx, inputs, output_group):
        # Batch evaluation (REMOVED!)
        return EvalResult(artifacts=[...])

    async def evaluate_fanout(self, agent, ctx, inputs, output_group):
        # Fan-out evaluation (REMOVED!)
        return EvalResult(artifacts=[...])
```

**After (New Unified API):**
```python
class MyEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Auto-detects batch vs fan-out from ctx and output_group
        # Check ctx.is_batch for batch mode
        # Check output_group.outputs[0].count > 1 for fan-out

        if ctx.is_batch:
            # Handle batch processing
            return EvalResult(artifacts=[...])
        elif output_group.outputs[0].count > 1:
            # Handle fan-out (multiple artifacts)
            return EvalResult(artifacts=[artifact1, artifact2, ...])
        else:
            # Handle single artifact
            return EvalResult(artifacts=[artifact])
```

**Impact:**
- ❌ **Custom engines must update** if they implemented `evaluate_batch()` or `evaluate_fanout()`
- ✅ **Built-in DSPyEngine updated** - no action needed for users
- ⚠️ **Examples unaffected:** Most examples don't define custom engines

**Migration:**
1. Remove `evaluate_batch()` method
2. Remove `evaluate_fanout()` method
3. Update `evaluate()` to check `ctx.is_batch` and `output_group.outputs[0].count`
4. Use single `evaluate()` method for all patterns

**Example Migration:**

**Before:**
```python
class MovieEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Single movie
        return EvalResult(artifacts=[movie_artifact])

    async def evaluate_fanout(self, agent, ctx, inputs, output_group):
        # Multiple movies
        return EvalResult(artifacts=[movie1, movie2, movie3])
```

**After:**
```python
class MovieEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Auto-detect: check output_group for fan-out
        count = output_group.outputs[0].count if output_group.outputs else 1

        if count > 1:
            # Fan-out: create multiple artifacts
            movies = [create_movie(i) for i in range(count)]
            return EvalResult(artifacts=movies)
        else:
            # Single artifact
            return EvalResult(artifacts=[create_movie()])
```

---

## 🔐 Context Provider Changes

### **NEW:** Pluggable Context Provider System

**Status:** ✅ **NON-BREAKING** - Additive feature, backward compatible

**New Pattern:**
```python
from flock import Flock
from flock.context_provider import FilteredContextProvider, FilterConfig

# Global context provider (all agents)
flock = Flock(context_provider=FilteredContextProvider(
    FilterConfig(tags={"important"})
))

# Per-agent context provider
agent = (
    flock.agent("researcher")
    .with_context(FilteredContextProvider(
        FilterConfig(from_agents={"analyzer"})
    ))
)
```

**Impact:**
- ✅ **Fully backward compatible:** Default provider still works
- ✅ **Examples unaffected:** No examples use context providers yet
- 📚 **New documentation needed:** Context provider patterns guide

**Features:**
- Security boundary enforcement
- Declarative filtering (tags, agents, time ranges)
- Per-agent or global configuration
- Custom provider support via `BaseContextProvider`

---

## 🎯 Fan-Out API Changes

### **ENHANCED:** `.publishes()` Fan-Out Syntax

**Status:** ✅ **NON-BREAKING** - Enhanced API, old syntax still works

**Before (Old Syntax - Still Works):**
```python
agent.publishes(Task, Task, Task)  # Creates 3 Tasks
```

**After (New Syntax - Recommended):**
```python
agent.publishes(Task, fan_out=3)  # Clearer intent
```

**Both Patterns Supported:**
```python
# Pattern 1: Duplicate types (OLD - verbose but works)
agent.publishes(Movie, Tagline, Movie, Movie)  # 1 Movie, 1 Tagline, 2 more Movies

# Pattern 2: fan_out parameter (NEW - recommended)
agent.publishes(Movie, fan_out=3)  # Creates 3 Movies
agent.publishes(Movie, Tagline, fan_out=2)  # ERROR! fan_out applies to ALL types
```

**Impact:**
- ✅ **Fully backward compatible:** Old syntax still supported
- ⚠️ **Examples may use old syntax:** Consider updating for clarity
- 📚 **Documentation needs update:** Recommend new syntax in guides

**Migration (Optional but Recommended):**

**Before:**
```python
# Verbose: duplicate types
.publishes(Report, Report, Report, Report, Report)
```

**After:**
```python
# Clear: explicit count
.publishes(Report, fan_out=5)
```

---

## 🔌 MCP API Changes

### **CONFIRMED:** MCP Registration API Unchanged

**Status:** ✅ **NO BREAKING CHANGES**

**MCP Registration (Still Works):**
```python
from flock import Flock
from flock.mcp import StdioServerParameters

flock = Flock()

# Add MCP server (API unchanged)
flock.add_mcp(
    name="search_web",
    enable_tools_feature=True,
    connection_params=StdioServerParameters(
        command="uvx",
        args=["duckduckgo-mcp-server"],
    ),
)

# Assign to agent (API unchanged)
agent = (
    flock.agent("researcher")
    .with_mcps(["search_web", "read-website"])  # Still works!
)
```

**Per-Server Configuration (API unchanged):**
```python
agent.with_mcps({
    "filesystem": {
        "roots": ["/workspace/data"],
        "tool_whitelist": ["read_file", "write_file"],
    },
    "github": {},  # No restrictions
})
```

**Impact:**
- ✅ **Zero breaking changes:** MCP API stable
- ✅ **Examples work as-is:** No migration needed
- ✅ **Documentation accurate:** No updates required

---

## 🔄 Subscription API Changes

### **CONFIRMED:** Subscription API Unchanged

**Status:** ✅ **NO BREAKING CHANGES**

**JoinSpec (Still Works):**
```python
from flock.subscription import JoinSpec
from datetime import timedelta

agent.consumes(
    XRayImage,
    LabResults,
    join=JoinSpec(
        by=lambda x: x.patient_id,  # Correlation key
        within=timedelta(minutes=5),  # Time window
    ),
)
```

**BatchSpec (Still Works):**
```python
from flock.subscription import BatchSpec
from datetime import timedelta

agent.consumes(
    Email,
    batch=BatchSpec(
        size=10,  # Batch size
        timeout=timedelta(seconds=30),  # Or time-based
    ),
)
```

**Impact:**
- ✅ **Zero breaking changes:** Subscription API stable
- ✅ **Examples work as-is:** No migration needed
- ✅ **Documentation accurate:** No updates required

---

## ✅ Migration Checklist

### For All Codebases

- [ ] **Update import paths**
  ```python
  # BEFORE:
  from flock import Flock

  # AFTER:
  from flock import Flock
  ```

- [ ] **Update component imports (if used)**
  ```python
  # BEFORE:
  from flock.components import AgentComponent

  # AFTER:
  from flock.components.agent import AgentComponent
  ```

- [ ] **Test all code** - Run full test suite
  ```bash
  pytest tests/ -v
  ```

- [ ] **Update documentation** - Fix code examples in docs

### For Custom Engine Implementations

- [ ] **Remove deprecated methods**
  - Delete `evaluate_batch()` method
  - Delete `evaluate_fanout()` method

- [ ] **Implement unified evaluate()**
  ```python
  async def evaluate(self, agent, ctx, inputs, output_group):
      # Check ctx.is_batch for batching
      # Check output_group.outputs[0].count for fan-out
      # Return EvalResult with appropriate artifacts
  ```

- [ ] **Test engine behavior**
  - Test single artifact mode
  - Test batch mode (if used)
  - Test fan-out mode (if used)

### Optional Improvements

- [ ] **Adopt new fan-out syntax** (clarity improvement)
  ```python
  # OLD (still works):
  .publishes(Task, Task, Task)

  # NEW (clearer):
  .publishes(Task, fan_out=3)
  ```

- [ ] **Consider context providers** (new feature)
  ```python
  # Add filtered context if needed
  flock = Flock(context_provider=FilteredContextProvider(...))
  ```

---

## 📝 Examples Status

### Summary

| Category | Count | Status | Fix Needed |
|----------|-------|--------|------------|
| **CLI Examples** | 15 | ✅ Fixed | None |
| **Dashboard Examples** | 16 | ✅ Fixed | None |
| **Claude's Workshop** | 10 | ✅ Fixed | None |
| **Misc Examples** | 5 | ✅ Fixed | None |
| **Pattern Examples** | 5 | ✅ Fixed | None |
| **TOTAL** | **51** | **✅ ALL FIXED** | **Complete** |

### Bulk Fix Command

```bash
# Fix all 51 examples in one command
cd /Users/ara/Projects/flock
find examples/ -name "*.py" -exec sed -i '' 's/from flock\.orchestrator import/from flock import/g' {} +

# Verify changes
git diff examples/ | grep "from flock" | head -20

# Test a few examples
python examples/01-cli/01_declarative_pizza.py
python examples/02-dashboard/05_mcp_and_tools.py
```

### Example Files by Directory

**`examples/01-cli/` (15 files)** - All need import fix
- 01_declarative_pizza.py
- 02_input_and_output.py
- 03_code_detective.py
- 04_input_and_output.py
- 05_mcp_and_tools.py
- 06_mcp_roots.py
- 07_web_detective.py
- 08_band_formation.py
- 09_debate_club.py
- 10_news_agency.py
- 11_tracing_detective.py
- 12_secret_agents.py
- 13_medical_diagnostics_joinspec.py
- 14_ecommerce_batch_processing.py
- 15_iot_sensor_batching.py

**`examples/02-dashboard/` (16 files)** - All need import fix
- 01_declarative_pizza.py
- 02_input_and_output.py
- 03_code_detective.py
- 04_input_and_output.py
- 05_mcp_and_tools.py
- 06_mcp_roots.py
- 07_web_detective.py
- 08_band_formation.py
- 09_debate_club.py
- 10_news_agency.py
- 11_tracing_detective.py
- 12_secret_agents.py
- 13_medical_diagnostics_joinspec.py
- 14_ecommerce_batch_processing.py
- 15_iot_sensor_batching.py
- 16_news_batching.py

**`examples/03-claudes-workshop/` (10 files)** - All need import fix
- lesson_01_code_detective.py
- lesson_02_band_formation.py
- lesson_03_web_detective.py
- lesson_04_debate_club.py
- lesson_05_tracing_detective.py
- lesson_06_secret_agents.py
- lesson_07_news_agency.py
- lesson_08_the_matchmaker.py
- lesson_09_the_batch_optimizer.py
- lesson_10_the_smart_factory.py

**`examples/04-misc/` (5 files)** - All need import fix
- 01_persistent_pizza.py
- 02-dashboard-edge-cases.py
- 03-scale-test-100-agents.py
- 04_persistent_pizza_dashboard.py
- 05_lm_studio.py

**`examples/00-patterns/` (5 files)** - All need import fix
- 01-single_publish.py
- 02-multi_publish.py
- 03-multi-artifact-multi-publish.py
- 04-fan-out.py
- 05-multi-fan-out.py

---

## 🎯 Impact Analysis

### Critical (Affects All Users)

1. **Import Path Change** 🔴 HIGH
   - **Impact:** ALL 51 examples broken
   - **Fix Time:** 2 minutes (bulk sed command)
   - **Risk:** LOW (simple find-replace)

### Medium (Affects Custom Code)

2. **Component Imports** 🟡 MEDIUM
   - **Impact:** Code importing `flock.components` directly
   - **Fix Time:** 5-10 minutes per file
   - **Risk:** LOW (compiler catches errors)

3. **Engine API Changes** 🟡 MEDIUM
   - **Impact:** Custom engines with `evaluate_batch()`/`evaluate_fanout()`
   - **Fix Time:** 15-30 minutes per engine
   - **Risk:** MEDIUM (requires understanding new pattern)

### Low (Optional Features)

4. **Fan-Out Syntax** 🟢 LOW
   - **Impact:** Aesthetic improvement only
   - **Fix Time:** Optional
   - **Risk:** ZERO (old syntax still works)

5. **Context Providers** 🟢 LOW
   - **Impact:** New feature, not required
   - **Fix Time:** N/A (opt-in)
   - **Risk:** ZERO (backward compatible)

---

## 📚 Documentation Updates Needed

### High Priority

1. **Quick Start Guide**
   - Update import statements
   - Update all code examples
   - Add migration note at top

2. **API Reference**
   - Update `Flock` import path
   - Document new engine API
   - Add context provider docs

3. **Examples README**
   - Add migration notice
   - Link to this document
   - Provide bulk fix command

### Medium Priority

4. **Pattern Guides**
   - Update fan-out examples
   - Add engine migration guide
   - Add context provider guide

5. **Architecture Docs**
   - Update module diagrams
   - Document new structure
   - Explain refactoring benefits

### Low Priority

6. **Contributing Guide**
   - Update module structure
   - Update component paths
   - Add refactoring notes

---

## 🚀 Rollout Plan

### Phase 1: Fix Critical Issues (1 hour)

1. **Fix all 51 examples** (2 minutes)
   ```bash
   find examples/ -name "*.py" -exec sed -i '' 's/from flock\.orchestrator import/from flock import/g' {} +
   ```

2. **Test examples** (30 minutes)
   ```bash
   # Test representative samples
   python examples/01-cli/01_declarative_pizza.py
   python examples/02-dashboard/13_medical_diagnostics_joinspec.py
   python examples/00-patterns/04-fan-out.py
   ```

3. **Commit fixes** (5 minutes)
   ```bash
   git add examples/
   git commit -m "fix: Update examples to use new import paths (from flock import Flock)"
   ```

### Phase 2: Update Documentation (2-3 hours)

1. Update Quick Start (30 min)
2. Update API Reference (30 min)
3. Create migration guide (60 min)
4. Update README (30 min)

### Phase 3: Announce Changes (30 minutes)

1. Create CHANGELOG entry
2. Add migration notes to README
3. Update release notes
4. Notify users (if applicable)

---

## ✨ Summary

### Breaking Changes

| Change | Impact | Fix Complexity | Backward Compatible |
|--------|--------|----------------|---------------------|
| Import path (`flock.orchestrator` → `flock`) | 🔴 HIGH | ✅ TRIVIAL | ❌ NO |
| Component paths | 🟡 MEDIUM | ✅ EASY | ⚠️ PARTIAL |
| Engine API | 🟡 MEDIUM | 🟡 MODERATE | ❌ NO |
| Fan-out syntax | 🟢 LOW | ✅ TRIVIAL | ✅ YES |
| Context providers | 🟢 NONE | ✅ TRIVIAL | ✅ YES |
| MCP API | 🟢 NONE | ✅ NONE | ✅ YES |
| Subscription API | 🟢 NONE | ✅ NONE | ✅ YES |

### Action Items

**Immediate (Before Release):**
- [x] Document all breaking changes (THIS FILE)
- [x] Fix all 51 examples (2 min bulk sed) - ✅ COMPLETE 2025-10-19
- [x] Test fixed examples (30 min) - ✅ COMPLETE 2025-10-19
- [x] Update Quick Start docs (30 min) - ✅ COMPLETE 2025-10-19 (README, AGENTS.md, CONTRIBUTING.md)
- [ ] Create CHANGELOG entry (15 min)

**Short Term (With Release):**
- [ ] Update API reference docs
- [ ] Create migration guide
- [ ] Update README with migration notes
- [ ] Announce breaking changes

**Long Term (Post-Release):**
- [ ] Create engine migration guide
- [ ] Add context provider tutorial
- [ ] Update architecture docs
- [ ] Create video walkthrough (if applicable)

---

**Last Updated:** 2025-10-19
**Document Version:** 1.1
**Refactoring Phase:** 7 (90% Complete - Examples Fixed + Docs Updated)
