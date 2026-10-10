---
title: Local Models
description: Run Flock agents on local models through an OpenAI-compatible server (Ollama, llama.cpp, vLLM, LM Studio)
tags:
  - local
  - ollama
  - llama.cpp
  - vllm
  - models
  - offline
search:
  boost: 1.5
---

# Local Models

**Run Flock agents on your own hardware by serving the model with a local inference server.**

Ollama, llama.cpp's `llama-server`, vLLM and LM Studio all serve models over an OpenAI-compatible API. Flock talks to them like to any hosted model: point the model string at the server and keep the rest of your agents unchanged. The server owns the GPU, batching and model lifecycle; your Flock process stays light.

!!! warning "Upgrade note: the `transformers/` provider was removed"
    Earlier versions shipped an in-process Hugging Face Transformers provider (`Flock("transformers/<model>")`, extra `flock-core[transformers]`). It was removed together with its `torch` dependency. Serve the same model with one of the servers below and change the model string, for example `transformers/Qwen/Qwen3-4B-Instruct-2507` → `ollama_chat/qwen3:4b`.

---

## Ollama

```bash
ollama pull qwen3:4b
ollama serve                      # http://localhost:11434
```

```python
from flock import Flock

flock = Flock("ollama_chat/qwen3:4b")
```

Set `OLLAMA_API_BASE` if Ollama runs on another host or port. See [Connect with Ollama](../tutorials/connect_with_ollama.md) for a full walkthrough.

## llama.cpp, vLLM, LM Studio and other OpenAI-compatible servers

Start the server, then use the `openai/` prefix with the model name the server reports and point `OPENAI_BASE_URL` at it:

```bash
# llama.cpp
llama-server -m Qwen3-4B-Instruct-2507-Q4_K_M.gguf --port 8080
export OPENAI_BASE_URL="http://localhost:8080/v1"

# vLLM
vllm serve Qwen/Qwen3-4B-Instruct-2507 --port 8000
export OPENAI_BASE_URL="http://localhost:8000/v1"

# LM Studio: start the local server in the app (default port 1234)
export OPENAI_BASE_URL="http://localhost:1234/v1"
```

```python
from flock import Flock

flock = Flock("openai/qwen3-4b-instruct")
```

Local servers usually accept any API key; set `OPENAI_API_KEY` to a placeholder if your environment has none. To use a local model for one agent only, give that agent its own engine:

```python
from flock import DSPyEngine

local = DSPyEngine(model="ollama_chat/qwen3:4b")
summarizer = (
    flock.agent("summarizer")
    .consumes(Document)
    .publishes(Summary)
    .with_engines(local)
)
```

Example: [`examples/04-misc/05_lm_studio.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/04-misc/05_lm_studio.py).

## Choosing a model

Flock agents produce structured output (Pydantic models), so instruction-tuned models that follow output formats reliably work best. Small models (1-4B parameters) handle simple single-field outputs; multi-field outputs, tools and long contexts need larger ones. Quantized GGUF models in llama.cpp or Ollama run on consumer GPUs and on CPUs.

## Semantic matching stays local too

[Semantic subscriptions](semantic-subscriptions.md) compute their embeddings in-process with a small ONNX model and need no server: install `flock-core[semantic]`.
