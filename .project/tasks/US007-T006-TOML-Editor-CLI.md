# Implement CLI TOML Editor for Agent Configurations

## Summary

Add a TOML editor to the CLI application that allows users to view, create, and edit agent and agent system configuration files.

## Description

Now that agents and Flock systems can be serialized to and from TOML files, users need a convenient way to edit these files directly within the CLI application. This task involves creating a TOML editor similar to the existing settings editor, but specifically designed for agent configurations, with features tailored to the structure of agent and system TOML files.

## User Story

[US007-TOML-Serialization](.project/userstories/US007-TOML-Serialization.md)

## Technical Requirements

1. Add a "Agent Editor" option to the CLI main menu
2. Implement a file browser to locate and select agent/system TOML files
3. Create a TOML file viewer with syntax highlighting for agent configurations
4. Implement an editor interface for modifying agent properties
5. Add validation for agent configuration changes
6. Implement file saving with automatic backup
7. Add agent creation wizard for generating new agent configurations
8. Provide templates for common agent types

## Test Requirements

The following tests should be implemented to verify the TOML Editor CLI functionality:

1. **CLI Integration Tests**:
   - Test that the Agent Editor appears in the main CLI menu
   - Verify navigation to and from the editor works correctly
   - Test keyboard shortcuts and navigation within the editor
   - Verify the editor respects CLI theme settings

2. **File Browser Tests**:
   - Test browsing through the file system to locate TOML files
   - Verify file filtering shows only relevant files
   - Test previewing agent TOML files before opening
   - Verify handling of invalid or non-agent TOML files

3. **Viewer Component Tests**:
   - Test syntax highlighting for different TOML elements
   - Verify all agent properties are displayed correctly
   - Test rendering of comments and documentation
   - Verify handling of large files and performance

4. **Editor Interface Tests**:
   - Test editing simple properties (strings, numbers, booleans)
   - Verify editing complex properties (tools, evaluators, routers)
   - Test validation feedback for invalid changes
   - Verify UI responds appropriately to different input types

5. **Wizard Tests**:
   - Test agent creation wizard flow from start to finish
   - Verify all agent templates can be created successfully
   - Test each step of the wizard for correct validation
   - Verify generated TOML files are valid and loadable

6. **File Operation Tests**:
   - Test saving edited files
   - Verify backup files are created before overwriting
   - Test handling of read-only files or permission issues
   - Verify handling of concurrent file modifications

7. **Validation Tests**:
   - Test validation of agent properties (name, model, etc.)
   - Verify validation of tool references
   - Test validation of evaluator configurations
   - Verify error messages are clear and helpful

8. **Integration Tests with Flock**:
   - Test creating an agent in the editor and loading it in Flock
   - Verify editing an existing agent preserves functionality
   - Test creating a complete system and running it
   - Verify compatibility with all agent features

9. **UI Usability Tests**:
   - Verify clear feedback for user actions
   - Test keyboard navigation throughout the editor
   - Verify help text and documentation is accessible
   - Test UI responsiveness and performance

All tests should follow project testing conventions and focus on both functionality and usability.

## Implementation Plan

1. Extend the CLI menu to include an "Agent Editor" option
2. Create a file browser component for navigating to agent TOML files
   - Add support for listing files with `.toml` extension
   - Display preview of agent configuration when selecting a file
3. Implement a TOML viewer component:
   - Add syntax highlighting for TOML structure
   - Clearly display agent properties (name, model, tools, etc.)
   - Show comments and documentation in the file
4. Create an editor interface:
   - Allow editing of simple properties (name, model, description)
   - Provide special editors for complex properties (tools, evaluators)
   - Implement validation for changes
5. Add agent creation wizard:
   - Create step-by-step wizard for defining new agents
   - Provide templates for common agent types
   - Generate valid TOML with helpful comments
6. Implement saving with validation and backup:
   - Validate changes before saving
   - Create backups of existing files
   - Provide error messages for invalid configurations

## Definition of Done

1. Users can access the Agent Editor from the CLI main menu
2. Users can browse, select, and view agent TOML files
3. The editor provides a clear view of agent configuration with syntax highlighting
4. Users can edit agent properties with appropriate validation
5. Changes can be saved to TOML files with automatic backups
6. New agent configurations can be created from scratch or templates
7. The editor works with both individual agent files and complete system files
8. Changes made in the editor produce valid TOML files that can be loaded by Flock

## Dependencies

- [US007-T001-TOML-Serializable-Base](.project/tasks/US007-T001-TOML-Serializable-Base.md)
- [US007-T002-FlockAgent-TOML-Serialization](.project/tasks/US007-T002-FlockAgent-TOML-Serialization.md)
- [US007-T003-Flock-TOML-Serialization](.project/tasks/US007-T003-Flock-TOML-Serialization.md)

## Related Tasks

- [US007-T004-Callable-Reference-System](.project/tasks/US007-T004-Callable-Reference-System.md)
- [US007-T005-TOML-Documentation-and-Examples](.project/tasks/US007-T005-TOML-Documentation-and-Examples.md)

## Estimated Effort

Medium-Large (5-7 hours)

## Priority

Medium

## Assignee

Unassigned

## Status

Not Started
