---
hide:
  - toc
---

# Installation 🐣

Getting Flock onto your system is easy using modern Python package managers like `uv` or the standard `pip`. We recommend using `uv` for faster installations.

## Using `uv` (Recommended)

`uv` is a fast Python package installer and resolver.

1.  **Install `uv`** (if you haven't already):
    ```bash
    # On macOS and Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # On Windows
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

    # Or via pip
    pip install uv
    ```

2.  **Install Flock Core:**
    ```bash
    uv pip install flock-core
    ```
    This installs the essential `flock-core` package.

3.  **Install with Extras (Optional):**
    If you need additional tools or features:
    ```bash
    # For common tools (web search, markdownify, etc.)
    uv pip install flock-core[tools]

    # To install everything, including tools and future extras
    uv pip install flock-core[all]
    ```

## Using `pip`

If you prefer using `pip`:

1.  **Install Flock Core:**
    ```bash
    pip install flock-core
    ```

2.  **Install with Extras (Optional):**
    ```bash
    # For common tools
    pip install flock-core[tools]

    # To install everything
    pip install flock-core[all]
    ```

!!! note "Available Extras"
    *   `tools`: Installs `tavily-python` and `markdownify`.
    *   `all`: Installs all optional dependencies defined in `tools`, plus `docling`.

## Setting Up Your Environment (API Keys)

Flock agents typically interact with Large Language Models (LLMs). You'll need to configure API keys for the services you intend to use. Flock uses `litellm` under the hood, which supports numerous providers (OpenAI, Anthropic, Gemini, Azure, etc.).

The recommended way to manage your API keys is through **environment variables**. You can set them directly in your shell, or use a `.env` file in your project's root directory.

1.  **Create a `.env` file:** In the main folder of your project, create a file named `.env`.
2.  **Add your keys:** Add the necessary API keys for your chosen LLM provider(s). Refer to the `litellm` documentation for the correct environment variable names.

    Example `.env` file:
    ```dotenv
    # .env
    OPENAI_API_KEY="your-openai-api-key"
    ANTHROPIC_API_KEY="your-anthropic-api-key"
    TAVILY_API_KEY="your-tavily-api-key" # For Tavily search tool
    # Add Azure, GitHub, etc., keys if needed by specific tools
    # AZURE_SEARCH_ENDPOINT="your-azure-search-endpoint"
    # AZURE_SEARCH_API_KEY="your-azure-search-api-key"
    # GITHUB_PAT="your-github-pat"
    ```

Flock (via `litellm` and `python-decouple`) will automatically load these variables when needed.

!!! warning "Security"
    Never commit your `.env` file containing secret keys to version control (like Git). Add `.env` to your `.gitignore` file.

## Verifying Installation

You can quickly verify that Flock is installed by opening a Python interpreter and importing it:

```python
import flock.core
print("Flock imported successfully!")
```

If this runs without errors, you're all set!

Next Steps

With Flock installed, you're ready for the Quick Start guide to build and run your first agent!