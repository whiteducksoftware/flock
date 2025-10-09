---
title: Installation
description: Install Flock and configure your development environment in minutes
tags:
  - getting started
  - installation
  - setup
  - beginner
search:
  boost: 2.5
---

# Installation

Get Flock up and running in minutes.

---

## Prerequisites

- **Python 3.10+** (we use modern async features)
- **OpenAI API key** (or compatible LLM provider)
- **UV package manager** (recommended) or pip

---

## Install with UV (Recommended)

UV is a fast, reliable Python package manager that handles virtual environments automatically:

```bash
# Install Flock
uv pip install flock-core

# Or with all optional features
uv pip install "flock-core[all]"
```

---

## Install with pip

```bash
# Install Flock
pip install flock-core

# Or with all optional features
pip install "flock-core[all]"
```

---

## Optional Dependencies

Flock has several optional feature sets:

### Development Tools
```bash
pip install "flock-core[dev]"
```
Includes pytest, ruff, mypy, and other development tools.

### Dashboard (React UI)
```bash
pip install "flock-core[dashboard]"
```
Real-time dashboard for monitoring agent execution.

### Comparison Frameworks
```bash
pip install "flock-core[comparison]"
```
LangGraph, AutoGen, and other frameworks for benchmarking.

### All Features
```bash
pip install "flock-core[all]"
```

---

## Configuration

### Set Your API Key

```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."

# For other providers (via LiteLLM)
export ANTHROPIC_API_KEY="..."
export COHERE_API_KEY="..."
```

### Configure Default Model

```bash
export DEFAULT_MODEL="openai/gpt-4.1"
```

Flock uses [LiteLLM](https://docs.litellm.ai/docs/) for provider abstraction, supporting 100+ LLM providers.

---

## Verify Installation

```python
from flock import Flock
print("✅ Flock installed successfully!")
```

Or from command line:

```bash
python -c "from flock import Flock; print('✅ Flock ready!')"
```

---

## Enable Tracing (Optional but Recommended)

Flock's observability features require trace storage:

```bash
# Enable auto-tracing to DuckDB
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true
```

This creates `.flock/traces.duckdb` in your project directory for full execution history.

---

## Next Steps

Ready to build your first agent? Continue to the [Quick Start Guide](quick-start.md).

For more details on tracing configuration, see the [Tracing Guide](../guides/tracing/tracing-quickstart.md).
