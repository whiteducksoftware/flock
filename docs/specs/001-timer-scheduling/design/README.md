# Timer-Based Agent Scheduling - Design Documentation

**Feature Status:** ✅ Design Complete | 🚧 Implementation Pending

---

## 📋 **Overview**

This directory contains the complete design documentation for **timer-based agent scheduling** in Flock - enabling agents to execute periodically or at specific times without requiring artifact triggers.

**Target Release:** v0.6.0

---

## 📁 **Documentation Files**

### **1. DESIGN.md** (Main Design Document) ⭐
**Comprehensive design specification including:**
- Architecture overview and integration points
- Complete API design with fluent builder pattern
- Implementation details for all components
- Real-world usage examples
- Edge cases and considerations
- Future enhancement roadmap
- Success criteria and validation rules

**Start here** for complete understanding of the feature.

### **2. API_EXAMPLES.md** (Quick Reference)
**Practical code examples covering:**
- Basic periodic execution
- Scheduled execution (daily, one-time)
- Timer + context filtering patterns
- Multi-type context aggregation
- Real-world use cases (health monitoring, reports, cleanup)
- Complete multi-agent workflow examples
- Quick reference tables

**Use this** for quick copy-paste examples during implementation.

### **3. IMPLEMENTATION_CHECKLIST.md** (Execution Plan)
**Detailed implementation tasks organized by phase:**
- Phase 1: Core infrastructure (data models, builder API)
- Phase 2: Timer component implementation
- Phase 3: Testing strategy (unit, integration, performance)
- Phase 4: Documentation (guides, tutorials, examples)
- Phase 5: Polish and release
- Acceptance criteria and success metrics
- Timeline estimates

**Use this** to track implementation progress.

### **4. TEST_EXAMPLES.md** (Test Guidance)
**Comprehensive test examples:**
- Unit tests (ScheduleSpec, TimerComponent, AgentContext)
- Integration tests (scheduled agent execution, context filtering)
- Performance tests (100+ concurrent timers)
- Complete workflow tests
- Test coverage goals (>90%)

**Use this** for TDD (test-driven development).

---

## 🎯 **Design Summary**

### **Core Concept**

Scheduled agents execute on **timer triggers** rather than artifact triggers:

```python
# Traditional artifact-triggered agent
agent = flock.agent("processor").consumes(Order).publishes(Receipt)
# Triggered when Order artifact published

# NEW: Timer-triggered agent
agent = flock.agent("health").schedule(every=timedelta(seconds=30)).publishes(HealthStatus)
# Triggered every 30 seconds automatically
```

### **Key Features**

✅ **Fluent API** - `.schedule()` method integrates seamlessly with existing builder pattern
✅ **Artifact-Driven** - Timers publish `TimerTick` artifacts internally (maintains architecture)
✅ **Context Filtering** - `.consumes()` filters blackboard context (not trigger)
✅ **Flexible Scheduling** - Supports intervals, daily times, one-time execution
✅ **Production-Ready** - Graceful shutdown, backpressure handling, validation

### **Scheduling Modes**

| Mode | Syntax | Example |
|------|--------|---------|
| **Periodic** | `schedule(every=timedelta(...))` | Every 30 seconds |
| **Daily** | `schedule(at=time(...))` | Daily at 5 PM |
| **One-Time** | `schedule(at=datetime(...))` | Nov 1, 2025 at 9 AM |

### **Agent Input Semantics**

**Timer-triggered agents receive:**
- ❌ **No input artifact** (`ctx.artifacts = []`)
- ✅ **Timer metadata** (`ctx.timer_iteration`, `ctx.fire_time`, `ctx.trigger_type`)
- ✅ **Blackboard context** (`ctx.get_artifacts(Type)` - all artifacts, optionally filtered)

**This is different from normal triggers:**
- Normal: Agent receives the **specific artifact** that triggered it
- Timer: Agent receives **empty input**, accesses blackboard for context

---

## 🚀 **Implementation Roadmap**

### **Milestone 1: Core Infrastructure** (Week 1)
- `ScheduleSpec` dataclass
- `TimerTick` system artifact
- `AgentBuilder.schedule()` method
- `AgentContext` timer properties

### **Milestone 2: Timer Component** (Week 2)
- `TimerComponent` implementation
- Background timer tasks
- `on_initialize()` / `on_shutdown()` hooks
- Interval, daily, and one-time scheduling logic

### **Milestone 3: Testing** (Week 3)
- Unit tests (>95% coverage)
- Integration tests (>90% coverage)
- Performance tests (100+ concurrent timers)

### **Milestone 4: Documentation** (Week 4)
- User guide (`docs/guides/scheduling.md`)
- Tutorial (`docs/tutorials/scheduled-agents.md`)
- 5 example scripts (`examples/09-scheduling/`)
- Update `AGENTS.md`

### **Milestone 5: Release** (Week 5)
- Dashboard integration (optional)
- Version bump to 0.6.0
- Changelog and release notes

**Total Estimate:** 3-4 weeks (1 developer, full-time)

---

## 💡 **Design Highlights**

### **1. Elegant Fluent API**

```python
# Reads like natural language
agent = (
    flock.agent("health_monitor")
    .description("Monitors system health")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)
```

### **2. Context Filtering Power**

```python
# Timer fires every 5 minutes
# Agent ONLY sees ERROR-level logs
error_analyzer = (
    flock.agent("analyzer")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)
```

### **3. Maintains Artifact-Driven Architecture**

Under the hood, timers are just another artifact producer:
```
TimerComponent → Publishes TimerTick → Agent Subscription → Agent Execution
```

### **4. Production-Ready Design**

- ✅ Graceful shutdown (cancel timer tasks)
- ✅ Backpressure handling (`max_concurrency`)
- ✅ Validation (prevent invalid configs like schedule + batch)
- ✅ Context provider integration (visibility, filtering)
- ✅ Correlation IDs for tracing

---

## 🎯 **Quick Start Guide**

**For Implementers:**

1. **Read DESIGN.md** - Understand the complete architecture
2. **Review API_EXAMPLES.md** - See what users will write
3. **Follow IMPLEMENTATION_CHECKLIST.md** - Track progress phase-by-phase
4. **Write tests from TEST_EXAMPLES.md** - TDD approach
5. **Implement components** - Follow the design spec exactly
6. **Run examples** - Verify everything works end-to-end

**For Reviewers:**

1. Check design against Flock architecture principles
2. Verify API consistency with existing patterns
3. Validate edge case handling
4. Review test coverage plan
5. Approve or request changes

**For Users (after release):**

1. Read `docs/guides/scheduling.md` - User guide
2. Follow `docs/tutorials/scheduled-agents.md` - Step-by-step tutorial
3. Run examples from `examples/09-scheduling/` - Learn by doing
4. Check `API_EXAMPLES.md` in this directory - Quick reference

---

## ❓ **FAQ**

### **Q: Why not just use asyncio.create_task() with a loop?**

**A:** That's exactly what we do internally! But we provide:
- Declarative API (no boilerplate)
- Automatic lifecycle management (startup/shutdown)
- Integration with blackboard context
- Artifact-driven architecture (traceability, monitoring)
- Consistent fluent API

### **Q: What happens if agent execution is slower than timer interval?**

**A:** Executions queue up by default. Use `max_concurrency(1)` to limit:
```python
agent.schedule(every=timedelta(seconds=10)).max_concurrency(1)
```

### **Q: Can I combine timer trigger with artifact trigger?**

**A:** Not in v0.6.0 (dual-mode triggering is a future enhancement). Current design:
- **Timer trigger**: `.schedule()` only
- **Artifact trigger**: `.consumes()` only
- **Context filter**: `.schedule()` + `.consumes()` (consumes = filter, not trigger)

### **Q: How do timers interact with `run_until_idle()`?**

**A:** Timers keep the orchestrator busy. Use `serve()` instead:
```python
# ❌ This will never complete
await flock.run_until_idle()

# ✅ Use serve() for long-running orchestrators with timers
await flock.serve()
```

### **Q: Are timer states persisted across restarts?**

**A:** No in v0.6.0 (iteration counters reset). Persistent state is planned for v0.7.0.

---

## 📞 **Feedback & Questions**

**During Design Phase:**
- Open issues/discussions in GitHub
- Update design documents based on feedback
- Iterate until consensus reached

**During Implementation:**
- Track blockers in `IMPLEMENTATION_CHECKLIST.md`
- Update design if implementation reveals issues
- Maintain test coverage as you go

**After Release:**
- Gather user feedback from examples/tutorials
- Monitor GitHub issues for bugs/feature requests
- Plan v0.7.0 enhancements (cron, persistence, distributed)

---

## ✅ **Design Approval**

**Design Status:** ✅ Complete and ready for review

**Reviewers:**
- [ ] Architecture review (alignment with Flock principles)
- [ ] API review (fluent pattern consistency)
- [ ] Implementation review (technical feasibility)
- [ ] Documentation review (clarity, completeness)

**Approval Date:** _Pending_

**Implementation Start Date:** _After approval_

---

## 🎉 **Summary**

This design provides **elegant timer-based scheduling** that:
- Feels native to Flock's fluent API
- Maintains artifact-driven architecture
- Supports common scheduling patterns (periodic, daily, one-time)
- Enables powerful context filtering
- Handles production edge cases

**Next Steps:**
1. Review and approve design
2. Start implementation following `IMPLEMENTATION_CHECKLIST.md`
3. Ship v0.6.0 with timer scheduling! 🚀

---

**Last Updated:** 2025-10-30
**Design Version:** 1.0
**Target Release:** v0.6.0
