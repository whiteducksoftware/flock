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
# API Keys
OPENAI_API_KEY=your_openai_api_key_here
AZURE_API_KEY=your_azure_api_key_here
AZURE_API_BASE=https://your-resource.openai.azure.com/

# Model Configuration
DEFAULT_MODEL=openai/gpt-4.1

# Tracing Configuration
FLOCK_AUTO_TRACE=true
FLOCK_TRACE_FILE=true
FLOCK_TRACE_SERVICES=["flock", "agent", "dspyengine"]
```

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
- [Tracing Configuration](../guides/tracing/) for telemetry settings
