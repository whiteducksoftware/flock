# User Story: TOML Serialization for Agents and Flock

## ID

US007

## Title

Add TOML Serialization Support for Agents and Flock Systems

## Description

As a Flock developer, I want to save and load agent definitions and complete Flock systems in TOML format so that I can have a more human-readable configuration format and easily edit agent definitions manually.

## Current State

Currently, Flock and FlockAgent instances can be serialized to and deserialized from JSON files. The JSON serialization works well for programmatic interactions but has several limitations:

1. JSON is not human-friendly for manual editing of complex nested structures
2. JSON doesn't support comments, making it difficult to document configuration
3. The current approach serializes callables as hex strings, making the files nearly impossible to edit manually
4. There's no standard way to create a human-readable representation of the agent system

## Desired State

After implementation, users should be able to:

1. Save FlockAgent instances to TOML files with a clean, readable format
2. Load FlockAgent instances from TOML files
3. Save entire Flock systems (with multiple agents) to TOML files
4. Load entire Flock systems from TOML files
5. Manually edit these TOML files with proper documentation and examples

The TOML format should:

- Support all the same capabilities as the existing JSON serialization
- Provide a more human-friendly representation of agent configurations
- Include comments that document the purpose of each section
- Handle callables in a way that makes them replaceable via configuration

## Technical Details

The implementation will build on the existing serialization framework in `src/flock/core/serialization/`. We'll need to:

1. Add TOML serialization methods to the `Serializable` base class
2. Implement `to_toml` and `from_toml` methods for both `FlockAgent` and `Flock` classes
3. Create a strategy for handling callables in TOML (likely using named references to registered functions)
4. Add support for TOML file detection based on extension
5. Update relevant documentation

**Required Dependencies:**

- `toml` package (already used in the codebase for theme configuration)

## Related Tasks

- Create TOML serialization for FlockAgent
- Create TOML serialization for Flock systems
- Implement callable reference system
- Add tests for TOML serialization ✓
- Update documentation with TOML examples

## Implementation Progress

- **Test Suite Implementation**: Complete ✓
  - Created comprehensive tests for Serializable, FlockAgent, Flock, and callable reference system
  - Implemented integration tests for end-to-end workflows
  - Tests are currently failing as expected in TDD approach

- **Implementation Phase**: Not Started
  - Serializable base class TOML methods
  - Callable reference system
  - FlockAgent TOML serialization
  - Flock system TOML serialization

## Acceptance Criteria

1. A FlockAgent can be saved to a TOML file and loaded back with identical functionality
2. A complete Flock system can be saved to a TOML file and loaded back with identical functionality
3. TOML files are human-readable and include comments explaining structure
4. Serialization properly handles tools, routers, evaluators, and other complex components
5. Unit tests verify the serialization cycle works correctly ✓
6. Documentation is updated with examples

## UI Mockups

Example TOML file format for an agent:

```toml
# FlockAgent: example_agent
# Created: 2023-06-15 14:30:00
# This file defines a Flock agent that summarizes text

name = "example_agent"
model = "openai/gpt-4o"
description = "An agent that summarizes text"
input = "text: str | The text to summarize"
output = "summary: str | The summarized text"
use_cache = true

[evaluator]
name = "default_evaluator"
type = "NaturalLanguageEvaluator"

# Tools available to this agent
[tools]
# List of tool references (from tools registry)
references = ["web_search", "code_eval"]

# Module configurations
[modules.output_module]
enabled = true
render_table = true
wait_for_input = false
```

## Notes

1. We should maintain backward compatibility with the existing JSON serialization
2. The format should be extensible for future enhancements
3. Consider supporting conversion between formats (JSON to TOML and vice versa)
4. Handle the challenge of representing callable objects in a text format

## Tests

To ensure the TOML serialization functionality meets all requirements, the following test cases should be implemented:

### Base Serialization Tests ✓

1. **Basic Serialization Cycle**: Test that basic Python types can be converted to TOML and back with fidelity
   - Simple objects with primitive types (strings, numbers, booleans)
   - Objects with lists, dictionaries, and nested structures
   - Objects with special characters in strings

2. **File Operations**: Test saving to and loading from TOML files
   - Verify file contents match expected format
   - Verify file loading recreates identical objects
   - Test handling of file path edge cases (non-existent paths, permissions)

3. **Error Handling**: Test that appropriate exceptions are raised for invalid inputs
   - Malformed TOML strings
   - Incompatible data types
   - Missing required fields

### FlockAgent Serialization Tests ✓

1. **Simple Agent Serialization**:
   - Test serializing an agent with basic properties
   - Test deserializing a TOML string into an agent
   - Verify agent properties match before and after serialization

2. **Complex Agent Components**:
   - Test serializing agents with custom evaluators
   - Test agents with attached modules
   - Test agents with tools and complex configurations

3. **Callable Handling**:
   - Test serialization of agents with function references (description, input, output)
   - Test serialization of agents with tool callables
   - Verify callable references can be resolved on deserialization

### Flock System Serialization Tests ✓

1. **Multi-Agent Serialization**:
   - Test serializing a Flock with multiple agents
   - Test that agent relationships are preserved
   - Verify context and registry information is properly maintained

2. **Router Serialization**:
   - Test serialization of agents with routers
   - Verify router configurations and references are maintained
   - Test complex workflows with multiple handoffs

3. **Tool Registry**:
   - Test serialization of tool registries
   - Verify tool dependencies and references are maintained
   - Test deserialization correctly recreates tool access

### Format Conversion Tests ✓

1. **JSON-TOML Interoperability**:
   - Test converting from JSON to TOML format
   - Test converting from TOML to JSON format
   - Verify data integrity across conversions

2. **Format Detection**:
   - Test automatic format detection based on file extension
   - Test handling of unknown or unsupported formats

### Integration Tests ✓

1. **Full Workflow Tests**:
   - Test saving a complete agent system and loading it in a new session
   - Test running agents from loaded TOML configurations
   - Verify all functionality works as expected in real usage scenarios

2. **Manual Editing Tests**:
   - Test editing TOML files manually and loading the modified configurations
   - Verify comments and documentation in TOML files are preserved
   - Test human-readability and editability metrics

### Performance Tests ✓

1. **Serialization Performance**:
   - Benchmark serialization and deserialization speeds for various agent complexities
   - Compare performance with JSON serialization
   - Test with large-scale agent systems

## Stakeholders

- Flock developers
- Flock users who want to manually configure agents
- Flock contributors who need to debug agent configurations

## Priority

Medium

## Story Points / Effort

3 points

## Status

In Progress - Test Suite Completed, Implementation Pending
