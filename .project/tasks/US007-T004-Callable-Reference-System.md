# Implement Callable Reference System for YAML Serialization

## Summary

Create a system to represent callable objects (functions, methods) in YAML format using human-readable references.

## Description

One of the challenges with serializing agent systems to YAML is handling callable objects like tools, evaluators, and functions. Currently, these are serialized as hex-encoded pickle data in JSON, which is not human-readable or editable. This task involves creating a reference system that can represent callables in a human-readable way in YAML files, while still enabling full functionality when loaded back.

## User Story

[US007-YAML-Serialization](.project/userstories/US007-YAML-Serialization.md)

## Technical Requirements

1. Create a registry system for common tools and functions
2. Implement a way to reference registered callables by name in YAML
3. Create a path-based reference system for custom callables
4. Implement fallback to pickle for callables that can't be referenced
5. Ensure the system can serialize and deserialize all types of callables used in Flock
6. Consider leveraging YAML anchors and references for complex relationships if appropriate

## Test Requirements

The following tests should be implemented to verify the Callable Reference System functionality:

1. **Registry Reference Tests**:
   - Test registering a callable in the registry
   - Test retrieving a callable from the registry
   - Test converting a registered callable to a reference and back
   - Test handling of non-existent registry references

2. **Import Reference Tests**:
   - Test referencing a callable by import path
   - Test resolving import path references to actual callables
   - Test handling of various import formats (module, class methods, etc.)
   - Test handling of invalid import paths

3. **Pickle Fallback Tests**:
   - Test fallback to pickle for non-referenceable callables
   - Test round-trip serialization via pickle
   - Test handling of unpicklable objects
   - Verify pickle references are tagged appropriately in YAML

4. **Complex Callable Tests**:
   - Test handling of lambdas and anonymous functions
   - Test handling of class methods and instance methods
   - Test handling of closures with captured variables
   - Test handling of decorated functions

5. **Integration Tests with Agent System**:
   - Test referencing tools used by agents
   - Test referencing evaluators and routers
   - Test referencing input/output callables
   - Verify functions work correctly after deserialization

6. **Reference Format Tests**:
   - Verify reference strings are formatted correctly
   - Test parsing reference strings of different formats
   - Test handling of malformed reference strings
   - Test human-readability of reference strings

7. **Performance Tests**:
   - Benchmark reference resolution performance
   - Compare to direct pickle serialization
   - Test with a large number of callable references

All tests should use pytest fixtures to set up test functions and registries. Mock functions with different characteristics should be used to test various callable types.

## Implementation Plan

1. Create a `CallableRegistry` class:
   - Implement methods to register and retrieve callables
   - Pre-register all built-in tools and common functions
   - Add support for user-defined registrations
2. Implement serialization helpers:
   - Create a function to convert a callable to a reference string
   - Create a function to resolve a reference string back to a callable
3. Add YAML-specific serialization code:
   - When serializing to YAML, convert callables to references
   - When deserializing from YAML, resolve references to callables
4. Handle different reference types:
   - Registry references (e.g., `@registry:web_search`)
   - Import references (e.g., `@import:module.submodule:function_name`)
   - Pickle fallback (e.g., `@pickle:base64_encoded_data`)
5. Create tests for the reference system:
   - Test registry resolution
   - Test import resolution
   - Test pickle fallback
   - Test full serialization cycle

## Definition of Done

1. CallableRegistry class is implemented and tested
2. Reference conversion and resolution functions work correctly
3. YAML serialization can represent all types of callables
4. All common built-in tools are pre-registered
5. Documentation explains how to use the reference system
6. Unit tests verify the system works for all callable types

## Dependencies

- [US007-T001-YAML-Serializable-Base](.project/tasks/US007-T001-YAML-Serializable-Base.md)

## Related Tasks

- [US007-T002-FlockAgent-YAML-Serialization](.project/tasks/US007-T002-FlockAgent-YAML-Serialization.md)
- [US007-T003-Flock-YAML-Serialization](.project/tasks/US007-T003-Flock-YAML-Serialization.md)

## Estimated Effort

Medium (3-5 hours)

## Priority

High

## Assignee

Unassigned

## Status

Not Started
