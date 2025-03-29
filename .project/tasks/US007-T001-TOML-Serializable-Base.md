# Add TOML Serialization to Serializable Base Class

## Summary
Extend the Serializable base class to support TOML serialization and deserialization.

## Description
The `Serializable` abstract base class in `src/flock/core/serialization/serializable.py` currently supports JSON and msgpack serialization. This task involves adding TOML serialization capabilities to this class to enable a more human-readable format for serialized objects.

## User Story
[US007-TOML-Serialization](.project/userstories/US007-TOML-Serialization.md)

## Technical Requirements
1. Add TOML-related methods to the `Serializable` class:
   - `to_toml()`: Convert instance to TOML string
   - `from_toml()`: Create instance from TOML string
   - `to_toml_file()`: Save instance to TOML file
   - `from_toml_file()`: Load instance from TOML file
2. Handle Python types correctly in TOML conversion
3. Add proper error handling for TOML serialization
4. Ensure all methods have appropriate docstrings

## Implementation Plan
1. Add the `toml` package import to `serializable.py` (check if it's already installed in project dependencies)
2. Implement `to_toml()` method that converts the object's dictionary representation to TOML format
3. Implement `from_toml()` static method that converts a TOML string to a dictionary and then to an object
4. Implement `to_toml_file()` and `from_toml_file()` methods for file operations
5. Add appropriate error handling for all new methods
6. Add unit tests for the new TOML serialization methods
7. Update docstrings to include examples of TOML serialization

## Definition of Done
1. All specified methods are implemented in the `Serializable` class
2. Unit tests verify serialization and deserialization work correctly
3. Documentation is updated with examples of TOML usage
4. Code passes all linting checks
5. PR is approved and merged

## Dependencies
- `toml` package (already used in the theme system)

## Related Tasks
- [US007-T002-FlockAgent-TOML-Serialization](.project/tasks/US007-T002-FlockAgent-TOML-Serialization.md)
- [US007-T003-Flock-TOML-Serialization](.project/tasks/US007-T003-Flock-TOML-Serialization.md)

## Estimated Effort
Small (1-2 hours)

## Priority
High

## Assignee
Unassigned

## Status
Not Started 