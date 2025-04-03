# Task: YAML Editor CLI

## ID

US007-T006

## User Story Reference

[US007-YAML-Serialization](../userstories/US007-YAML-Serialization.md)

## Description

Add a YAML editor to the Flock CLI application that allows users to create, view, and edit agent and system configurations directly from the command line. This will provide a convenient way for users to work with YAML configurations without needing external tools.

The CLI should also be able to be started programmatically with an already loaded Flock system, enabling users to execute, edit, or manage agents from an existing configuration.

## Status

In Progress

## Required Changes

1. **YAML File Browser**:
   - Add a command to browse for YAML agent and system files
   - Implement navigation through directories to locate YAML files
   - Provide filtering and search capabilities for YAML files

2. **YAML Viewer**:
   - Create a command to preview YAML files in a formatted, readable way
   - Implement syntax highlighting for different YAML elements
   - Add collapsible sections for better navigation of complex files

3. **YAML Editor**:
   - Implement a command to edit YAML files with syntax validation
   - Add auto-completion for common fields and values
   - Provide templates for creating new agent configurations

4. **Validation System**:
   - Add real-time validation against expected schema
   - Implement clear error messages for invalid configurations
   - Provide suggestions to fix common errors

5. **Conversion Utilities**:
   - Add commands to convert between JSON and YAML formats
   - Implement batch conversion for multiple files
   - Provide options for different output formats and styles

6. **Programmatic CLI Initialization**:
   - Add a `start_cli()` method to the Flock class similar to the existing `start_api()` method
   - Integrate with the existing CLI framework in `src/flock/cli`
   - Support loading the CLI with a current Flock instance and its agents
   - Add a new CLI mode for loaded Flock instances

7. **Enhanced UI for Loaded Agents**:
   - Display a summary of loaded agents in the Flock system
   - Create an elegant visualization of agent components that abstracts the raw YAML
   - Provide both a visual editor and raw YAML editor option for expert users

8. **Flock Creation and Loading**:
   - When no Flock is loaded, provide options to load a *.flock.yaml file or create a new basic Flock
   - Add a new Flock creation wizard that guides users through the process of creating a basic Flock
   - Seamlessly transition to agent management after Flock creation or loading

9. **Registry Management**:
   - Add functionality to view all registered items in the Flock Registry (agents, callables, types, components)
   - Implement filtering and search capabilities for registry items by category, name, or path
   - Create commands to manually add items to the registry with proper validation
   - Add commands to remove items from the registry with appropriate warnings
   - Implement an auto-registration scanner that:
     - Scans a file, directory, or directory tree for registry-eligible items
     - Identifies classes with @flock_component, @flock_tool, and @flock_type decorators
     - Detects potential registry candidates that lack decorators
     - Allows batch registration with confirmation
     - Generates reports of newly registered items

## Main Menu Structure

When starting without a loaded Flock instance:

```
=================================
FLOCK CLI
=================================

1. Load Flock from YAML
2. Create New Flock
3. Theme Builder
4. Settings
5. Registry Management
6. Exit
```

When started with a loaded Flock instance:

```
=================================
FLOCK CLI
=================================
Flock loaded with X agents: [agent1, agent2, ...]

1. Execute Flock
2. Start Web Server
3. Start Web Server with UI
4. Manage Agents
5. View Results of Past Runs
6. Edit YAML Configurations
7. Registry Management
8. Settings
9. Exit
```

### Execute Flock
- Allow selection of a start agent
- Input configuration
- Execution options (logging, caching, etc.)
- Execute and view results

### Start Web Server / Start Web Server with UI
- Configure host and port settings
- Set server name
- Launch web server with or without UI components
- Display connection information

### Manage Agents
- List all agents in the system
- Add/remove/edit agents
- View agent details in an elegant visual format
- Export/import agents

### View Results of Past Runs
- Show history of executions
- Filter by agent, date, status
- View detailed outputs
- Export results

### Registry Management
- View Registry Contents
  - Browse by category (Agents, Callables, Types, Components) 
  - Search by name or path
  - View detailed information about items
- Add to Registry
  - Manually add items with full path specification
  - Import from Python modules
- Remove from Registry
  - Select and remove items with confirmation
  - Batch removal with filtering
- Auto-Registration Scanner
  - Scan file/directory for registry decorators
  - Preview potential registrations
  - Execute batch registration
  - Generate registration report
- Export Registry
  - Export current registry state to YAML/JSON

## Acceptance Criteria

1. Users can browse, view, and edit YAML files from the CLI
2. Editor provides syntax highlighting and validation
3. Users receive helpful error messages for invalid configurations
4. Files can be converted between JSON and YAML formats
5. Editor provides auto-completion and template support
6. Changes are validated before saving to prevent corrupted files
7. CLI can be started programmatically with a loaded Flock instance
8. Loaded agents are displayed with summary information
9. Users can execute the loaded Flock system directly from the CLI
10. Agent components are visualized in an elegant, abstracted way
11. Both visual editing and raw YAML editing are supported
12. Users can create a new Flock from scratch using a guided wizard
13. Users can choose between executing the Flock directly or via a web server
14. Users can view all registered items in the Flock Registry by category
15. Users can search and filter registry items by name, type, or path
16. Users can manually add and remove items from the registry
17. An auto-registration scanner can detect and register items from files and directories
18. The registry management system provides clear feedback about registration operations

## Testing

1. Test browsing functionality with various directory structures
2. Verify that syntax highlighting works correctly for all YAML elements
3. Test validation with both valid and invalid configurations
4. Verify that conversion between formats preserves all data
5. Test editor with a range of file sizes and complexities
6. Test programmatic CLI initialization with different Flock configurations
7. Verify that all menu options work correctly with loaded agents
8. Test visualization of agent components for clarity and usability
9. Test Flock creation wizard with various configurations
10. Test web server launch options with and without UI

## Related Tasks

- [US007-T001-YAML-Serializable-Base](done/US007-T001-YAML-Serializable-Base.md) (Completed)
- [US007-T002.1-FlockAgent-YAML-Formatting](done/US007-T002.1-FlockAgent-YAML-Formatting.md) (Completed)
- [US007-T003.2-YAML-Schema-Documentation](done/US007-T003.2-YAML-Schema-Documentation.md) (Completed)
- [US007-T004-Callable-Reference-System](done/US007-T004-Callable-Reference-System.md) (Completed)

## Implementation Details

### Integration with Existing CLI

The implementation should extend the current CLI framework in `src/flock/cli`:

1. **Main Entry Point**:
   - Update `src/flock/__init__.py` to recognize loaded Flock instances
   - Remove the "Start advanced mode" menu item
   - Add logic to display different menu options based on whether a Flock is loaded

2. **New CLI Modules**:
   - Create a `yaml_editor.py` module in `src/flock/cli` for YAML editing functionality
   - Create a `manage_agents.py` module in `src/flock/cli` for managing loaded agents
   - Create a `execute_flock.py` module in `src/flock/cli` for executing loaded Flock instances
   - Create a `view_results.py` module in `src/flock/cli` for viewing execution history
   - Create a `create_flock.py` module in `src/flock/cli` for the Flock creation wizard
   - Create a `registry_management.py` module in `src/flock/cli` for managing the Flock Registry

3. **Web Server Integration**:
   - Update or create a `start_web_server.py` module in `src/flock/cli` that integrates with the loaded Flock
   - Provide options for starting with or without UI components
   - Leverage the existing `start_api()` method in the Flock class

### Visualization of Agent Components

For the elegant visualization of agent components, implement:

1. **Component Diagram**: Visual representation of agent structure including:
   - Input/output fields
   - Tools and modules
   - Evaluator configuration
   - Router connections

2. **Abstract Editor**: A form-based editor that abstracts the YAML structure:
   - Field-by-field editing with validation
   - Component addition/removal through UI controls
   - Connection management for multi-agent systems
   - Preview of changes before saving

3. **Expert Mode**: Toggle between abstract view and raw YAML:
   - Syntax highlighting
   - Schema validation
   - Auto-completion
   - Side-by-side comparison of visual and YAML representations

### Flock Creation Wizard

Implement a guided wizard for creating a new Flock:

1. **Basic Configuration**:
   - Flock name and description
   - Default model selection
   - Logging configuration
   - Execution options (local vs. Temporal)

2. **Initial Agent Creation**:
   - Quick creation of a simple agent with basic input/output
   - Options to add tools and modules
   - Templates for common agent patterns

3. **Save Options**:
   - Save to YAML file
   - Continue editing in the CLI
   - Immediately execute

### Flock Class Integration

Add the following method to the `Flock` class in `src/flock/core/flock.py`:

```python
def start_cli(
    self,
    server_name: str = "Flock CLI",
    show_results: bool = False,
    edit_mode: bool = False,
) -> None:
    """Start a CLI interface for this Flock instance.
    
    This method loads the CLI with the current Flock instance already available,
    allowing users to execute, edit, or manage agents from the existing configuration.
    
    Args:
        server_name: Optional name for the CLI interface
        show_results: Whether to initially show results of previous runs
        edit_mode: Whether to open directly in edit mode
    """
    # Import locally to avoid circular imports
    from flock.cli.loaded_flock_cli import start_loaded_flock_cli
    
    logger.info(
        f"Starting CLI interface with loaded Flock instance ({len(self._agents)} agents)"
    )
    
    # Pass the current Flock instance to the CLI
    start_loaded_flock_cli(
        flock=self,
        server_name=server_name,
        show_results=show_results,
        edit_mode=edit_mode
    )
```

This method follows the same pattern as the existing `start_api()` method.

### Use of Rich and Questionary

The implementation should leverage the existing libraries used in the current CLI:

1. **Rich**: Used for formatting, tables, panels, and other terminal UI elements
2. **Questionary**: Used for interactive prompts, selections, and form inputs

### Registry Management Implementation

Implement registry management with the following components:

1. **Registry Viewer**:
   - Interactive table-based view of registry contents
   - Filtering by category, name pattern, and path
   - Detailed view for individual items showing metadata
   - Color-coding to distinguish different registry categories

2. **Registry Editor**:
   - Form-based interface for adding new items to the registry
   - Path validation and suggestion
   - Dynamic loading of modules for registration
   - Confirmation system for removal operations

3. **Auto-Registration Scanner**:
   - Directory browser for selecting scan targets
   - Progress indicator for scanning operations
   - Preview system showing detected items
   - Confirmation workflow for batch operations
   - Report generation for completed scans

4. **Implementation Interfaces**:
   ```python
   # In registry_management.py
   
   def view_registry_contents(
       category: Optional[str] = None,
       search_pattern: Optional[str] = None
   ) -> None:
       """Display registry contents with filtering options."""
       # Implementation...
   
   def add_to_registry(
       item_type: Literal["agent", "callable", "type", "component"],
       module_path: str,
       item_name: str,
       alias: Optional[str] = None
   ) -> bool:
       """Add an item to the registry manually."""
       # Implementation...
   
   def remove_from_registry(
       item_type: Literal["agent", "callable", "type", "component"],
       item_name_or_path: str
   ) -> bool:
       """Remove an item from the registry."""
       # Implementation...
   
   def scan_for_registry_items(
       target_path: str,
       recursive: bool = True,
       auto_register: bool = False
   ) -> dict[str, list[str]]:
       """Scan directory for potential registry items and optionally register them."""
       # Implementation...
   ```

5. **Registry Storage and Persistence**:
   - Option to save current registry state to a file
   - Load registry state from previous sessions
   - Track registration sources for traceability

## Notes

- Consider leveraging existing CLI libraries for text editing and highlighting
- Ensure the editor is accessible on all supported platforms
- Focus on discoverability and ease-of-use for new users
- Provide keyboard shortcuts and help documentation within the editor
- Use TUI (Text User Interface) libraries like Textual or Rich for creating elegant visualizations in the terminal
- Consider using a state management pattern to handle transitions between different CLI views
- Maintain consistency with the existing CLI style and navigation patterns
