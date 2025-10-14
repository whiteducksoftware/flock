# Implementation Priority Guide: What to Do First

## 🎯 TL;DR Recommendation

**Do the OrchestratorComponent implementation FIRST**, integrating logging as you go (following the LOGGING_GUIDE.md). This gives you:

1. ✅ **Immediate value**: Cleaner orchestrator architecture
2. ✅ **Natural logging adoption**: Add logs while refactoring (easier than retrofitting)
3. ✅ **Validates logging strategy**: Real-world testing of logging patterns
4. ✅ **Production impact**: Both better architecture AND observability

---

## 🔍 Decision Factors

### Option A: OrchestratorComponent First (RECOMMENDED ✅)

**Rationale**:
- The 100+ line `_schedule_artifact` method is causing active pain NOW
- Logging makes the most sense when integrated during component refactoring
- You already have a complete implementation plan (Spec 004)
- Components will serve as logging exemplars for the rest of the codebase

**Timeline**: 2 weeks (40-60 hours)

**Deliverables**:
1. OrchestratorComponent architecture (Phases 1-7)
2. Logging integrated throughout (following LOGGING_GUIDE.md)
3. CircuitBreaker and Deduplication components with exemplary logging
4. Validated logging patterns for rest of codebase

**Risk**: Low (well-scoped, comprehensive plan, backward compatible)

---

### Option B: Framework-Wide Logging First

**Rationale**:
- Establish logging culture before major refactoring
- All modules get observability immediately
- Simpler changes (less risk)

**Problems**:
- ❌ Retrofitting logs into existing code is tedious
- ❌ No immediate architectural improvement
- ❌ Miss opportunity to integrate logging during refactoring
- ❌ Components are best logging exemplars, but they don't exist yet

**Timeline**: 3-4 weeks (20 hours spread thin)

**Risk**: Medium (widespread changes, might miss important log points)

---

### Option C: Parallel Execution

**Rationale**:
- Maximum speed
- Both improvements simultaneously

**Problems**:
- ❌ Merge conflicts (orchestrator.py touched by both)
- ❌ Split focus
- ❌ Harder to validate logging strategy

**Risk**: High (coordination overhead)

---

## ✅ RECOMMENDED APPROACH: OrchestratorComponent with Integrated Logging

### Phase-by-Phase Breakdown

#### **Week 1: Foundation + Circuit Breaker (Phases 1-5)**

**Phase 1: Base Classes** (4-6 hours)
```python
# Create: src/flock/orchestrator_component.py
# Add logger immediately:
from flock.logging.logging import get_logger
logger = get_logger("flock.component")

# OrchestratorComponent base class
# ScheduleDecision enum
# CollectionResult dataclass
```

**Logging Impact**: Establishes component logging pattern

---

**Phase 2: Orchestrator Integration** (2-4 hours)
```python
# Modify: src/flock/orchestrator.py
# Add component management:
def add_component(self, component: OrchestratorComponent) -> Self:
    self._components.append(component)
    self._components.sort(key=lambda c: c.priority)
    
    logger.info(
        f"Component added: name={component.name or component.__class__.__name__}, "
        f"priority={component.priority}, total_components={len(self._components)}"
    )
    return self
```

**Logging Impact**: First orchestrator logs (component management)

---

**Phase 3: Hook Runners** (8-12 hours)
```python
# Add 8 hook runner methods with comprehensive logging:
async def _run_before_schedule(...) -> ScheduleDecision:
    for component in self._components:
        logger.debug(f"Running on_before_schedule: component={comp_name}, agent={agent.name}")
        decision = await component.on_before_schedule(...)
        
        if decision == ScheduleDecision.SKIP:
            logger.info(f"Scheduling skipped by component: component={comp_name}, agent={agent.name}")
            return ScheduleDecision.SKIP
    return ScheduleDecision.CONTINUE
```

**Logging Impact**: Comprehensive hook execution logging

---

**Phase 4: Refactor _schedule_artifact** (8-12 hours)
```python
# Clean up _schedule_artifact using components:
async def _schedule_artifact(self, artifact: Artifact) -> None:
    if not self._components_initialized:
        await self._run_initialize()
    
    logger.debug(f"Scheduling artifact: type={artifact.type}, id={artifact.id}")
    
    # Use component hooks instead of inline logic
    artifact = await self._run_artifact_published(artifact)
    if artifact is None:
        logger.debug("Artifact blocked by component")
        return
    # ... rest using component hooks ...
```

**Logging Impact**: Orchestrator scheduling decisions now logged

---

**Phase 5: CircuitBreakerComponent** (4-6 hours)
```python
class CircuitBreakerComponent(OrchestratorComponent):
    async def on_before_schedule(...) -> ScheduleDecision:
        count = self._iteration_counts.get(agent.name, 0)
        
        if count >= self.max_iterations:
            logger.warning(f"Circuit breaker TRIPPED: agent={agent.name}, count={count}")
            return ScheduleDecision.SKIP
        
        if count >= self.max_iterations * 0.95:
            logger.warning(f"Circuit breaker at 95%: agent={agent.name}, count={count}/{self.max_iterations}")
        
        logger.debug(f"Circuit breaker check: agent={agent.name}, count={count}/{self.max_iterations}")
        self._iteration_counts[agent.name] = count + 1
        return ScheduleDecision.CONTINUE
```

**Logging Impact**: Exemplary component logging pattern established

---

#### **Week 2: Deduplication + Integration (Phases 6-7)**

**Phase 6: DeduplicationComponent** (4-6 hours)
```python
class DeduplicationComponent(OrchestratorComponent):
    async def on_before_schedule(...) -> ScheduleDecision:
        key = (str(artifact.id), agent.name)
        
        if key in self._processed:
            logger.info(f"Deduplication BLOCKED: artifact_id={artifact.id}, agent={agent.name}")
            return ScheduleDecision.SKIP
        
        self._processed.add(key)
        logger.debug(f"Deduplication check passed: artifact_id={artifact.id}, agent={agent.name}")
        return ScheduleDecision.CONTINUE
```

**Logging Impact**: Second exemplary component

---

**Phase 7: Integration + Validation** (8-12 hours)
- Auto-add default components
- Run full test suite (743 tests)
- Validate backward compatibility
- Performance benchmarks
- Document logging patterns for other modules

**Logging Impact**: Validated logging strategy ready for framework-wide rollout

---

### 🎯 After OrchestratorComponent: Framework-Wide Logging

**With validated patterns from components**, roll out logging to rest of framework:

#### **Week 3-4: High-Priority Modules**

Following CircuitBreaker/Deduplication examples:

1. **Store (`store.py`)** - 2 hours
   ```python
   logger = get_logger("flock.store")
   
   async def publish(self, artifact: Artifact) -> None:
       logger.debug(f"Storing artifact: id={artifact.id}, type={artifact.type}")
       # ... store logic ...
       logger.info(f"Artifact stored: id={artifact.id}")
   ```

2. **Subscription (`subscription.py`)** - 1 hour
   ```python
   logger = get_logger("flock.subscription")
   
   def matches(self, artifact: Artifact) -> bool:
       result = artifact.type in self.types
       logger.debug(f"Subscription match: artifact_type={artifact.type}, matches={result}")
       return result
   ```

3. **Visibility (`visibility.py`)** - 1 hour
   ```python
   logger = get_logger("flock.visibility")
   
   def allows(self, agent: AgentIdentity) -> bool:
       result = agent.name in self.agents
       logger.debug(f"Visibility check: agent={agent.name}, allowed={result}")
       return result
   ```

4. **Registry (`registry.py`)** - 1 hour
5. **Runtime (`runtime.py`)** - 1 hour
6. **Correlation/Batch Engines** - 2 hours

**Total**: ~8 hours to add logging to 6 critical modules

---

## 📊 Value Delivery Timeline

### Week 1 (OrchestratorComponent Foundation)
- ✅ Cleaner orchestrator architecture
- ✅ Component system established
- ✅ Hook-based execution model
- ✅ Logging patterns validated

**Value**: 60% of architectural improvement

### Week 2 (OrchestratorComponent Complete)
- ✅ Full component refactoring
- ✅ Backward compatibility preserved
- ✅ 743 tests passing
- ✅ Performance validated
- ✅ Two exemplary logged components

**Value**: 100% of architectural improvement + 20% of logging improvement

### Week 3-4 (Framework-Wide Logging)
- ✅ Logging in store, subscription, visibility, registry
- ✅ Complete observability
- ✅ Production debugging enabled

**Value**: 100% of logging improvement

---

## 🎯 Success Metrics (End of Week 2)

### Architecture
- [ ] OrchestratorComponent base class implemented
- [ ] 8 hook runner methods working
- [ ] CircuitBreakerComponent migrated
- [ ] DeduplicationComponent migrated
- [ ] `_schedule_artifact` reduced from 138 to <50 lines
- [ ] ALL existing tests passing (743 tests)
- [ ] Performance overhead <5%

### Logging
- [ ] Component lifecycle logged (initialize, hooks, shutdown)
- [ ] Scheduling decisions logged (SKIP, DEFER, CONTINUE)
- [ ] Circuit breaker state logged (counts, warnings, trips)
- [ ] Deduplication logged (blocks, passes)
- [ ] Hook execution logged (entry, results, errors)
- [ ] Structured format validated (key=value pairs)
- [ ] Performance overhead <1ms per log

---

## 🚀 Immediate Next Steps (Right Now)

### 1. Create Feature Branch
```bash
git checkout -b feature/orchestrator-component-with-logging
```

### 2. Start Phase 1 (Base Classes) - 4-6 hours

**Tasks**:
- [ ] Read Spec 004 design doc completely
- [ ] Read LOGGING_GUIDE.md completely  
- [ ] Create `src/flock/orchestrator_component.py`
- [ ] Implement ScheduleDecision enum
- [ ] Implement CollectionResult dataclass
- [ ] Implement OrchestratorComponentConfig class
- [ ] Implement OrchestratorComponent base class
- [ ] Add logger: `logger = get_logger("flock.component")`
- [ ] Write tests in `tests/test_orchestrator_component.py`
- [ ] Run tests: `pytest tests/test_orchestrator_component.py -v`

**Definition of Done**:
- [ ] All Phase 1 tests passing
- [ ] Code coverage >80%
- [ ] Ruff linting passes
- [ ] No placeholder code

### 3. Commit Checkpoint
```bash
git add src/flock/orchestrator_component.py tests/test_orchestrator_component.py
git commit -m "Phase 1: OrchestratorComponent base classes with logging"
```

### 4. Continue to Phase 2
Repeat for Phases 2-7, committing after each phase.

---

## 🔥 Why This Approach Wins

1. **Single Focus**: One major refactoring with integrated logging
2. **Natural Integration**: Logging added while code is being written (easier than retrofitting)
3. **Validated Patterns**: Components become logging exemplars for rest of framework
4. **Immediate Value**: Better architecture + observability in 2 weeks
5. **Risk Management**: Comprehensive test suite catches regressions
6. **Momentum**: Success breeds success - team sees value quickly

---

## ❓ FAQ

**Q: Why not logging first?**  
A: Retrofitting logs is tedious and error-prone. Better to integrate during refactoring when code is already being touched.

**Q: What if OrchestratorComponent takes longer than 2 weeks?**  
A: The plan has buffer built in (40-60 hour range). Each phase can be committed independently. Even partial completion delivers value.

**Q: What about existing logging in orchestrator.py?**  
A: Keep it! Enhance it with component-specific logs. The orchestrator already has `self._logger`.

**Q: Should I add logging to ALL modules during OrchestratorComponent work?**  
A: No! Focus on components only. Use Week 3-4 for framework-wide rollout with validated patterns.

**Q: What if tests fail in Phase 4 (refactoring)?**  
A: That's why Phase 4 is last and has the most test coverage. The design preserves backward compatibility, so existing tests should pass.

---

## 📋 Decision Summary

| Approach | Timeline | Risk | Value | Recommendation |
|----------|----------|------|-------|----------------|
| **OrchestratorComponent + Logging** | 2 weeks | Low | High | ✅ **DO THIS** |
| Framework Logging First | 3-4 weeks | Medium | Medium | ❌ Skip |
| Parallel Execution | 2 weeks | High | High | ❌ Too risky |

---

## 🎉 Final Recommendation

**START IMMEDIATELY** with OrchestratorComponent implementation (Phase 1), following:
1. `docs/specs/004-orchestrator-component/PLAN.md` for structure
2. `docs/specs/004-orchestrator-component/LOGGING_GUIDE.md` for logging

**After Week 2**, roll out logging framework-wide using validated patterns.

This maximizes value delivery, minimizes risk, and ensures logging patterns are proven before widespread adoption.

---

**Ready to start? Begin with Phase 1 - Base Classes!** 🚀

*See: `docs/specs/004-orchestrator-component/PLAN.md` for detailed implementation steps*
