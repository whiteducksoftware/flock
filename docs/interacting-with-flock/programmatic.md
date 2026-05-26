---
hide:
  - toc
---

# 🐍 Programmatic API (Python)

The most fundamental way to interact with Flock is directly within your Python code. This approach gives you the most control over execution flow, input/output handling, and integration with other Python libraries.

Once you have a configured `Flock` instance, you can trigger agent executions using several key methods:

## 1. Single Synchronous Run: `flock.run()`

This is the simplest way to execute a workflow starting from a specific agent. It runs synchronously, meaning your script will wait until the entire workflow (including any agent handoffs) completes before proceeding.

```python
from flock.core import Flock, FlockFactory

# Assume 'flock' is your configured Flock instance
# Assume 'my_agent' is a FlockAgent instance added to the flock

input_data = {"topic": "Benefits of Declarative AI"}

# Run starting with 'my_agent'
try:
    # result is a Box object (dot-accessible dict) by default
    result = flock.run(start_agent=my_agent, input=input_data)

    print("Workflow Completed!")
    print(f"Title: {result.generated_title}") # Access results easily
    print(f"Points: {result.key_points}")

except Exception as e:
    print(f"An error occurred: {e}")
```

**Use Case:** 

Simple scripts, direct integration where blocking execution is acceptable, easier debugging for linear flows.

**Returns:** 

A Box object (dot-accessible dictionary) containing the final result of the last agent executed in the chain, or a standard dictionary if box_result=False.

## 2. Single Asynchronous Run: flock.run_async()

For applications using asyncio, this method allows you to run a workflow without blocking the main event loop.

```python
import asyncio
from flock.core import Flock, FlockFactory

# Assume 'flock' and 'my_agent' are configured

async def main():
    input_data = {"topic": "Async AI Workflows"}
    try:
        result = await flock.run_async(start_agent=my_agent.name, input=input_data) # Can use agent name
        print("Async Workflow Completed!")
        print(f"Result: {result}") # result is a Box object by default
    except Exception as e:
        print(f"An error occurred: {e}")

# asyncio.run(main())
```

**Use Case:** 

Integrating Flock into asynchronous applications (like web servers), running multiple Flock workflows concurrently.

**Returns:** 

Same as flock.run(), but returns an awaitable coroutine.

## 3. Batch Processing: flock.run_batch() / flock.run_batch_async()

Process multiple input items efficiently, either sequentially or in parallel. This is ideal for tasks like generating variations, processing datasets, or evaluating agent performance.

```python
from flock.core import Flock, FlockFactory

# Assume 'flock' and 'summarizer_agent' are configured
# summarizer_agent takes 'text_to_summarize', outputs 'summary'

batch_data = [
    {"text_to_summarize": "Text block 1..."},
    {"text_to_summarize": "Another long text block..."},
    {"text_to_summarize": "Final piece of text..."}
]

static_data = {"max_summary_length": 100} # Input common to all items

try:
    # Run in parallel locally, show progress bar
    results = flock.run_batch(
        start_agent=summarizer_agent,
        batch_inputs=batch_data,
        static_inputs=static_data,
        parallel=True,
        max_workers=4,
        silent_mode=True, # Shows progress bar
        return_errors=True # Return Exceptions instead of raising
    )

    print(f"Batch processing completed for {len(results)} items.")
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            print(f"Item {i+1} failed: {res}")
        else:
            print(f"Item {i+1} Summary: {res.summary}") # Access results

except Exception as e:
    print(f"Batch processing error: {e}")

# Async version: await flock.run_batch_async(...)
```

**Use Case:** 

Processing large datasets, generating multiple outputs from varying inputs, performance testing.

**Input:** 

Can be a list of dictionaries, a pandas DataFrame, or a path to a CSV file.

**Features:** 

Parallel execution (local threads or Temporal), input mapping (for DataFrames/CSVs), static inputs, error handling options, CSV output.

**Returns:**

 A list containing the result (Box or dict) or Exception object for each input item, in the original order.

## 4. Agent Evaluation: flock.evaluate() / flock.evaluate_async()

Evaluate an agent's performance against a dataset using specified metrics.

```python
from flock.core import Flock, FlockFactory

# Assume 'flock' and 'qa_agent' are configured
# qa_agent takes 'question', outputs 'answer'

dataset_path = "path/to/qa_dataset.csv" # CSV with 'question' and 'true_answer' columns
input_mapping = {"question": "question"} # Map CSV 'question' col to agent 'question' input
answer_mapping = {"answer": "true_answer"} # Map agent 'answer' output to CSV 'true_answer' col
metrics_to_run = ["exact_match", "semantic_similarity"] # Use built-in metrics

try:
    results_df = flock.evaluate(
        dataset=dataset_path,
        start_agent=qa_agent,
        input_mapping=input_mapping,
        answer_mapping=answer_mapping,
        metrics=metrics_to_run,
        output_file="evaluation_results.csv", # Save detailed results
        return_dataframe=True,
        silent_mode=True
    )
    print("Evaluation Complete!")
    print("Average Scores:")
    print(results_df[["metric_exact_match", "metric_semantic_similarity"]].mean())

except Exception as e:
    print(f"Evaluation error: {e}")
```

**Use Case:** 

Assessing agent accuracy, comparing different models or prompts, regression testing.

**Input:** 

Hugging Face dataset ID, path to CSV, list of dictionaries, pandas DataFrame, or HF Dataset object.

**Features:** 

Input/Answer mapping, various built-in metrics (exact match, fuzzy, ROUGE, semantic similarity), custom metric functions, LLM-as-judge, parallel execution, detailed output saving.

**Returns:** 

A pandas DataFrame (if return_dataframe=True) or a list of dictionaries containing inputs, expected answers, agent output, calculated metrics, and errors for each dataset item.

Choose the programmatic method that best fits your execution needs within your Python application.

