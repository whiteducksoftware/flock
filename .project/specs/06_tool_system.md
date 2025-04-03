# Flock Tool System Specification

## Overview
The tool system provides agents with capabilities to perform actions beyond generating text. Tools can retrieve information, perform calculations, interact with external systems, or execute code. This specification defines how tools are integrated and used within the Flock framework.

**Core Implementation:** `src/flock/core/tools/`

## Tool Definition

### Requirements
- Tools must be callable functions or methods
- Tools must accept standard Python types as inputs
- Tools must return JSON-serializable outputs
- Tools should include proper docstrings for agent instruction
- Tools should handle errors gracefully

### Tool Registration
Tools can be registered in two ways:
1. Through agent definition: `tools=[tool1, tool2]`
2. Through Flock registration: `flock.add_tool("tool_name", tool_function)`

## Tool Integration

### Agent Integration
Tools attached to an agent are:
1. Registered in the global registry
2. Made available to the agent during evaluation
3. Formatted appropriately for the model to understand their capabilities

### Evaluator Integration
The evaluator is responsible for:
1. Formatting tools for model consumption
2. Detecting tool invocation in model outputs
3. Executing tools with appropriate parameters
4. Formatting tool results for continued model interaction

## Standard Tool Categories

### 1. Basic Tools

**Implementation:** `src/flock/core/tools/basic_tools.py`

- Web search tools (Tavily, DuckDuckGo, Bing)
- Web content extraction and parsing
- Code evaluation (via PythonInterpreter)
- Math evaluation
- Time and date functions
- Text parsing and extraction (URLs, numbers)
- File operations (read/write)
- JSON processing

### 2. LLM-specific Tools

**Implementation:** `src/flock/core/tools/llm_tools.py`

- Text chunking and splitting (multiple strategies)
- Token counting and management
- Keyword extraction
- Text cleaning and formatting
- Chat history formatting
- Language detection
- JSON extraction from text
- Table formatting
- Text hashing

### 3. Azure Tools

**Implementation:** `src/flock/core/tools/azure_tools.py`

- Azure-specific functionality
- Cloud resource management

### 4. Markdown Tools

**Implementation:** `src/flock/core/tools/markdown_tools.py`

- Markdown processing and generation
- Documentation creation helpers

## Tool Execution Flow

1. Agent provides tools list during initialization
2. Evaluator formats tools as function descriptions for the model
3. Model generates output that may include tool invocation
4. Evaluator parses the tool invocation and parameters
5. Evaluator executes the tool with parsed parameters
6. Tool result is formatted and provided back to the model
7. Model continues generation with tool results available
8. Final model output is returned as agent result

## Design Principles

1. **Flexibility**:
   - Support for any callable function
   - No special base classes required
   - Dynamic addition of tools possible

2. **Safety**:
   - Tools should have clear boundaries
   - Error handling to prevent failures
   - Input validation for security

3. **Discoverability**:
   - Clear documentation for agent understanding
   - Consistent interface patterns
   - Self-describing capabilities

4. **Performance**:
   - Efficient execution
   - Proper handling of async tools
   - Support for caching tool results

## Implementation Requirements

1. Tools must work with different model providers
2. Tools must handle both synchronous and asynchronous execution
3. Tools should provide clear error messages
4. Tools should be testable in isolation
5. Complex tools should be composable from simpler tools 