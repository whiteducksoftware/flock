# Configuring Flock for Ollama

This guide explains how to configure Flock to connect to your Ollama instance running on `localhost:1134` with the `granite3.3:2b` model.

## Quick Setup

### Prerequisites

1. **Ollama is installed and running**
2. **The granite3.3:2b model is available**
3. **Ollama is configured to run on port 1134** (default is 11434)

### Step 1: Start Ollama on Port 1134

```bash
# Stop any existing Ollama instance
pkill ollama

# Start Ollama on port 1134
OLLAMA_HOST=0.0.0.0:1134 ollama serve
```

### Step 2: Pull the Model (if needed)

```bash
ollama pull granite3.3:2b
```

### Step 3: Configure Environment Variables

```bash
export TRELLIS_MODEL="ollama/granite3.3:2b"
export OLLAMA_API_BASE="http://localhost:1134"
```

### Step 4: Run Your Flock Application

```python
from flock import Flock

# Create orchestrator with Ollama model
orchestrator = Flock("ollama/granite3.3:2b")

# Create your agents...
```

## Environment Variables Reference

### Model Configuration

The framework reads model names from these environment variables (in order of precedence):

1. **`TRELLIS_MODEL`** - Flock-specific model configuration
2. **`OPENAI_MODEL`** - Fallback for OpenAI compatibility
3. **Model passed to `Flock()` constructor** - Direct specification

**Example:**
```bash
export TRELLIS_MODEL="ollama/granite3.3:2b"
```

### Ollama Base URL Configuration

LiteLLM (the underlying library) reads the Ollama API base URL from:

- **`OLLAMA_API_BASE`** - Ollama-specific base URL

**Example:**
```bash
export OLLAMA_API_BASE="http://localhost:1134"
```

## Code Location Analysis

### Where Environment Variables Are Read

1. **Model Name Resolution** (`src/flock/engines/dspy_engine.py:303-309`)
   ```python
   def _resolve_model_name(self) -> str:
       model = self.model or os.getenv("TRELLIS_MODEL") or os.getenv("OPENAI_MODEL")
       if not model:
           raise NotImplementedError(
               "DSPyEngine requires a configured model (set TRELLIS_MODEL, OPENAI_MODEL, or pass model=...)."
           )
       return model
   ```

2. **LiteLLM Integration** (`src/flock/engines/dspy_engine.py:158-167`)
   ```python
   model_name = self._resolve_model_name()
   dspy_mod = self._import_dspy()

   lm = dspy_mod.LM(
       model=model_name,
       temperature=self.temperature,
       max_tokens=self.max_tokens,
       cache=self.enable_cache,
       num_retries=self.max_retries,
   )
   ```

3. **Orchestrator Default** (`src/flock/orchestrator.py:95`)
   ```python
   if not model:
       self.model = os.getenv("DEFAULT_MODEL")
   ```

### How LiteLLM Handles Ollama

When you specify a model with the `ollama/` prefix (e.g., `ollama/granite3.3:2b`):

1. **LiteLLM automatically detects** the Ollama provider
2. **Reads `OLLAMA_API_BASE`** from environment variables
3. **Constructs the API endpoint** as `{OLLAMA_API_BASE}/api/generate` or `/api/chat`
4. **Sends requests** to your local Ollama instance

## Configuration Methods

### Method 1: Environment Variables (Recommended)

**Best for:** Production deployments, CI/CD, shared configurations

```bash
# In your shell or .env file
export TRELLIS_MODEL="ollama/granite3.3:2b"
export OLLAMA_API_BASE="http://localhost:1134"
```

Then in your code:
```python
from flock import Flock

# Model is automatically picked up from environment
orchestrator = Flock()
```

### Method 2: Direct in Code

**Best for:** Testing, development, scripts

```python
import os
from flock import Flock

# Set environment variables
os.environ["TRELLIS_MODEL"] = "ollama/granite3.3:2b"
os.environ["OLLAMA_API_BASE"] = "http://localhost:1134"

# Or pass model directly
orchestrator = Flock("ollama/granite3.3:2b")
```

### Method 3: .env File (Recommended for Development)

Create a `.env` file in your project root:

```bash
# .env
TRELLIS_MODEL=ollama/granite3.3:2b
OLLAMA_API_BASE=http://localhost:1134
```

Then use `python-dotenv`:
```python
from dotenv import load_dotenv
from flock import Flock

load_dotenv()  # Load environment variables from .env
orchestrator = Flock()
```

## Troubleshooting

### Connection Refused

**Error:** `Connection refused` or `Cannot connect to Ollama`

**Solutions:**
1. Check Ollama is running: `ps aux | grep ollama`
2. Verify port: `lsof -i :1134`
3. Test connection: `curl http://localhost:1134/api/tags`

### Model Not Found

**Error:** `Model not found: granite3.3:2b`

**Solutions:**
1. List available models: `ollama list`
2. Pull the model: `ollama pull granite3.3:2b`

### Wrong Port

**Error:** Connection works on port 11434 but not 1134

**Solutions:**
1. Ensure you started Ollama with: `OLLAMA_HOST=0.0.0.0:1134 ollama serve`
2. Or update your configuration to use the default port: `export OLLAMA_API_BASE="http://localhost:11434"`

### DSPy/LiteLLM Debug Logging

Enable verbose logging to see what's happening:

```python
import os

# Enable LiteLLM debug logging
os.environ["LITELLM_LOG"] = "DEBUG"

# Now run your Flock application
from flock import Flock
orchestrator = Flock("ollama/granite3.3:2b")
```

## Example Application

See the complete working example at:
- `examples/showcase/07_ollama_example.py`

Run it:
```bash
cd /Users/tilmansattler/src/whiteduck/flock
export TRELLIS_MODEL="ollama/granite3.3:2b"
export OLLAMA_API_BASE="http://localhost:1134"
uv run python examples/showcase/07_ollama_example.py
```

## Additional Resources

- **LiteLLM Ollama Documentation:** https://docs.litellm.ai/docs/providers/ollama
- **Ollama Documentation:** https://github.com/ollama/ollama/blob/main/docs/api.md
- **DSPy Documentation:** https://dspy-docs.vercel.app/
- **Flock AGENTS.md:** See the root `AGENTS.md` file for framework details

## Summary

**TL;DR:**

1. Set environment variables:
   ```bash
   export TRELLIS_MODEL="ollama/granite3.3:2b"
   export OLLAMA_API_BASE="http://localhost:1134"
   ```

2. Start Ollama on port 1134:
   ```bash
   OLLAMA_HOST=0.0.0.0:1134 ollama serve
   ```

3. Create your Flock orchestrator:
   ```python
   from flock import Flock
   orchestrator = Flock("ollama/granite3.3:2b")
   ```

4. Build and run your agents! 🚀
