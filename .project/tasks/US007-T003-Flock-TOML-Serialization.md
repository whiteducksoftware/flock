# Implement TOML Serialization for Flock Systems

## Summary
Add TOML serialization and deserialization support for complete Flock systems.

## Description
This task involves extending the Flock class with methods to save and load entire agent systems in TOML format. A Flock system can contain multiple agents, routers, tools, and context data, making it more complex than individual agent serialization. This implementation will allow developers to create, share, and modify complete agent systems using a human-readable format.

## User Story
[US007-TOML-Serialization](.project/userstories/US007-TOML-Serialization.md)

## Technical Requirements
1. Add methods to the Flock class:
   - `save_to_toml_file()`: Save a complete Flock system to a TOML file
   - `load_from_toml_file()`: Load a complete Flock system from a TOML file
2. Create a structured TOML format that organizes agents, tools, and system settings
3. Handle references between agents for handoff routers
4. Manage serialization of global context
5. Include helpful comments and documentation in the generated TOML

## Implementation Plan
1. Extend the Flock class with TOML serialization methods:
   - Implement `save_to_toml_file(file_path: str, start_agent: str | None = None, input: dict | None = None)` method
   - Implement `load_from_toml_file(cls, file_path: str)` class method
2. Design a TOML structure for Flock systems:
   - Top-level system configuration
   - Section for each agent
   - Global tools section
   - References for agent connections
3. Handle agent and tool serialization:
   - Call individual agent serialization methods
   - Organize tools in a central registry section
4. Manage handoff references between agents
5. Add documentation comments to the generated TOML
6. Create comprehensive test cases for:
   - Single-agent systems
   - Multi-agent workflows with handoffs
   - Systems with custom tools and evaluators
7. Update documentation with examples

## Definition of Done
1. Complete Flock systems can be saved to TOML files
2. Flock systems can be loaded from TOML files with all functionality preserved
3. Generated TOML files are human-readable and include helpful comments
4. Complex systems with multiple agents and handoffs work correctly
5. Edge cases (custom tools, evaluators, modules) are handled correctly
6. Unit tests verify the serialization cycle works correctly
7. Documentation is updated with TOML examples

## Dependencies
- [US007-T001-TOML-Serializable-Base](.project/tasks/US007-T001-TOML-Serializable-Base.md)
- [US007-T002-FlockAgent-TOML-Serialization](.project/tasks/US007-T002-FlockAgent-TOML-Serialization.md)

## Related Tasks
- [US007-T004-Callable-Reference-System](.project/tasks/US007-T004-Callable-Reference-System.md)
- [US007-T005-TOML-Documentation-and-Examples](.project/tasks/US007-T005-TOML-Documentation-and-Examples.md)

## Estimated Effort
Medium-Large (4-6 hours)

## Priority
Medium

## Assignee
Unassigned

## Status
Not Started 