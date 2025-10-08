# Dependencies & Package Management for AI Agents

This document covers dependency management and package installation for AI agents working with Flock Flow.

## 📦 Package Management with UV

**⚠️ CRITICAL: NEVER use `pip install`** - Always use `uv add` to maintain `uv.lock` consistency.

### UV Commands (NOT pip!)

```bash
# Poe tasks (recommended)
poe install          # Complete installation workflow
poe build           # Sync dependencies, build, and install
poe test            # Run tests
poe test-cov        # Run with coverage
poe lint            # Lint code
poe format          # Format code

# Manual UV commands
uv sync --dev --all-groups --all-extras  # Install all dependencies
uv add package-name                        # Add production dependency
uv add --dev package-name                  # Add development dependency
uv remove package-name                     # Remove dependency
uv run pytest tests/test_specific.py       # Run specific test
```

## 🐍 Key Backend Dependencies

| Category | Package | Purpose |
|----------|---------|---------|
| **AI/LLM** | `dspy==3.0.0` | DSPy framework for prompt programming |
| | `litellm==1.75.3` | LLM API abstraction layer |
| **Web Framework** | `fastapi>=0.117.1` | Modern web framework |
| | `uvicorn>=0.37.0` | ASGI server |
| | `websockets>=15.0.1` | WebSocket support |
| **Data & Validation** | `pydantic[email]>=2.11.9` | Data validation and settings |
| **CLI & UX** | `typer>=0.19.2` | Modern CLI framework |
| | `rich>=14.1.0` | Rich text and formatting |
| **Observability** | `opentelemetry-***` | Distributed tracing |
| | `loguru>=0.7.3` | Structured logging |
| **Protocol** | `mcp>=1.7.1` | Model Context Protocol support |
| **Testing** | `pytest>=8.3.3` | Testing framework |
| | `ruff>=0.7.2` | Linting and formatting |
| | `mypy>=1.15.0` | Type checking |

## 🎨 Frontend Dependencies

| Category | Package | Purpose |
|----------|---------|---------|
| **Core** | `react^19.2.0` | UI framework |
| | `typescript^5.9.3` | Type safety |
| | `vite^7.1.9` | Build tool |
| **Visualization** | `@xyflow/react^12.8.6` | Graph visualization |
| | `dagre^0.8.5` | Graph layout algorithm |
| **State** | `zustand^5.0.8` | State management |
| | `idb^8.0.3` | IndexedDB wrapper |
| **Testing** | `vitest^3.2.4` | Test framework |
| | `@testing-library/react^16.3.0` | React testing utilities |

## 🔧 Adding New Dependencies

### Backend (Python)

```bash
# Add production dependency
uv add package-name

# Add dev dependency
uv add --dev package-name

# Example: Add a new LLM library
uv add anthropic>=0.18.0
```

### Frontend (JavaScript/TypeScript)

```bash
cd frontend

# Add dependency
npm install package-name

# Add dev dependency
npm install --save-dev package-name

# Example: Add a new chart library
npm install recharts
```

## 🚨 Important Notes

1. **Always use UV for Python packages** - Never `pip install`
2. **Check `uv.lock` after changes** - Ensure lock file is updated
3. **Test after adding dependencies** - Run `poe test` to verify
4. **Document new dependencies** - Update this file if adding major dependencies
5. **Check compatibility** - Ensure new packages work with Python 3.10+

## 🔍 Troubleshooting

### UV Issues

```bash
# Clear UV cache
uv cache clean

# Reinstall from scratch
rm -rf .venv uv.lock
poe install

# Force sync
uv sync --refresh
```

### Frontend Issues

```bash
cd frontend

# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear build cache
npm run clean
```

---

*For development workflow, see [development.md](./development.md)*
