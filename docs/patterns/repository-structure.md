# Flock-Flow Repository Structure Analysis

## Overview

This document provides a comprehensive structural analysis of the Flock-Flow repository, detailing the organization patterns, navigation conventions, and architectural layout that help agents understand the project structure efficiently.

## Project Architecture

**Flock-Flow** is a Python-based AI agent framework with a TypeScript/React frontend dashboard, implementing the blackboard pattern for agent coordination. The project follows a mixed monorepo structure with clear separation between Python backend and frontend components.

## Directory Structure

```
flock-flow/
├── 📁 src/flock/          # Main Python package (backend)
├── 📁 frontend/                # React/TypeScript frontend dashboard
├── 📁 tests/                   # Comprehensive test suite
├── 📁 docs/                    # Documentation and analysis
├── 📁 examples/                # Example implementations
├── 📁 scripts/                 # Build and utility scripts
├── 📁 .claude-flow/            # Claude Flow coordination metrics
├── 📁 .claude/                 # Claude Code configuration
├── 📁 .vscode/                 # VS Code settings
├── 📁 .devcontainer/           # Development container config
├── 📄 pyproject.toml           # Python project configuration
├── 📄 package.json             # Frontend dependencies (in frontend/)
├── 📄 uv.lock                  # Python dependency lock file
├── 📄 requirements.txt         # Python requirements
└── 📄 README.md                # Project documentation
```

## Core Python Package Structure (`src/flock/`)

### Main Module Files
- **`__init__.py`** (332 bytes) - Package initialization with exports
- **`agent.py`** (25KB) - Core agent implementation
- **`orchestrator.py`** (24KB) - Main orchestration logic
- **`components.py`** (5.7KB) - Shared components
- **`service.py`** (5KB) - Service layer
- **`runtime.py`** (4.9KB) - Runtime management
- **`registry.py`** (4.8KB) - Component registry
- **`cli.py`** (2.2KB) - Command-line interface
- **`artifacts.py`** (2.2KB) - Artifact management
- **`store.py`** (1.9KB) - Data store abstraction
- **`subscription.py`** (3KB) - Event subscription system
- **`visibility.py`** (2.9KB) - Visibility controls
- **`utilities.py`** (11.8KB) - Utility functions
- **`examples.py`** (3.4KB) - Usage examples

### Subdirectories

#### 📁 `api/` - API Layer
External API interfaces and HTTP endpoints.

#### 📁 `core/` - Core Infrastructure
- **`logging/`** - Centralized logging configuration

#### 📁 `dashboard/` - Real-time Dashboard (13KB total)
- **`collector.py`** (10.6KB) - Data collection service
- **`service.py`** (19.7KB) - Dashboard web service
- **`websocket.py`** (9KB) - WebSocket handler
- **`launcher.py`** (8.5KB) - Dashboard launcher
- **`events.py`** (5.1KB) - Event handling
- **`static/`** - Static web assets

#### 📁 `engines/` - AI/LLM Engines
Different AI engine implementations and adapters.

#### 📁 `helper/` - Helper Utilities
Shared helper functions and utilities.

#### 📁 `logging/` - Logging System (11 subdirectories)
Comprehensive logging infrastructure with multiple handlers and formatters.

#### 📁 `mcp/` - Model Context Protocol (25.8KB total)
- **`client.py`** (25.9KB) - MCP client implementation
- **`config.py`** (15.8KB) - MCP configuration
- **`manager.py`** (9.7KB) - MCP manager
- **`tool.py`** (5.5KB) - MCP tool interface
- **`servers/`** - MCP server implementations
- **`types/`** - Type definitions
- **`util/`** - MCP utilities

#### 📁 `themes/` - UI Themes (338 items)
Extensive theme collection for UI customization.

#### 📁 `utility/` - Utility Modules
Additional utility functions and helpers.

## Frontend Structure (`frontend/`)

### Configuration Files
- **`package.json`** (1.2KB) - Node.js dependencies and scripts
- **`tsconfig.json`** - TypeScript configuration
- **`vite.config.ts`** - Vite build configuration
- **`vitest.config.ts`** - Test configuration

### Source Structure (`frontend/src/`)

#### 📁 `components/` - React Components
- **`common/`** - Shared UI components
- **`controls/`** - Control panel components
- **`details/` - Detail view components
- **`filters/` - Filter components
- **`graph/`** - Graph visualization components
  - **`expanded/`** - Expanded graph views
- **`layout/`** - Layout components
- **`modules/`** - Module-specific components
- **`settings/`** - Settings components

#### 📁 `hooks/` - React Hooks
Custom React hooks for state management and data fetching.

#### 📁 `services/` - Frontend Services
API client services and data management.

#### 📁 `store/` - State Management
Zustand-based state management stores.

#### 📁 `types/` - TypeScript Types
Type definitions for frontend data structures.

#### 📁 `utils/` - Frontend Utilities
Frontend-specific utility functions.

#### 📁 `test-utils/` - Testing Utilities
Test utilities and helpers.

#### 📁 `__tests__/` - Test Files
- **`integration/`** - Integration tests
- **`e2e/`** - End-to-end tests

## Test Structure (`tests/`)

### Test Categories
- **Unit Tests** - Direct module testing (20+ test files)
- **Integration Tests** (`tests/integration/`) - Component integration
- **Contract Tests** (`tests/contract/`) - API contract validation
- **E2E Tests** (`tests/e2e/`) - End-to-end testing

### Key Test Files
- **`test_agent.py`** (18KB) - Agent functionality tests
- **`test_orchestrator.py`** (18KB) - Orchestrator tests
- **`test_dashboard_api.py`** (21.6KB) - Dashboard API tests
- **`test_dashboard_collector.py`** (18.4KB) - Dashboard collector tests
- **`test_dspy_streaming_events.py`** (12.1KB) - Streaming event tests
- **`test_components.py`** (6.4KB) - Component tests
- **`test_subscription.py`** (7.6KB) - Subscription tests
- **`test_visibility.py`** (6.7KB) - Visibility tests

## Documentation Structure (`docs/`)

### Analysis and Architecture
- **`analysis/`** - Technical analysis documents
- **`architecture/`** - Architecture documentation
- **`design/`** - Design documents
- **`specs/`** - Feature specifications
- **`extrernal/`** - External integrations

### Key Documents
- **`landscape_analysis.md`** (43KB) - Comprehensive landscape analysis
- **`review.md`** (60KB) - Code review documentation
- **`PACKAGING_README.md`** - Packaging guidelines
- **`packaging-react-dashboard-strategy.md`** - Frontend packaging strategy

## Examples Structure (`examples/`)

- **`features/`** - Feature-specific examples
- **`showcase/`** - Showcase implementations
- **`blog/`** - Blog post examples
- **`notebooks/`** - Jupyter notebook examples

## Configuration Files

### Python Configuration
- **`pyproject.toml`** - Main project configuration, dependencies, scripts
- **`requirements.txt`** - Python requirements
- **`uv.lock`** - Dependency lock file (673KB)
- **`.python-version`** - Python version specification

### Development Configuration
- **`.envtemplate`** - Environment variable template
- **`.env`** - Local environment configuration
- **`.gitignore`** - Git ignore rules
- **`.ruff_cache/`** - Ruff linter cache
- **`.pytest_cache/`** - pytest cache

### Frontend Configuration
- **`frontend/package.json`** - Node.js dependencies
- **`frontend/package-lock.json`** - Node.js lock file (125KB)
- **`frontend/tsconfig.json`** - TypeScript configuration
- **`frontend/vite.config.ts`** - Vite build configuration

## Scripts and Automation

### Build Scripts (`scripts/`)
- **`build_dashboard.py`** - Dashboard build automation

### Poe Tasks (pyproject.toml)
- **`install`** - Project installation
- **`build`** - Build process
- **`lint`** - Code linting with Ruff
- **`format`** - Code formatting
- **`test`** - Testing with various coverage options
- **`docs`** - Documentation serving

## Navigation Patterns and Conventions

### File Naming Conventions
- **Python modules**: `snake_case.py`
- **TypeScript files**: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- **Test files**: `test_*.py` for Python, `*.test.tsx` for TypeScript
- **Configuration**: `.env*`, `*.config.*`, `*.toml`

### Import Patterns
- **Python imports**: Use absolute imports from `src.flock`
- **TypeScript imports**: Relative imports within frontend, absolute for external packages
- **Test imports**: Test utilities in `conftest.py` and test helpers

### Module Organization
- **Core functionality**: Directly in `src/flock/`
- **Feature modules**: Grouped in subdirectories
- **Shared utilities**: Centralized in `utility/`, `helper/`, `utils/`
- **External integrations**: Separate modules (e.g., `mcp/`, `api/`)

### Configuration Hierarchy
1. **Environment variables** (`.env`)
2. **Project configuration** (`pyproject.toml`)
3. **Module configuration** (module-specific configs)
4. **Runtime configuration** (CLI arguments)

## Development Workflow Patterns

### Testing Strategy
- **80%+ overall coverage requirement**
- **100% coverage for critical paths** (orchestrator, subscription, visibility, agent)
- **Determinism testing** (multiple runs)
- **Contract testing** for API compliance
- **Integration testing** for component interaction

### Build and Deploy
- **UV-based Python package management**
- **Vite-based frontend build**
- **TypeScript compilation**
- **Automated testing** with coverage reporting
- **Documentation generation** with MkDocs

### Code Quality
- **Ruff for linting and formatting**
- **Type checking with mypy**
- **Pre-commit hooks**
- **Coverage gates**
- **Documentation requirements**

## Key Architectural Decisions

### Monorepo Structure
- **Clear separation** between Python backend and frontend
- **Independent build processes** for each component
- **Shared documentation** and examples
- **Unified testing strategy**

### Blackboard Pattern Implementation
- **Agent-centric design** with `agent.py` as core
- **Orchestrator pattern** for coordination
- **Event-driven architecture** with subscriptions
- **Visibility controls** for data access

### Real-time Dashboard
- **WebSocket communication** for live updates
- **React-based frontend** with TypeScript
- **Modular component architecture**
- **State management with Zustand**

## Navigation Guidelines for Agents

### When Working with Core Logic
1. **Start with `src/flock/`** for main implementation
2. **Check `orchestrator.py`** for coordination patterns
3. **Review `agent.py`** for agent implementation
4. **Consult `components.py`** for shared utilities

### When Working with Frontend
1. **Navigate to `frontend/src/`** for React components
2. **Check `components/`** for UI building blocks
3. **Review `store/`** for state management patterns
4. **Consult `services/`** for API integration

### When Working with Testing
1. **Use `tests/`** for comprehensive test examples
2. **Check `conftest.py`** for test configuration
3. **Review integration tests** for component interaction patterns
4. **Consult contract tests** for API examples

### When Working with Configuration
1. **Check `pyproject.toml`** for project setup
2. **Review `.envtemplate`** for environment variables
3. **Consult individual module configs** for specific settings
4. **Check `scripts/`** for build automation

This structure analysis provides agents with the necessary context to navigate the codebase efficiently, understand the organization patterns, and locate relevant files for their specific tasks.
