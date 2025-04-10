---
hide:
  - toc
---

# Configuration ⚙️

Flock offers several ways to configure its behavior, from setting up LLM providers to controlling logging and execution modes.

## Environment Variables (.env file)

The primary and recommended way to configure Flock and its integrations is through **environment variables**. Flock uses the `python-decouple` library to read these variables, prioritizing:

1.  Environment variables set directly in your system.
2.  Values defined in a `.env` file located in your project's root directory.

**Create a `.env` file in your project root:**

```dotenv
# .env - Example Configuration

# --- LLM Provider API Keys (Required) ---
# Add keys for the providers you use (OpenAI, Anthropic, Gemini, Azure, etc.)
# Refer to litellm documentation for specific variable names
OPENAI_API_KEY="your-openai-api-key"
# ANTHROPIC_API_KEY="your-anthropic-api-key"
# GOOGLE_API_KEY="your-google-api-key" # For Gemini

# --- Default Flock Settings ---
DEFAULT_MODEL="openai/gpt-4o" # Default LLM used if not specified by Agent/Flock

# --- Tool-Specific Keys (Optional) ---
TAVILY_API_KEY="your-tavily-search-key"
GITHUB_PAT="your-github-personal-access-token" # For GitHub tools
GITHUB_REPO="your-username/your-repo-name"      # For GitHub tools
GITHUB_USERNAME="your-github-username"        # For GitHub tools
AZURE_SEARCH_ENDPOINT="your-azure-search-url"   # For Azure Search tools
AZURE_SEARCH_API_KEY="your-azure-search-key"    # For Azure Search tools
# AZURE_SEARCH_INDEX_NAME="your-default-index"  # For Azure Search tools

# --- Temporal Integration (Optional) ---
# TEMPORAL_SERVER_URL="localhost:7233" # Default if Temporal is enabled

# --- Logging & Debugging ---
# LOCAL_DEBUG="True" # Set to True to force local execution even if enable_temporal=True in code (DEPRECATED - use enable_temporal=False instead)
LOG_LEVEL="INFO" # Logging level (DEBUG, INFO, WARNING, ERROR)
LOGGING_DIR="logs" # Directory to store log files

# --- Telemetry (OpenTelemetry/Jaeger - Optional) ---
# OTEL_SERVICE_NAME="flock-service"
# JAEGER_ENDPOINT="http://localhost:14268/api/traces" # Thrift HTTP endpoint
# JAEGER_TRANSPORT="http" # Or "grpc" (e.g., "localhost:14250")
# OTEL_SQL_DATABASE_NAME="flock_events.db"
# OTEL_FILE_NAME="flock_events.jsonl"
# OTEL_ENABLE_SQL="True"
# OTEL_ENABLE_FILE="True"
# OTEL_ENABLE_JAEGER="False" # Set to True to enable Jaeger exporting

# --- CLI Settings (Managed by `flock settings`) ---
# SHOW_SECRETS="False"
# VARS_PER_PAGE="20"
```


**LLM Keys**: Essential for your agents to function. Use the variable names specified by litellm.

**Tool Keys**: Required only if you use specific tools (Tavily, GitHub, Azure Search).

**DEFAULT_MODEL**: Sets the fallback LLM identifier if an agent doesn't specify its own.

**TEMPORAL_SERVER_URL**: Needed if you enable Temporal for distributed execution.

**Logging/Telemetry**: Control log verbosity, output directories, and OpenTelemetry settings.

## Instance Configuration (Code)

You can also override or set configurations directly when creating Flock or FlockAgent instances in your Python code:


### Configure Flock instance
```python
from flock.core import Flock, FlockAgent, FlockFactory

my_flock = Flock(
    name="ConfiguredFlock",
    model="anthropic/claude-3-sonnet-20240229", # Override default model
    enable_temporal=False, # Force local execution
    enable_logging=True    # Enable logging for this flock instance
)
```

### Configure Agent instance
```python
specific_agent = FlockFactory.create_default_agent(
    name="SpecificAgent",
    model="openai/gpt-3.5-turbo", # Use a different model for this agent
    use_cache=False,              # Disable caching for this agent
    temperature=0.7,              # Set LLM temperature
    # ... other agent-specific configs
)

my_flock.add_agent(specific_agent)
```


Settings provided during instantiation take precedence over environment variables for that specific instance.

## CLI Settings

When starting Flock as CLI-Tool (typing `flock` in your terminal) it offers a Settings editor.
These settings are typically stored in ~/.flock/.env. If this file exists flock will ignore local .env files and only use the global .env.

This behavior can be changed by the `LOCAL_ENV_OVERWRITES_GLOBAL_ENV` flag.
