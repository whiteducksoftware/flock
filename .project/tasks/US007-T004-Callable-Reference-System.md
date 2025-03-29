# Implement Callable Reference System for TOML Serialization

## Summary
Create a system to represent callable objects (functions, methods) in TOML format using human-readable references.

## Description
One of the challenges with serializing agent systems to TOML is handling callable objects like tools, evaluators, and functions. Currently, these are serialized as hex-encoded pickle data in JSON, which is not human-readable or editable. This task involves creating a reference system that can represent callables in a human-readable way in TOML files, while still enabling full functionality when loaded back.

## User Story
[US007-TOML-Serialization](.project/userstories/US007-TOML-Serialization.md)

## Technical Requirements
1. Create a registry system for common tools and functions
2. Implement a way to reference registered callables by name in TOML
3. Create a path-based reference system for custom callables
4. Implement fallback to pickle for callables that can't be referenced
5. Ensure the system can serialize and deserialize all types of callables used in Flock

## Implementation Plan
1. Create a `CallableRegistry` class:
   - Implement methods to register and retrieve callables
   - Pre-register all built-in tools and common functions
   - Add support for user-defined registrations
2. Implement serialization helpers:
   - Create a function to convert a callable to a reference string
   - Create a function to resolve a reference string back to a callable
3. Add TOML-specific serialization code:
   - When serializing to TOML, convert callables to references
   - When deserializing from TOML, resolve references to callables
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
3. TOML serialization can represent all types of callables
4. All common built-in tools are pre-registered
5. Documentation explains how to use the reference system
6. Unit tests verify the system works for all callable types

## Dependencies
- [US007-T001-TOML-Serializable-Base](.project/tasks/US007-T001-TOML-Serializable-Base.md)

## Related Tasks
- [US007-T002-FlockAgent-TOML-Serialization](.project/tasks/US007-T002-FlockAgent-TOML-Serialization.md)
- [US007-T003-Flock-TOML-Serialization](.project/tasks/US007-T003-Flock-TOML-Serialization.md)

## Estimated Effort
Medium (3-5 hours)

## Priority
High

## Assignee
Unassigned

## Status
Not Started 