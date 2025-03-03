# Chain of Draft Implementation

This is an implementation of the "Chain of Draft: Thinking Faster by Writing Less" paper using the Flock agent framework.

## Overview

Chain of Draft (CoD) is a novel prompting strategy for large language models that encourages minimalistic, concise reasoning steps rather than verbose Chain-of-Thought (CoT) reasoning. This implementation demonstrates how to use the Flock framework to create and run Chain of Draft-based reasoning workflows.

## Key Benefits of Chain of Draft

- **Efficiency**: Uses as little as 7.6% of the tokens compared to CoT
- **Cost Reduction**: Significantly reduces API costs due to fewer tokens
- **Lower Latency**: Faster responses due to less text generation
- **Comparable Accuracy**: Despite using fewer tokens, maintains similar or better accuracy compared to CoT

## How Chain of Draft Works

Chain of Draft works by instructing the LLM to use concise, minimalistic reasoning steps instead of verbose explanations. For example:

**Chain of Thought (CoT):**
```
To solve this problem, I need to find how many lollipops Jason gave to Denny.
Initially, Jason had 20 lollipops.
After giving some to Denny, Jason now has 12 lollipops.
To find out how many lollipops Jason gave to Denny, I need to calculate the difference between the initial number and the remaining number.
20 - 12 = 8
Therefore, Jason gave 8 lollipops to Denny.
```

**Chain of Draft (CoD):**
```
20 - x = 12; x = 20 - 12 = 8.
```

Both approaches arrive at the same answer, but CoD uses significantly fewer tokens.

## Implementation Details

This implementation uses Flock's agent framework to create a multi-step reasoning workflow:

1. **Problem Analyzer Agent**: Analyzes the problem and produces the first reasoning step
2. **Reasoning Step Agent**: Performs intermediate reasoning steps until a conclusion is reached
3. **Final Answer Agent**: Extracts the final answer from the reasoning steps

The workflow is orchestrated by a specialized router that determines when to continue with more reasoning steps or when to finalize the answer.

## Project Structure

```
chain-of-draft/
├── README.md              # This file
├── 2502.18600v1.pdf       # The original research paper
├── src/                   # Implementation code
│   ├── __init__.py
│   ├── chain_of_draft.py  # Core CoD implementation
│   ├── agents.py          # CoD-specific agents
│   ├── router.py          # Routing logic for CoD steps
│   ├── prompts.py         # Prompt templates
│   └── evaluation.py      # Evaluation utilities
├── tests/                 # Test cases
│   ├── __init__.py
│   ├── test_cod_basic.py
│   └── test_cod_vs_cot.py
└── examples/              # Example use cases
    ├── arithmetic.py      # Arithmetic reasoning
    ├── comparison.py      # CoD vs CoT comparison
    └── symbolic.py        # Symbolic reasoning
```

## Installation

This implementation is part of the Flock framework. Make sure you have Flock installed:

```bash
pip install flock-core
```

## Quick Start

```python
import asyncio
from flock.core import Flock
from src.chain_of_draft import create_chain_of_draft_workflow

async def main():
    # Initialize Flock
    flock = Flock(model="openai/gpt-4o")
    
    # Create a Chain of Draft workflow for arithmetic reasoning
    flock = create_chain_of_draft_workflow(flock, "arithmetic")
    
    # Run the workflow
    result = await flock.run_async(
        start_agent="problem_analyzer",
        input={"problem": "If there are 5 apples and 3 oranges in a basket, and 2 apples are removed, how many fruits remain in the basket?"}
    )
    
    print(f"Answer: {result['answer']}")
    print(f"Reasoning steps: {result['reasoning_steps']}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Running Examples

The `examples` directory contains several demonstration scripts:

### Arithmetic Reasoning

```bash
python examples/arithmetic.py
```

This runs Chain of Draft on several arithmetic problems and displays the results.

### Symbolic Reasoning

```bash
python examples/symbolic.py
```

This demonstrates Chain of Draft on probability and coin flip problems.

### Comparing CoD vs CoT

```bash
python examples/comparison.py
```

This runs both Chain of Draft and Chain of Thought on the same problems and compares their performance in terms of token usage, execution time, and accuracy.

## Running Tests

```bash
pytest tests/
```

## Token Counting

This implementation includes a simple token counter that estimates token usage. For more accurate token counting, you could integrate with the tokenizer from your LLM provider.

## Customization

You can customize the Chain of Draft implementation:

- Modify the prompts in `prompts.py` to adjust the reasoning style
- Change the maximum number of reasoning steps in `create_chain_of_draft_workflow`
- Add additional agent types for specialized reasoning tasks

## References

- [Chain of Draft: Thinking Faster by Writing Less](https://arxiv.org/abs/2502.18600) (Xu et al., 2025)
- [Flock Agent Framework](https://github.com/whiteducksoftware/flock) 