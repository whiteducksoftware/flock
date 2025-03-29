# Implement TOML Serialization for FlockAgent

## Summary

Add TOML serialization and deserialization support for FlockAgent classes.

## Description

This task involves extending the FlockAgent class with methods to save and load agent configurations in TOML format. The TOML format will provide a more human-readable and editable alternative to the existing JSON serialization, making it easier for developers to create and modify agent definitions manually.

## User Story

[US007-TOML-Serialization](.project/userstories/US007-TOML-Serialization.md)

## Technical Requirements

1. Add methods to the FlockAgent class:
   - `save_to_toml_file()`: Save agent to a TOML file
   - `load_from_toml_file()`: Load agent from a TOML file
2. Create a human-readable representation of agent properties in TOML
3. Handle special cases like callables (functions, methods) through a reference system
4. Create a serialization format that preserves all agent functionality
5. Include helpful comments in the generated TOML files

## Test Requirements

The following tests should be implemented to verify the FlockAgent TOML serialization functionality:

1. **Basic Agent Serialization Tests**:
   - Test serializing a simple agent with basic properties (name, description, model)
   - Test round-trip serialization (save to TOML and load back)
   - Verify all basic properties are preserved after serialization cycle

2. **Input/Output Field Tests**:
   - Test serializing agents with various input/output field formats (simple strings, typed fields, with descriptions)
   - Test serializing agents with callable input/output definitions
   - Verify input/output field definitions are correctly preserved

3. **Component Serialization Tests**:
   - Test serializing agents with custom evaluators
   - Test serializing agents with attached modules
   - Test serializing agents with handoff routers
   - Verify all components can be serialized and deserialized correctly

4. **Tool Reference Tests**:
   - Test serializing agents with built-in tools
   - Test serializing agents with custom tool functions
   - Verify tool references are correctly serialized and resolved on deserialization

5. **Format Validation Tests**:
   - Verify generated TOML follows the spec defined in user story
   - Test that comments and documentation in TOML files are useful and correct
   - Verify the TOML is formatted in a human-readable way

6. **Error Case Tests**:
   - Test handling of invalid TOML input
   - Test handling of missing required fields
   - Test handling of incompatible field types

7. **Complex Agent Tests**:
   - Test serializing a complete agent with all possible features
   - Create an end-to-end test that creates, saves, loads, and runs an agent

All tests should use pytest fixtures to manage test agents and follow project conventions for test organization.

## Implementation Plan

1. Extend the FlockAgent class with TOML serialization methods:
   - Implement `save_to_toml_file(file_path: str)` method
   - Implement `load_from_toml_file(cls, file_path: str)` class method
2. Create a strategy for handling callable objects in TOML:
   - For built-in tools, use named references
   - For custom functions, either pickle them or store a reference to their location
3. Add documentation in the form of comments to the generated TOML
4. Add appropriate file extension handling (`.toml`)
5. Create a test case that verifies:
   - An agent can be saved to TOML
   - The TOML file is human-readable
   - The agent can be loaded back from TOML with identical functionality
6. Update docstrings and examples

## Definition of Done

1. FlockAgent can be saved to a TOML file with a clear, human-readable format
2. FlockAgent can be loaded from a TOML file with all functionality preserved
3. Generated TOML files include helpful comments
4. All edge cases (tools, modules, evaluators) are handled correctly
5. Unit tests verify the serialization cycle works correctly
6. Documentation is updated with TOML examples

## Dependencies

- [US007-T001-TOML-Serializable-Base](.project/tasks/US007-T001-TOML-Serializable-Base.md) should be completed first

## Related Tasks

- [US007-T003-Flock-TOML-Serialization](.project/tasks/US007-T003-Flock-TOML-Serialization.md)
- [US007-T004-Callable-Reference-System](.project/tasks/US007-T004-Callable-Reference-System.md)

## Estimated Effort

Medium (3-4 hours)

## Priority

High

## Assignee

Unassigned

## Status

Not Started
