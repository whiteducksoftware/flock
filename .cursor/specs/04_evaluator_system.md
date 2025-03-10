# Flock Evaluator System Specification

## Overview
The evaluator system provides the core evaluation mechanism for agents, defining how inputs are processed and outputs are generated. It abstracts the interaction with language models and provides a standardized interface for agent evaluation.

## Core Evaluator Components

### 1. FlockEvaluatorConfig

**Purpose:**
Base configuration class for all evaluator configurations.

**Requirements:**
- Must extend Pydantic's BaseModel
- Must include common configuration options for model interaction

**Standard Fields:**
- Model identifier
- Caching preferences
- Temperature settings
- Token limits

### 2. FlockEvaluator

**Purpose:**
Base abstract class for all evaluators.

**Requirements:**
- Must implement an `evaluate` method that processes agent inputs
- Must handle tool execution when applicable
- Must properly format inputs based on agent definitions
- Must process and structure outputs according to agent output definitions

**API:**
- `evaluate(agent, inputs, tools)`: Asynchronous method to evaluate inputs and produce structured outputs

## Standard Evaluators

### 1. DeclarativeEvaluator

**Purpose:**
Default evaluator that uses a declarative approach, focusing on input/output mapping.

**Functionality:**
- Creates DSPy signatures from agent definitions
- Configures language models appropriately
- Selects appropriate agent tasks based on tool requirements
- Processes model results into structured outputs

**Configuration:**
- `agent_type_override`: Optional override for agent type
- `model`: Model identifier (default: 'openai/gpt-4o')
- `use_cache`: Whether to cache results (default: True)
- `temperature`: Model temperature (default: 0.0)
- `max_tokens`: Maximum token generation (default: 4096)

## Integration Points

### DSPy Integration

**Requirements:**
- Must support DSPy for language model interactions
- Must properly convert agent definitions to DSPy signatures
- Must support DSPy caching when enabled

### Tool Execution

**Requirements:**
- Must properly format tools for model access
- Must handle tool execution when requested by the model
- Must support synchronous and asynchronous tools
- Must properly format tool results for the model

## Design Principles

1. **Modularity**:
   - Evaluators should be interchangeable
   - Different evaluation strategies possible with same agent definition

2. **Abstraction**:
   - Hide complexity of model interactions
   - Provide a consistent interface regardless of underlying model

3. **Flexibility**:
   - Support different model providers
   - Support different evaluation strategies
   - Allow configuration of evaluation parameters

4. **Performance**:
   - Support caching of results
   - Optimize token usage
   - Handle rate limiting appropriately

## Implementation Requirements

1. Evaluators must be serializable
2. Evaluators must handle exceptions gracefully
3. Evaluators should provide appropriate debugging information
4. Evaluators should support observability through tracing
5. Evaluators should maintain compatibility with multiple model providers 