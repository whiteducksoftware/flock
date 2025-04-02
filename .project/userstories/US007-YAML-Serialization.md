# User Story: YAML Serialization for Agents and Flock

## ID

US007

## Title

Add YAML Serialization Support for Agents and Flock Systems

## Description

As a Flock developer, I want to save and load agent definitions and complete Flock systems in YAML format so that I can have a more human-readable configuration format with support for complex nested structures and easily edit agent definitions manually.

## Current State

Currently, Flock and FlockAgent instances can be serialized to and deserialized from JSON files. The JSON serialization works well for programmatic interactions but has several limitations:

1. JSON is not human-friendly for manual editing of complex nested structures
2. JSON doesn't support comments, making it difficult to document configuration
3. The current approach serializes callables as hex strings, making the files nearly impossible to edit manually
4. There's no standard way to create a human-readable representation of the agent system

## Desired State

After implementation, users should be able to:

1. Save FlockAgent instances to YAML files with a clean, readable format
2. Load FlockAgent instances from YAML files
3. Save entire Flock systems (with multiple agents) to YAML files
4. Load entire Flock systems from YAML files
5. Manually edit these YAML files with proper documentation and examples

The YAML format should:

- Support all the same capabilities as the existing JSON serialization
- Provide a more human-friendly representation of agent configurations
- Include comments that document the purpose of each section
- Handle callables in a way that makes them replaceable via configuration
- Leverage YAML anchors and references for complex object structures

## Technical Details

The implementation will build on the existing serialization framework in `src/flock/core/serialization/`. We'll need to:

1. Add YAML serialization methods to the `Serializable` base class
2. Implement `to_yaml` and `from_yaml` methods for both `FlockAgent` and `Flock` classes
3. Create a strategy for handling callables in YAML (likely using named references to registered functions)
4. Add support for YAML file detection based on extension
5. Update relevant documentation

**Required Dependencies:**

- `pyyaml` package (a common YAML implementation for Python)

## Implementation Tasks Status

| ID | Task | Priority | Status | Description |
|----|------|----------|--------|-------------|
| US007-T007 | [YAML Serialization Tests](../tasks/done/US007-T007-YAML-Serialization-Tests.md) | Highest | Completed | Create a comprehensive test suite for YAML serialization following TDD principles |
| US007-T001 | [YAML Serializable Base](../tasks/done/US007-T001-YAML-Serializable-Base.md) | High | Completed | Extend the Serializable base class to support YAML serialization |
| US007-T004 | [Callable Reference System](../tasks/done/US007-T004-Callable-Reference-System.md) | High | Completed | Create a system to represent callable objects in YAML using human-readable references |
| US007-T002.1 | [FlockAgent YAML Formatting](../tasks/done/US007-T002.1-FlockAgent-YAML-Formatting.md) | High | Completed | Enhance FlockAgent YAML output with human-readable formatting and descriptive comments |
| US007-T002.2 | [FlockAgent YAML Examples](../tasks/done/US007-T002.2-FlockAgent-YAML-Examples.md) | Medium | Completed | Create example YAML files for common FlockAgent configurations |
| US007-T003.1 | [Flock System YAML Formatting](../tasks/done/US007-T003.1-Flock-System-YAML-Formatting.md) | Medium | Completed | Enhance Flock YAML output with human-readable formatting and descriptive comments |
| US007-T003.2 | [YAML Schema Documentation](../tasks/done/US007-T003.2-YAML-Schema-Documentation.md) | Medium | Completed | Create schema documentation for YAML files |
| US007-T005 | [YAML Documentation and Examples](../tasks/US007-T005-YAML-Documentation-and-Examples.md) | Medium | Not Started | Create comprehensive documentation and examples for YAML serialization |
| US007-T006 | [YAML Editor CLI](../tasks/US007-T006-YAML-Editor-CLI.md) | Medium | Not Started | Add a YAML editor to the CLI application for editing agent and system configurations |

## Learnings

This section documents important lessons learned during the implementation of each task to help future developers avoid similar pitfalls.

### Task US007-T007: YAML Serialization Tests

#### Error 1: Inadequate Code Analysis Before Writing Tests

**Problem**: Tests were initially written without thoroughly examining all class properties and relationships in the codebase. This led to testing non-existent properties (e.g., `use_tools` in FlockAgent) and incorrect assumptions about class behavior.

**Solution**: 
- Always thoroughly examine the actual class definitions before writing tests
- Use techniques like reading the source files and analyzing inheritance hierarchies
- Create a checklist of all properties and methods to be tested
- Cross-reference the checklist with the actual code

#### Error 2: Improper Mock Implementation of Abstract Classes

**Problem**: Mock implementations of abstract classes (like FlockEvaluator) were initially created without properly implementing all required abstract methods, or with incorrect method signatures.

**Solution**:
- Carefully check all abstract methods that need implementation
- Ensure method signatures match the parent class (parameters, return types)
- Include proper async/await patterns if methods are asynchronous
- Test mock classes in isolation before using them in larger test cases

#### Error 3: Missing Tests for Key Components

**Problem**: Initial tests did not cover all critical components of the serialization process, such as modules, routers, and tools.

**Solution**:
- Create a comprehensive inventory of all components that require serialization
- Develop dedicated test cases for each component type
- Test components both in isolation and as part of complex objects
- Include edge cases for each component type

#### Error 4: Incorrect Test Structure for Complex Objects

**Problem**: Tests for complex objects with nested components were not structured to properly verify that all parts of the object were correctly serialized and deserialized.

**Solution**:
- Use assertions that explicitly verify the structure of serialized objects
- Check that all nested components are properly represented
- Verify that relationships between components are maintained after deserialization
- Test serialization cycles (object → serialized form → deserialized object)

#### Error 5: Insufficient Error Handling Testing

**Problem**: Initial tests focused on the happy path but did not adequately test error handling for malformed input, missing properties, or incompatible types.

**Solution**:
- Include specific test cases for error conditions
- Verify appropriate exceptions are raised for invalid input
- Test boundary conditions (empty strings, null values, etc.)
- Ensure error messages are informative and helpful

#### Error 6: Not Utilizing Existing Code as Reference

**Problem**: Tests were written without examining how existing serialization methods (e.g., to_json, from_json) were implemented, missing opportunities to maintain consistency.

**Solution**:
- Study existing serialization implementations as a reference
- Ensure new methods follow similar patterns and conventions
- Reuse existing utility functions where appropriate
- Maintain consistent behavior between different serialization formats

### Task US007-T001: YAML Serializable Base

#### Learning 1: Importance of Maintaining Consistent Error Handling

**Problem**: Initial implementation of YAML serialization methods didn't match the error handling pattern of existing serialization methods.

**Solution**:
- Analyzed existing methods (to_json, from_json) to understand error handling patterns
- Ensured that YAML methods wrap all operations in try/except blocks consistently
- Propagated appropriate exceptions with clear error messages
- Maintained the same error handling structure across all serialization methods

#### Learning 2: Directory Creation for File Operations

**Problem**: The to_yaml_file method initially failed when the target directory didn't exist.

**Solution**:
- Added directory creation logic before writing files
- Used pathlib's mkdir(parents=True) to ensure all parent directories are created
- Set exist_ok=True to avoid race conditions if the directory is created between check and creation
- Added appropriate exception handling for permission issues

#### Learning 3: Test-First Approach Benefits

**Benefit**: Having comprehensive tests already written (per US007-T007) made implementation straightforward.

**Insight**:
- Tests provided clear requirements for each method
- Test cases covered edge cases we might have missed
- We could immediately verify that implementation satisfied all requirements
- The transition from expected failures to passing tests provided clear progress indicators

#### Learning 4: Dependency Management

**Problem**: Adding PyYAML dependency required updates in multiple places.

**Solution**:
- Added dependency to pyproject.toml first
- Used uv pip compile to regenerate requirements.txt
- Verified the dependency was properly installed in the development environment
- Followed project conventions for version specification

## Task US007-T004: Callable Reference System

*Learnings will be added as this task is implemented.*

## Task US007-T002: FlockAgent YAML Serialization

*Learnings will be added as this task is implemented.*

## Task US007-T003: Flock YAML Serialization

*Learnings will be added as this task is implemented.*

## Related Tasks

- Create YAML serialization for FlockAgent
- Create YAML serialization for Flock systems
- Implement callable reference system
- Add tests for YAML serialization
- Update documentation with YAML examples

## Implementation Progress

- **Test Suite Implementation**: Completed
  - Created tests for Serializable, FlockAgent, Flock, and callable reference system
  - Implemented integration tests for end-to-end workflows
  - Following TDD approach, tests initially fail as expected

- **Implementation Phase**: In Progress
  - Serializable base class YAML methods: **Completed**
  - Callable reference system: **Completed**
  - FlockAgent YAML serialization: **Completed**
  - Flock system YAML serialization: **Completed**
  - YAML Schema documentation: **Completed**
  - Documentation and examples: **Not Started**
  - YAML Editor CLI: **Not Started**

## Acceptance Criteria

1. A FlockAgent can be saved to a YAML file and loaded back with identical functionality
2. A complete Flock system can be saved to a YAML file and loaded back with identical functionality
3. YAML files are human-readable and include comments explaining structure
4. Serialization properly handles tools, routers, evaluators, and other complex components
5. Unit tests verify the serialization cycle works correctly
6. Documentation is updated with examples

## UI Mockups

Example YAML file format for an agent:

```yaml
# FlockAgent: example_agent
# Created: 2023-06-15 14:30:00
# This file defines a Flock agent that summarizes text

name: example_agent
model: openai/gpt-4o
description: An agent that summarizes text
input: "text: str | The text to summarize"
output: "summary: str | The summarized text"
use_cache: true

evaluator:
  name: default_evaluator
  type: NaturalLanguageEvaluator

# Tools available to this agent
tools:
  # List of tool references (from tools registry)
  references:
    - web_search
    - code_eval

# Module configurations
modules:
  output_module:
    enabled: true
    render_table: true
    wait_for_input: false
```

## Notes

1. We should maintain backward compatibility with the existing JSON serialization
2. The format should be extensible for future enhancements
3. Consider supporting conversion between formats (JSON to YAML and vice versa)
4. Handle the challenge of representing callable objects in a text format
5. Use YAML anchors and references for complex object structures where appropriate

## Tests

To ensure the YAML serialization functionality meets all requirements, the following test cases should be implemented:

### Base Serialization Tests

1. **Basic Serialization Cycle**: Test that basic Python types can be converted to YAML and back with fidelity
   - Simple objects with primitive types (strings, numbers, booleans)
   - Objects with lists, dictionaries, and nested structures
   - Objects with special characters in strings

### FlockAgent Serialization Tests

1. **Simple Agent Serialization**:
   - Test serializing an agent with basic properties
   - Test deserializing a YAML string into an agent
   - Verify agent properties match before and after serialization

2. **Complex Agent Components**:
   - Test serializing agents with custom evaluators
   - Test agents with attached modules
   - Test agents with tools and complex configurations

3. **Callable Handling**:
   - Test serialization of agents with function references (description, input, output)
   - Test serialization of agents with tool callables
   - Verify callable references can be resolved on deserialization

### Flock System Serialization Tests

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

### Format Conversion Tests

1. **JSON-YAML Interoperability**:
   - Test converting from JSON to YAML format
   - Test converting from YAML to JSON format
   - Verify data integrity across conversions

2. **Format Detection**:
   - Test automatic format detection based on file extension
   - Test handling of unknown or unsupported formats

### Integration Tests

1. **Full Workflow Tests**:
   - Test saving a complete agent system and loading it in a new session
   - Test running agents from loaded YAML configurations
   - Verify all functionality works as expected in real usage scenarios

2. **Manual Editing Tests**:
   - Test editing YAML files manually and loading the modified configurations
   - Verify comments and documentation in YAML files are preserved
   - Test human-readability and editability metrics

### Performance Tests

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

In Progress
