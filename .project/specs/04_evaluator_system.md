# Flock Evaluator System Specification

## Overview
The evaluator system is responsible for processing agent inputs and generating outputs. It defines how agents interact with language models, including prompt formulation, model configuration, and output processing. This specification outlines the requirements and architecture of the evaluator system.

## Core Components

### 1. FlockEvaluator

**Implementation:** `src/flock/core/flock_evaluator.py`

**Purpose:**
Abstract base class defining the interface for all evaluators.

**Requirements:**
- Must define an `evaluate(agent, inputs, context)` method
- Must handle varied input and output formats
- Must integrate with tools if provided
- Should support caching when enabled

### 2. DeclarativeEvaluator

**Implementation:** `src/flock/evaluators/declarative/declarative_evaluator.py`

**Purpose:**
Standard evaluator that generates outputs based on agent's declared inputs and outputs.

**Configuration:**
- `agent_type_override`: Optional override for agent type
- `model`: The LLM to use for evaluation (default: openai/gpt-4o)
- `use_cache`: Whether to cache evaluation results (default: True)
- `temperature`: Sampling temperature (default: 0.0)
- `max_tokens`: Maximum generated tokens (default: 4096)

**Behavior:**
1. Creates a DSPy signature from agent input/output declarations
2. Configures the language model with appropriate settings
3. Selects the task type based on tool requirements
4. Executes the task with provided inputs
5. Processes and returns the structured results

**Mixins:**
- `DSPyIntegrationMixin`: Provides DSPy framework integration
- `PromptParserMixin`: Handles prompt parsing and formatting

## Evaluator Integration

### Agent Integration
The FlockAgent must:
- Store the evaluator in its `evaluator` attribute
- Call `evaluator.evaluate()` during its own `evaluate()` method
- Pass the appropriate context and inputs to the evaluator

### Factory Integration
The FlockFactory must:
- Create and configure the appropriate evaluator based on agent parameters
- Attach the evaluator to the agent during creation

## Specializations

### 1. Natural Language Evaluators

**Implementation:** `src/flock/evaluators/natural_language/`

**Purpose:**
Evaluators that use natural language processing techniques.

### 2. Memory-Enhanced Evaluators 

**Implementation:** `src/flock/evaluators/memory/`

**Purpose:**
Evaluators that incorporate memory capabilities for stateful conversations and reasoning.

## Design Principles

1. **Separation of Concerns**:
   - Evaluators handle prompt creation and model interaction
   - Agents define inputs and outputs
   - Clear division of responsibilities

2. **Flexibility**:
   - Support for different model providers via LiteLLM
   - Configurable parameters for each evaluation
   - Extensible through specializations

3. **Consistency**:
   - Standard interface for all evaluators
   - Predictable input and output processing
   - Common error handling patterns

4. **Performance**:
   - Built-in caching support
   - Efficient DSPy integration
   - Optimized model calls

## Implementation Requirements

1. Evaluators must be serializable
2. Evaluators should have minimal dependencies on specific model providers
3. Error handling should be graceful and informative
4. Caching should be configurable and efficient
5. Tool integration should be seamless and standardized 