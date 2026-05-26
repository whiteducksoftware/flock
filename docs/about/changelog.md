---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Changelog 📝

All notable changes to **Flock** will be documented in this file.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Core concepts & component documentation.
- Placeholder replacement across docs.
- Documentation improvements and typo fixes.

---

## [0.4.52] – 2025-05-30

### Added
- Package versioning updates and dependency improvements.

### Fixed
- Various bug fixes and stability improvements.

---

## [0.4.51] – 2025-05-24

### Added
- Enhanced error logging as default log level.
- Zendesk article count feature.
- Zendesk tools as MCP server.
- Configurable protocol support.

### Fixed
- Removed init definitions for tools to avoid requiring all tool dependencies.
- Chat in sidebar functionality.

---

## [0.4.5] – 2025-05-21 "MCP Integration"

### Added
- **Model Context Protocol (MCP) Support**: Declaratively connect to thousands of different tools.
- MCP server creation with `FlockFactory.create_mcp_server()`.
- Support for WebSocket, SSE, and STDIO transport protocols.
- Tool discovery and integration through MCP servers.
- Enhanced server management and client handling.

### Fixed
- OTLPSpanExporter crash issues.
- Literal data type handling in Flock agents.
- Various serialization and deserialization improvements.

---

## [0.4.3] – 2025-05-21

### Added
- High-level changelog documentation in README.
- Enhanced REST API deployment features.

### Changed
- Updated documentation structure and content.

---

## [0.4.1] – 2025-05-21 "Magpie"

### Added
- **Magpie** release branding and logo.
- Enhanced CLI messaging with release information.

### Changed
- Updated version display in CLI helper.
- Improved UI design elements.

---

## [0.4.0] – 2025-04-30 "Magpie" 🐤

### Added
- **REST API Deployment**: Deploy Flock agents as scalable REST API endpoints with `flock.serve()`.
- **Web UI**: Test and interact with Flock agents directly in browser with integrated web interface.
- **CLI Tool**: Manage configurations, run agents, and inspect results from terminal.
- **Enhanced Serialization**: Share, deploy, and run Flocks from YAML files with complete portability.
- **Batch and Evaluation Modes**: Process multiple inputs and benchmark agents against Q/A pairs.
- **First-Class Temporal Integration**: Production-grade workflows with retry policies and timeout control.
- **@flockclass Hydrator**: Turn any Pydantic model into a self-hydrating agent.
- Custom endpoint support with `FlockEndpoint` for business logic integration.
- Chat functionality and UI modes (standalone chat, agent execution).
- Shareable links with frozen agent configurations.
- Direct feedback system for issue reproduction.

### Changed
- Major architecture improvements for production deployment.
- Enhanced documentation with comprehensive guides and examples.
- Improved serialization system with type safety.

---

## [0.3.0] – 2025-02-24 "Hummingbird"

### Added
- **Redesigned Core Architecture**: Modular and flexible design with Modules and Evaluators.
- **FlockFactory**: Pre-configured agents for rapid development.
- **Module System**: Lifecycle hooks (`initialize`, `pre_evaluate`, `post_evaluate`, `terminate`).
- **Evaluator System**: `DeclarativeEvaluator` and `NaturalLanguageEvaluator`.
- **Built-in Modules**: `MemoryModule`, `OutputModule`, and `MetricsModule`.
- **CLI Interface**: Load flocks, theme builder, settings, advanced mode, and web server.
- Release notes system with CLI integration.

### Changed
- `Flock` class initialization updated to include `init_console`.
- Improved modularity and extensibility throughout the framework.

---

## [0.2.1] – 2025-01-15

### Added
- Initial public release to PyPI.
- Declarative agent framework foundation.
- Basic Temporal execution support.
- Core tools: `get_web_content_as_markdown`, Azure Blob helper, markdown utilities.

---

*Older history prior to open-source release is maintained internally.*
