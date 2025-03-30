# Add YAML Serialization to Serializable Base Class

## Summary

Extend the Serializable base class to support YAML serialization and deserialization.

## Description

The `Serializable` abstract base class in `src/flock/core/serialization/serializable.py` currently supports JSON and msgpack serialization. This task involves adding YAML serialization capabilities to this class to enable a more human-readable format for serialized objects with better support for complex nested structures.

## User Story

[US007-YAML-Serialization](.project/userstories/US007-YAML-Serialization.md)

## Technical Requirements

1. Add YAML-related methods to the `Serializable` class:
   - `to_yaml()`: Convert instance to YAML string
   - `from_yaml()`: Create instance from YAML string
   - `to_yaml_file()`: Save instance to YAML file
   - `from_yaml_file()`: Load instance from YAML file
2. Handle Python types correctly in YAML conversion
3. Add proper error handling for YAML serialization
4. Ensure all methods have appropriate docstrings
5. Leverage YAML's advanced features like anchors and references where appropriate

## Test Requirements

The following tests should be implemented to verify the YAML serialization functionality in the base class:

1. **Basic Type Tests**:
   - Test serializing objects with primitive types (string, int, float, bool)
   - Test serializing objects with complex types (list, dict, nested structures)
   - Test serializing objects with special characters and edge cases

2. **File Operation Tests**:
   - Test `to_yaml_file()` creates files with correct content
   - Test `from_yaml_file()` loads objects correctly
   - Test file path handling (non-existent directories, permissions)
   - Test round-trip serialization (to file and back)

3. **Error Handling Tests**:
   - Test handling of malformed YAML input
   - Test handling of incompatible types
   - Test proper exception raising and error messages

4. **Mock Class Tests**:
   - Create a simple mock implementation of Serializable
   - Test full serialization cycle with the mock class
   - Verify all properties are preserved after serialization

All tests should use the pytest framework and follow the existing testing patterns in the codebase.

## Implementation Plan

1. Add the `pyyaml` package import to `serializable.py` (add to project dependencies if needed)
2. Implement `to_yaml()` method that converts the object's dictionary representation to YAML format
3. Implement `from_yaml()` static method that converts a YAML string to a dictionary and then to an object
4. Implement `to_yaml_file()` and `from_yaml_file()` methods for file operations
5. Add appropriate error handling for all new methods
6. Add unit tests for the new YAML serialization methods
7. Update docstrings to include examples of YAML serialization

## Definition of Done

1. All specified methods are implemented in the `Serializable` class
2. Unit tests verify serialization and deserialization work correctly
3. Documentation is updated with examples of YAML usage
4. Code passes all linting checks
5. PR is approved and merged

## Dependencies

- `pyyaml` package

## Related Tasks

- [US007-T007-YAML-Serialization-Tests](.project/tasks/done/US007-T007-YAML-Serialization-Tests.md)
- [US007-T002-FlockAgent-YAML-Serialization](.project/tasks/US007-T002-FlockAgent-YAML-Serialization.md)
- [US007-T003-Flock-YAML-Serialization](.project/tasks/US007-T003-Flock-YAML-Serialization.md)

## Estimated Effort

Small (1-2 hours)

## Priority

High

## Assignee

Unassigned

## Status

Not Started
