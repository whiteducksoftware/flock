# Settings Editor Implementation

## Summary
Implement a settings editor for the Flock CLI that allows users to view, edit, add, and delete variables in the `.env` file.

## Description
The Flock CLI has a "Settings" menu item that needs to load a settings editor when selected. This editor will allow users to:
1. View all current environment variables in the `.env` file
2. Edit existing environment variable values
3. Add new environment variables
4. Delete existing environment variables
5. Create and switch between different environment profiles (dev, test, prod)

The implementation should provide a smooth and elegant user experience, leveraging the existing libraries used in the project (Rich and Questionary).

## User Story
[US001 - Environment Settings Editor](../../userstories/done/US001-Settings-Editor.md)

## Technical Requirements
- Create a new module in `src/flock/cli/settings.py` that implements the settings editor
- Use Rich for display and formatting of environment variables
- Use Questionary for interactive input and selection
- Handle edge cases such as:
  - Missing `.env` file
  - Invalid format in `.env` file
  - Special characters in variable names or values
  - Multi-line values
- Preserve comments and formatting in the `.env` file when possible
- Provide clear feedback after operations
- Implement confirmation for destructive operations (like deletion)
- Support managing multiple environment profiles

## Implementation Plan
1. Create a function to parse and load the `.env` file
2. Create a function to save the `.env` file
3. Implement a main menu for the settings editor
4. Implement view functionality with pagination
5. Implement edit functionality
6. Implement add functionality
7. Implement delete functionality
8. Implement profile switching and management
9. Connect the settings editor to the CLI main menu

## Definition of Done
- The settings editor can be accessed from the main CLI menu
- Users can view, edit, add, and delete environment variables
- Users can create, switch between, and manage different environment profiles
- The UI is responsive and provides clear feedback
- Edge cases are handled gracefully
- Code is well-documented and follows project conventions
- Changes to the `.env` file are properly preserved

## Dependencies
- Rich library
- Questionary library
- Python's os and dotenv modules

## Related Tasks
- [US001-002-env-settings-ui-components.md](US001-002-env-settings-ui-components.md)
- [US001-003-env-settings-file-operations.md](US001-003-env-settings-file-operations.md)
- [US001-005-env-profile-switching.md](US001-005-env-profile-switching.md)

## Estimated Effort
Medium - Approximately 4-6 hours of development time

## Priority
High - This is a core functionality for the CLI

## Assignee
TBD

## Status
Completed - May 21, 2024

## Implementation Notes
- Created settings_editor() function as the main entry point
- Implemented view_env_variables() with pagination and masking of sensitive values
- Added edit_env_variable(), add_env_variable(), and delete_env_variable() with proper validation
- Implemented profile management (switch_profile, create_profile, rename_profile, delete_profile)
- Added settings for show_secrets and vars_per_page control
- Ensured proper error handling and backups before destructive operations
- Connected the settings editor to the main CLI menu in src/flock/__init__.py 