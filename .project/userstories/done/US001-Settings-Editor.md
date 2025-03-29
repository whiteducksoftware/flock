# User Story: Environment Settings Editor

## ID
US001

## Title
Implement Environment Settings Editor with Profile Management

## Description
As a user of the Flock CLI application, I want to easily view, edit, add, and delete environment variables in the `.env` file and switch between different environment profiles (dev, test, prod) so that I can efficiently manage my configuration without manual file editing.

## Current State
Currently, the Flock CLI has a "Settings" menu item in the main menu, but it's not implemented yet. The `settings.py` file exists in the `src/flock/cli` directory but only contains a placeholder comment (`# TODO`). 

The main menu is implemented in `src/flock/\__init__.py` and already contains the "Settings" option as a selectable item (defined as `CLI_SETTINGS` in `src/flock/cli/constants.py`).

The application currently uses a single `.env` file for all environment variables. Users who want to switch between different environments (like development, testing, or production) have to manually edit this file or maintain separate copies outside of the application.

## Implemented State
The user can now:
1. Select "Settings" from the main menu to access the settings editor
2. View a list of all environment variables with proper formatting and pagination
3. Edit any existing environment variable with validation
4. Add new environment variables
5. Delete existing environment variables
6. Create new environment profiles (like dev, test, prod)
7. Switch between different profiles easily
8. See which profile is currently active
9. Have sensitive data (like API keys) masked by default with an option to view
10. Configure the number of variables displayed per page

The settings editor has an intuitive interface using Rich for display and Questionary for input. The UI is responsive and provides clear feedback after operations.

## Technical Details

### Project Structure
- Main entry point: `src/flock/__init__.py`
- CLI constants: `src/flock/cli/constants.py`
- Settings module: `src/flock/cli/settings.py`
- Environment variables are stored in `.env` file at the project root
- Template for environment variables: `.env_template`

### Technology Stack
- Python 3.8+
- Rich library for terminal formatting and display
- Questionary library for interactive CLI input
- Python's os, io, and shutil modules for file operations

### File Format
The `.env` file follows the standard format:
```
KEY1=value1
KEY2=value2
# This is a comment
MULTI_LINE="this is a
multi-line value"
```

For profile management, we store the profile name as a comment in the first row:
```
# Profile: dev
KEY1=value1
KEY2=value2
```

### Implementation Details
1. **Environment File Operations**:
   - Parse `.env` files while preserving comments and formatting
   - Implement safe file writing with backups
   - Support profile detection and switching
   - Handle edge cases like missing files or invalid formats

2. **UI Components**:
   - Main settings menu with options for viewing, editing, adding, deleting, and profile management
   - Table view for environment variables with pagination
   - Form inputs for editing/adding variables
   - Confirmation dialogs for destructive actions
   - Profile selection and management UI

3. **Security Features**:
   - Mask sensitive values (API keys, passwords)
   - Add toggle for showing/hiding sensitive data
   - Implement warnings for critical settings

4. **Profile Management**:
   - Store inactive profiles as `.env_[profile_name]` files
   - Make the current profile `.env`
   - Support creating, switching, renaming, and deleting profiles
   - Provide clear indication of the active profile

## Related Tasks
- [US001-001-env-settings-editor.md](../tasks/done/US001-001-env-settings-editor.md): Core settings editor implementation - COMPLETED
- [US001-002-env-settings-ui-components.md](../tasks/done/US001-002-env-settings-ui-components.md): UI design and implementation - COMPLETED
- [US001-003-env-settings-file-operations.md](../tasks/done/US001-003-env-settings-file-operations.md): File operations implementation - COMPLETED
- [US001-004-settings-security-features.md](../tasks/done/US001-004-settings-security-features.md): Security features implementation - COMPLETED
- [US001-005-env-profile-switching.md](../tasks/done/US001-005-env-profile-switching.md): Profile switching implementation - COMPLETED

## Acceptance Criteria
1. ✅ The settings editor is accessible from the main CLI menu
2. ✅ Environment variables can be viewed, edited, added, and deleted
3. ✅ Environment profiles can be created, switched, renamed, and deleted
4. ✅ The active profile is clearly indicated
5. ✅ Sensitive data is masked by default with an option to view
6. ✅ Operations provide clear feedback and confirmation for destructive actions
7. ✅ The UI is responsive and intuitive
8. ✅ File operations preserve comments and formatting when possible
9. ✅ Edge cases (missing files, invalid formats) are handled gracefully

## UI Mockups

### Main Settings Menu
```
┌─ Settings ───────────────────────────────────────┐
│                                                  │
│  Current Profile: dev                            │
│                                                  │
│  What would you like to do?                      │
│                                                  │
│  ❯ View all environment variables                │
│    Edit an environment variable                  │
│    Add a new environment variable                │
│    Delete an environment variable                │
│    Manage environment profiles                   │
│    Back to main menu                             │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Environment Variables View
```
┌─ Environment Variables (Profile: dev) ──────────────────────────────────────┐
│                                                                             │
│  Name                   Value                            Description        │
│  ─────────────────────────────────────────────────────────────────────────  │
│  OPENAI_API_KEY         sk-••••••••••••••••••••••        API Key           │
│  DATA_FOLDER            .data/                           Path              │
│  TELEMETRY              .telemetry/                      Path              │
│  LOCAL_DEBUG            true                             Flag              │
│  LOG_LEVEL              Debug                            Setting           │
│                                                                             │
│  Page 1 of 3                                                                │
│  [n] Next page  [p] Previous page  [e] Edit  [b] Back                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Profile Management
```
┌─ Profile Management ────────────────────────────┐
│                                                 │
│  Current Profile: dev                           │
│                                                 │
│  Available Profiles:                            │
│  ❯ dev (active)                                 │
│    test                                         │
│    prod                                         │
│                                                 │
│  Actions:                                       │
│    Switch to selected profile                   │
│    Create new profile                           │
│    Rename profile                               │
│    Delete profile                               │
│    Back to settings menu                        │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Notes
- Take care to handle sensitive data properly
- Ensure profile switching creates proper backups
- The UI should adapt to different terminal sizes
- Consider adding help/legend for complex operations

## Stakeholders
- Development team members who need to switch between environments
- System administrators managing production configurations
- New team members who need to set up their environment

## Priority
High - This is a core functionality for efficient workflow

## Story Points / Effort
8 points - Medium complexity with multiple components

## Status
Completed 