---
title: Local Models with Transformers
description: Run Flock agents with local Hugging Face models - no API keys required
tags:
  - transformers
  - local
  - huggingface
  - models
  - offline
search:
  boost: 1.5
---

# Local Models with Transformers

**Run Flock agents entirely locally using Hugging Face models.**

Flock includes a custom LiteLLM provider that enables local inference using the Hugging Face Transformers library. This means you can run agents without any API keys or internet connection.

---

## Quick Start

```python
from flock import Flock, flock_type
from pydantic import BaseModel, Field

@flock_type
class Question(BaseModel):
    text: str = Field(description="The question to answer")

@flock_type
class Answer(BaseModel):
    response: str = Field(description="The answer to the question")
    confidence: str = Field(description="How confident: low, medium, or high")

# Use transformers/ prefix for local models
flock = Flock("transformers/unsloth/Qwen3-4B-Instruct-2507-bnb-4bit")

qa_agent = (
    flock.agent("qa_expert")
    .description("Answers questions thoughtfully")
    .consumes(Question)
    .publishes(Answer)
)

async def main():
    await flock.publish(Question(text="What is the capital of France?"))
    await flock.run_until_idle()
    
    answers = await flock.get_artifacts(Answer)
    print(answers[0].response)

import asyncio
asyncio.run(main())
```

---

## Installation

The Transformers provider requires optional dependencies:

```bash
# Install with transformers support
pip install flock-core[semantic]

# Or install dependencies separately
pip install transformers torch accelerate bitsandbytes
```

!!! note "GPU Recommended"
    While CPU inference works, GPU acceleration significantly improves performance. The provider automatically uses CUDA if available.

---

## Model Naming Convention

Use the `transformers/` prefix followed by the Hugging Face model ID:

```python
# Format: transformers/<organization>/<model-name>
flock = Flock("transformers/microsoft/Phi-3-mini-4k-instruct")
flock = Flock("transformers/meta-llama/Llama-2-7b-chat-hf")
flock = Flock("transformers/unsloth/Qwen3-4B-Instruct-2507-bnb-4bit")
```

---

## Supported Models

Any causal language model from Hugging Face Hub works:

| Model Family | Example Model ID |
|--------------|------------------|
| **Qwen** | `transformers/Qwen/Qwen2.5-7B-Instruct` |
| **Llama** | `transformers/meta-llama/Llama-2-7b-chat-hf` |
| **Mistral** | `transformers/mistralai/Mistral-7B-Instruct-v0.2` |
| **Phi** | `transformers/microsoft/Phi-3-mini-4k-instruct` |
| **Gemma** | `transformers/google/gemma-2-9b-it` |

### Quantized Models

For memory-efficient inference, use pre-quantized models:

```python
# 4-bit quantized model (requires bitsandbytes)
flock = Flock("transformers/unsloth/Qwen3-4B-Instruct-2507-bnb-4bit")
```

---

## How It Works

### Auto-Registration

The Transformers provider is automatically registered when Flock is imported:

```python
from flock import Flock  # Provider registered automatically

# Now you can use transformers/ models
flock = Flock("transformers/microsoft/Phi-3-mini-4k-instruct")
```

### Model Caching

Models are cached in memory after first load:

```python
# First call: Downloads and loads model (~30s for large models)
flock1 = Flock("transformers/Qwen/Qwen2.5-7B-Instruct")

# Subsequent calls: Instant (uses cached model)
flock2 = Flock("transformers/Qwen/Qwen2.5-7B-Instruct")
```

Models are also cached on disk in the Hugging Face cache directory (`~/.cache/huggingface/`).

### Device Placement

The provider automatically handles device placement:

1. **With `accelerate`**: Uses `device_map="auto"` for optimal multi-GPU distribution
2. **Without `accelerate`**: Falls back to single GPU (if available) or CPU

```bash
# For best performance, install accelerate
pip install accelerate
```

---

## Streaming Support

The Transformers provider supports both streaming and non-streaming modes:

```python
from flock import Flock, DSPyEngine

# Enable streaming for real-time token output
engine = DSPyEngine(
    model="transformers/Qwen/Qwen2.5-7B-Instruct",
    stream=True  # Tokens appear as they're generated
)

agent = (
    flock.agent("streamer")
    .consumes(Input)
    .publishes(Output)
    .with_engines(engine)
)
```

---

## Memory Management

### GPU Memory

Large models require significant VRAM:

| Model Size | Approximate VRAM (FP16) | Approximate VRAM (4-bit) |
|------------|------------------------|-------------------------|
| 3B | ~6 GB | ~2 GB |
| 7B | ~14 GB | ~4 GB |
| 13B | ~26 GB | ~8 GB |

### Tips for Limited Memory

1. **Use quantized models**: Look for models with `bnb-4bit` or `GPTQ` in the name
2. **Clear model cache**: Delete `~/.cache/huggingface/hub/` if running low on disk space
3. **Use smaller models**: 3B-7B models work well for most tasks

---

## Comparison with API Models

| Feature | API Models | Local Transformers |
|---------|------------|-------------------|
| **Latency** | Network dependent | Local, consistent |
| **Cost** | Per-token pricing | Hardware only |
| **Privacy** | Data sent to API | Fully local |
| **Offline** | ❌ Requires internet | ✅ Works offline |
| **Model Selection** | Limited to provider | Any HF model |
| **Quality** | Highest (GPT-4, Claude) | Varies by model |

---

## Example: Offline Agent Pipeline

```python
import asyncio
from flock import Flock, flock_type
from pydantic import BaseModel, Field

@flock_type
class Document(BaseModel):
    content: str
    source: str

@flock_type
class Summary(BaseModel):
    key_points: list[str]
    word_count: int

@flock_type
class Analysis(BaseModel):
    sentiment: str = Field(pattern="^(positive|negative|neutral)$")
    topics: list[str]

# Fully offline pipeline
flock = Flock("transformers/microsoft/Phi-3-mini-4k-instruct")

summarizer = (
    flock.agent("summarizer")
    .description("Extract key points from documents")
    .consumes(Document)
    .publishes(Summary)
)

analyzer = (
    flock.agent("analyzer")
    .description("Analyze sentiment and topics")
    .consumes(Summary)
    .publishes(Analysis)
)

async def main():
    doc = Document(
        content="Flock is a production-focused framework...",
        source="readme.md"
    )
    await flock.publish(doc)
    await flock.run_until_idle()
    
    analyses = await flock.get_artifacts(Analysis)
    print(f"Sentiment: {analyses[0].sentiment}")
    print(f"Topics: {analyses[0].topics}")

asyncio.run(main())
```

---

## Troubleshooting

### Model Download Fails

```python
# Set HF_HOME for custom cache location
import os
os.environ["HF_HOME"] = "/path/to/cache"
```

### CUDA Out of Memory

```python
# Use a smaller or quantized model
flock = Flock("transformers/unsloth/Qwen3-4B-Instruct-2507-bnb-4bit")

# Or force CPU (slower but works)
import torch
torch.cuda.is_available = lambda: False
```

### Slow First Run

First run downloads and loads the model. Subsequent runs use cached model:

```bash
# Pre-download model
python -c "from transformers import AutoModelForCausalLM; AutoModelForCausalLM.from_pretrained('microsoft/Phi-3-mini-4k-instruct')"
```

---

## See Also

- [DSPy Engine Guide](dspy-engine.md) - Understanding the default engine
- [Custom Engines Tutorial](../tutorials/custom-engines.md) - Building your own engines
- [Connect with Ollama](../tutorials/connect_with_ollama.md) - Alternative local model approach
