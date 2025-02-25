# Installation

This guide will walk you through the process of installing Flock and setting up your development environment.

## Prerequisites

Before installing Flock, ensure you have the following prerequisites:

- Python 3.9 or higher
- pip (Python package installer)
- A virtual environment tool (optional but recommended)

## Installation Options

### Basic Installation

To install the core Flock package:

```bash
pip install flock-core
```

### Installation with Tools Support

To install Flock with tools support:

```bash
pip install flock-core[tools]
```

### Installation with All Tools

To install Flock with all tools including docling:

```bash
pip install flock-core[all-tools]
```

### Installation from Source

To install Flock from source:

```bash
git clone https://github.com/flock-ai/flock.git
cd flock
pip install -e .
```

## Setting Up a Virtual Environment

It's recommended to use a virtual environment to avoid conflicts with other Python packages.

### Using venv

```bash
# Create a virtual environment
python -m venv flock-env

# Activate the virtual environment (Windows)
flock-env\Scripts\activate

# Activate the virtual environment (macOS/Linux)
source flock-env/bin/activate

# Install Flock
pip install flock-core
```

### Using conda

```bash
# Create a conda environment
conda create -n flock-env python=3.9

# Activate the conda environment
conda activate flock-env

# Install Flock
pip install flock-core
```

## Verifying Installation

To verify that Flock is installed correctly, run the following command:

```bash
python -c "import flock; print(flock.__version__)"
```

This should print the version of Flock that you installed.

## Setting Up API Keys

Flock uses various APIs for its tools. To use these tools, you'll need to set up the appropriate API keys.

### OpenAI API Key

To use OpenAI models, you'll need an OpenAI API key. You can set it as an environment variable:

```bash
# Windows
set OPENAI_API_KEY=your-api-key

# macOS/Linux
export OPENAI_API_KEY=your-api-key
```

Or you can set it in your Python code:

```python
import os
os.environ["OPENAI_API_KEY"] = "your-api-key"
```

### Other API Keys

Depending on the tools you're using, you may need to set up other API keys:

- **Tavily API Key**: For web search using Tavily
- **DuckDuckGo API Key**: For web search using DuckDuckGo
- **Temporal API Key**: For Temporal integration

## Next Steps

Now that you have Flock installed, you can:

- Follow the [Quick Start](quickstart.md) guide to create your first agent
- Learn about [Basic Concepts](concepts.md) in Flock
- Configure Flock with [Configuration](configuration.md) options
