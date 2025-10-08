---
title: Changelog
description: Recent changes, updates, and release history for Flock Flow
tags:
  - changelog
  - releases
  - history
search:
  boost: 1.2
---

# 📝 Changelog

Track Flock Flow's evolution from initial release to enterprise-ready orchestration framework.

**Current Version:** v0.5.0 Beta 60 (October 2025)
**Next Major Release:** v1.0.0 (Q4 2025)

---

## 🎯 Release Strategy

- **v0.5.x** - Production-ready core with beta features
- **v1.0.0** - Enterprise features (Q4 2025) - See **[Roadmap](roadmap.md)**

---

## 📅 Recent Changes (October 2025)

### October 8, 2025 - Documentation Transformation

**v0.5.0b60** - Major documentation overhaul

#### ✨ Features
- **Phase 3: Tutorials & Examples** ([2f81e21](https://github.com/whiteducksoftware/flock/commit/2f81e21))
  - 4 comprehensive tutorials (multi-agent, conditional routing, advanced patterns, dashboards)
  - 2 in-depth guides (best practices, testing strategies)
  - Production-ready examples with real-world patterns
  - ~3,300 lines of new documentation

- **Phase 2: API Documentation** ([019b7dc](https://github.com/whiteducksoftware/flock/commit/019b7dc))
  - Complete API reference transformation
  - Type-safe examples with validation
  - Enhanced getting-started guides

- **Phase 1: Core Documentation** ([a8a4599](https://github.com/whiteducksoftware/flock/commit/a8a4599))
  - Restructured documentation architecture
  - Improved navigation and search
  - Better onboarding experience

#### 📊 Documentation
- **Comprehensive Mermaid Diagrams** ([986ad3f](https://github.com/whiteducksoftware/flock/commit/986ad3f))
  - Agent lifecycle state diagram
  - Orchestrator execution flow (14 steps)
  - Blackboard pub-sub pattern
  - Type-driven auto-chaining visualization
  - Visibility controls (all 5 types)
  - Component hooks flowchart

- **Improved README** ([408de27](https://github.com/whiteducksoftware/flock/commit/408de27))
  - Fixed typos and improved clarity
  - Expanded traditional prompt example
  - Better real-world context

### October 8, 2025 - Dashboard & Layout Improvements

**v0.5.0b57** - Enhanced visualization and user experience

#### ✨ Features
- **Multi-Layout Graph Visualization** ([36a5147](https://github.com/whiteducksoftware/flock/commit/36a5147))
  - 5 graph layout algorithms (hierarchical, force-directed, circular, grid, radial)
  - Auto-layouting improvements
  - Better dependency graph readability

#### 🐛 Fixes
- **SQL Security** ([adcda5a](https://github.com/whiteducksoftware/flock/commit/adcda5a))
  - Refactored DuckDB query to properly suppress Bandit warnings
  - No false positives on SQL injection detection

#### 📊 Documentation
- **AGENTS.md Enhancements**
  - Added critical PR base branch requirements ([b64ad40](https://github.com/whiteducksoftware/flock/commit/b64ad40))
  - Added critical versioning guide ([e8341e9](https://github.com/whiteducksoftware/flock/commit/e8341e9))

---

## 🔭 October 7, 2025 - Production Observability

**v0.5.0b54** - Enterprise-grade tracing and monitoring

### ✨ Features
- **Production-Ready Trace Viewer** ([2f63193](https://github.com/whiteducksoftware/flock/commit/2f63193))
  - 7 viewing modes: Timeline, RED metrics, Dependencies, SQL analytics, Artifacts, JSON, Raw
  - OpenTelemetry distributed tracing
  - DuckDB trace storage (AI-queryable)
  - Real-time WebSocket streaming
  - Service filtering and CSV export
  - Full I/O capture with JSON viewer

- **Unified Trace Dashboard** ([df6c1d3](https://github.com/whiteducksoftware/flock/commit/df6c1d3))
  - RED metrics (Rate, Errors, Duration)
  - Dependency graph visualization
  - Comprehensive observability

- **Auto-Tracing** ([b64e8bd](https://github.com/whiteducksoftware/flock/commit/b64e8bd))
  - Automatic instrumentation
  - Zero-configuration tracing

### 📊 Documentation
- **Comprehensive Tracing Guide** ([21df104](https://github.com/whiteducksoftware/flock/commit/21df104))
  - Effective tracing usage patterns
  - Debugging workflows
  - Performance analysis

### 🐛 Fixes
- **MCP Caching** ([aab5840](https://github.com/whiteducksoftware/flock/commit/aab5840))
  - Fixed ignored args in MCP caching
- **Frontend Build** ([739d759](https://github.com/whiteducksoftware/flock/commit/739d759))
  - Fixed frontend build package issues
- **CI Quality Gates** ([dcbc456](https://github.com/whiteducksoftware/flock/commit/dcbc456))
  - Fixed Flock 0.5 quality gates and CI
  - Fixed test npm order ([9925141](https://github.com/whiteducksoftware/flock/commit/9925141))
- **Dashboard Streaming** ([39636da](https://github.com/whiteducksoftware/flock/commit/39636da))
  - Fixed true concurrency in dashboard streaming
- **OpenTelemetry Dependencies** ([4a08956](https://github.com/whiteducksoftware/flock/commit/4a08956))
  - Fixed OTEL dependency issues

---

## 🚀 October 6, 2025 - Flock 0.5 Polish

**v0.5.0b43** - Major release preparation

### ✨ Features
- **README Overhaul** ([20425c0](https://github.com/whiteducksoftware/flock/commit/20425c0), [edb87da](https://github.com/whiteducksoftware/flock/commit/edb87da))
  - Updated with Flock 0.5 features
  - New banner image (800px width)
  - Better visual hierarchy

- **Dashboard Auto-Install** ([39bb86d](https://github.com/whiteducksoftware/flock/commit/39bb86d))
  - Fixed npm install when calling `.serve()`
  - Automatic frontend dependency management

### 📊 Documentation
- **Images & Layout** ([98d6326](https://github.com/whiteducksoftware/flock/commit/98d6326), [53280d4](https://github.com/whiteducksoftware/flock/commit/53280d4))
  - Added visual assets
  - Improved layout and formatting

---

## 🎨 October 3-6, 2025 - Flock Flow Migration

**v0.5.0b40** - Project renaming and architecture improvements

### ✨ Features
- **Flock Flow Branding** ([3eface3](https://github.com/whiteducksoftware/flock/commit/3eface3))
  - Migrated to "Flock Flow" branding
  - Updated all references and documentation

- **N-Shot Learning** ([5e07b54](https://github.com/whiteducksoftware/flock/commit/5e07b54), [c0ff4ea](https://github.com/whiteducksoftware/flock/commit/c0ff4ea))
  - Added n-shot learning example
  - Added ExampleUtilityComponent for n-shot learning

- **Feedback Component** ([4bc17a7](https://github.com/whiteducksoftware/flock/commit/4bc17a7), [f9a49a1](https://github.com/whiteducksoftware/flock/commit/f9a49a1))
  - Phase 4: Integration with Agent Factory
  - Phase 3: Component Lifecycle Integration
  - Complete FeedbackUtilityComponent class structure
  - FeedbackUtilityConfig with all configuration fields

### 🔧 Refactoring
- **Code Cleanup** ([c185339](https://github.com/whiteducksoftware/flock/commit/c185339), [4ac59e1](https://github.com/whiteducksoftware/flock/commit/4ac59e1))
  - Major refactoring for cleaner architecture
  - Improved code organization

---

## 🛠️ September 29-30, 2025 - Examples & Fixes

**v0.5.0b38** - Enhanced examples and bug fixes

### ✨ Features
- **DSPy Integration** ([680c768](https://github.com/whiteducksoftware/flock/commit/680c768), [1fd949f](https://github.com/whiteducksoftware/flock/commit/1fd949f))
  - Streaming status support
  - Streaming tool messages
  - Streaming object generation

- **More Examples** ([8ad4f26](https://github.com/whiteducksoftware/flock/commit/8ad4f26), [8944ee5](https://github.com/whiteducksoftware/flock/commit/8944ee5))
  - Added multiple production examples
  - Better example coverage

### 🐛 Fixes
- **Model Defaults** ([a54c729](https://github.com/whiteducksoftware/flock/commit/a54c729))
  - Fixed default model configuration in examples
- **MCP Whitelist** ([29a880f](https://github.com/whiteducksoftware/flock/commit/29a880f))
  - Fixed whitelist bug in MCP integration
- **Dashboard Refresh** ([2698947](https://github.com/whiteducksoftware/flock/commit/2698947))
  - Smaller, more efficient refresh cycles

---

## 📦 Version 0.4.x (Legacy Releases)

### v0.4.52 - v0.4.51
- Foundation work for 0.5.0 migration
- Core architecture improvements

### v0.4.5 - v0.4.3
- Early dashboard features
- Basic tracing support

### v0.4.1
- Initial blackboard implementation
- First subscription system

---

## 🔮 What's Next?

See our **[Roadmap](roadmap.md)** for upcoming features:

### Flock 1.0 (Q4 2025)
- ✅ Enterprise Persistence (Redis, PostgreSQL)
- ✅ Advanced Retry & Error Handling
- ✅ Aggregation Patterns (map-reduce, voting, consensus)
- ✅ Kafka Event Backbone (replay, time-travel)
- ✅ Kubernetes-Native Deployment (Helm charts)
- ✅ Authentication & Authorization (OAuth, RBAC)
- ✅ Human-in-the-Loop Approval Patterns
- ✅ Fan-Out / Fan-In Patterns
- ✅ Time-Based Scheduling (cron, sliding windows)

---

## 📊 Project Stats (October 2025)

- **Test Coverage:** 77.65% overall (743 tests)
- **Critical Path Coverage:** 86-100% (orchestrator, subscription, agent)
- **Documentation:** 50+ pages (guides, tutorials, API reference)
- **Examples:** 15+ production-ready examples
- **Contributors:** Growing community

---

## 🤝 Contributing

Want to be part of the changelog? Check out our **[Contributing Guide](contributing.md)**.

Every contribution counts:
- Bug fixes
- Feature additions
- Documentation improvements
- Example contributions
- Community support

---

## 📞 Questions?

- **Issues:** [GitHub Issues](https://github.com/whiteducksoftware/flock/issues)
- **Discussions:** [GitHub Discussions](https://github.com/whiteducksoftware/flock/discussions)
- **Documentation:** [docs.flock.whiteduck.de](https://docs.flock.whiteduck.de)

---

**Last Updated:** October 8, 2025
**Format:** [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
**Versioning:** [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

**Related:**
- **[Roadmap](roadmap.md)** - See what's coming next
- **[Contributing](contributing.md)** - Help build the future
- **[Getting Started](../getting-started/installation.md)** - Start building today
