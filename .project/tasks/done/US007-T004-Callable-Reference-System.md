# Task: Callable Reference System

## ID

US007-T004

## User Story Reference

[US007-YAML-Serialization](../userstories/US007-YAML-Serialization.md)

## Description

Create a system to represent callable objects (functions, methods, lambdas) in YAML using human-readable references, allowing for more maintainable and editable YAML configurations.

## Status

Partially Completed - Core functionality is implemented in FlockRegistry, but enhancements are needed for better documentation and user experience.

## Current Implementation

The core callable reference functionality has been implemented in the FlockRegistry class in `src/flock/core/flock_registry.py`, which provides:

1. Registration of callables with path strings via `register_callable()`
2. Retrieval of callables by path string via `get_callable()`
3. Lookup of path strings for callables via `get_callable_path_string()`
4. Dynamic imports for callables not found in the registry

A placeholder implementation also exists in `src/flock/core/serialization/callable_registry.py`.

The serialization and deserialization of callables is handled in `src/flock/core/serialization/serialization_utils.py`, which:
1. Converts callables to reference dictionaries with `__callable_ref__` keys
2. Resolves those references back to actual callables during deserialization

## Remaining Tasks

1. **Documentation Enhancement**:
   - Add comprehensive docstrings to explain how the callable reference system works
   - Create examples showing how to register and use callable references
   - Document best practices for callable serialization

2. **Error Handling Improvements**:
   - Enhance error messages for failed callable lookups
   - Provide better guidance for troubleshooting callable serialization issues

3. **Human-Readable References**:
   - Implement a more user-friendly representation in YAML output
   - Add explanatory comments to callable references in generated YAML

4. **Interface Consistency**:
   - Decide whether to fully migrate functionality to `CallableRegistry` or keep in `FlockRegistry`
   - Update references throughout codebase to use the chosen approach consistently

## Acceptance Criteria

1. Callables can be serialized to YAML with human-readable references
2. These references can be understood and edited by users
3. When YAML is deserialized, the correct callables are resolved
4. The system handles dynamic imports of callables from known modules
5. Edge cases are handled gracefully with informative error messages
6. Documentation explains the callable reference system clearly

## Testing

1. ✅ Unit tests for callable serialization and deserialization exist
2. ✅ Tests cover simple functions, methods, and builtins
3. ❌ Tests for error handling need to be added
4. ❌ Tests for documentation accuracy need to be added

## Related Tasks

- [US007-T001-YAML-Serializable-Base](done/US007-T001-YAML-Serializable-Base.md) (Completed)
- [US007-T002.1-FlockAgent-YAML-Formatting](US007-T002.1-FlockAgent-YAML-Formatting.md) (Not Started)
- [US007-T007-YAML-Serialization-Tests](done/US007-T007-YAML-Serialization-Tests.md) (Completed)

## Notes

- Consider whether the current implementation in FlockRegistry should be migrated to the CallableRegistry class
- The current implementation allows for serialization and deserialization of callables but doesn't focus on human-readability
- Need to balance security concerns with usability when handling callable serialization
