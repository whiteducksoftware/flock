# Configuration Reference

## Environment Variables and .env Files

Flock automatically loads environment variables from `.env` files in the current directory when the package is imported. This provides a convenient way to manage configuration without manually setting environment variables.

### Automatic .env Loading

When you import Flock, it will automatically:
1. Look for a `.env` file in the current working directory
2. Load all environment variables from that file
3. Make them available via `os.getenv()` throughout the application

```python
# This will automatically load .env file if it exists
from flock import Flock

flock = Flock()  # Will use DEFAULT_MODEL from .env if available
```

### Creating a .env File

Create a `.env` file in your project root:

```bash
# Choose a default model for your environment
DEFAULT_MODEL=openai/gpt-4.1
# DEFAULT_MODEL=azure/gpt-4.1

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Azure OpenAI (API-key path)
AZURE_API_KEY=your_azure_api_key_here
AZURE_API_BASE=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-12-01-preview

# Tracing
FLOCK_AUTO_TRACE=true
FLOCK_TRACE_FILE=true
FLOCK_TRACE_SERVICES=["flock", "agent", "dspyengine"]
```

## Azure OpenAI Authentication

Flock works with LiteLLM's Azure provider. `DEFAULT_MODEL` is resolved by Flock and `DSPyEngine`, while Azure connection settings such as `AZURE_API_BASE`, `AZURE_API_VERSION`, and `AZURE_API_KEY` are consumed by the underlying LiteLLM-backed `dspy.LM(...)`.

### API-key Authentication

The existing API-key flow remains supported:

```bash
DEFAULT_MODEL=azure/gpt-4.1
AZURE_API_KEY=your_azure_api_key_here
AZURE_API_BASE=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-12-01-preview
```

With that configuration in place, `DSPyEngine(model="azure/gpt-4.1")` works without any extra code.

### Entra ID / DefaultAzureCredential Authentication

For token-based auth, install the Azure auth dependency:

```bash
uv sync --extra azure
```

Then keep the Azure endpoint settings in `.env` and create the token provider in code:

```bash
DEFAULT_MODEL=azure/gpt-4.1
AZURE_API_BASE=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-12-01-preview
```

```python
from flock.engines import DSPyEngine
from flock.engines.auth.azure import get_default_azure_token_provider

engine = DSPyEngine(
    lm_kwargs={
        "azure_ad_token_provider": get_default_azure_token_provider(),
    }
)
```

The helper also accepts custom `scopes=` values and forwards additional keyword arguments to `DefaultAzureCredential(...)` when you need to tune the Azure identity chain. For the Azure AI Foundry **Agents** API, pass `AZURE_AI_FOUNDRY_SCOPE`:

```python
from flock.engines.auth.azure import AZURE_AI_FOUNDRY_SCOPE, get_default_azure_token_provider

token_provider = get_default_azure_token_provider(scopes=AZURE_AI_FOUNDRY_SCOPE)
```

### Provider-specific `lm_kwargs`

`DSPyEngine(lm_kwargs={...})` forwards extra keyword arguments to the `dspy.LM(...)` instance created by the engine. That passthrough is how Azure token providers, or any other provider-specific LM arguments supported by DSPy/LiteLLM, are attached.

Keep these reserved keys out of `lm_kwargs`: `model`, `temperature`, `max_tokens`, `max_completion_tokens`, `cache`, and `num_retries`. Use the dedicated engine field when one exists.

If an adapter creates its own `dspy.LM(...)` instance, configure that LM directly. `lm_kwargs` only affects the engine-managed LM. The [DSPy Engine guide](../guides/dspy-engine.md) shows both patterns.

### Available Environment Variables

See the [.envtemplate](https://github.com/whiteducksoftware/flock/blob/main/.envtemplate) file for a complete list of all available configuration options.

### Manual Environment Variable Loading

If you need to load environment variables from a custom location:

```python
from dotenv import load_dotenv
load_dotenv('/path/to/your/.env')  # Load from custom path

from flock import Flock
```

### Priority Order

Environment variables are resolved in this order:
1. System environment variables (highest priority)
2. `.env` file variables
3. Default values in the code (lowest priority)

## Configuration Options

For detailed configuration options, see:
- [Installation Guide](../getting-started/installation.md) for environment setup
- [.envtemplate](https://github.com/whiteducksoftware/flock/blob/main/.envtemplate) for all available options
- [DSPy Engine Guide](../guides/dspy-engine.md) for `lm_kwargs`, adapters, and Azure auth wiring
- [Tracing Configuration](../guides/tracing/) for telemetry settings
