# Environment Profile Switching

## Summary
Implement a feature to create, manage, and switch between multiple environment profiles (dev, test, prod, etc.) in the settings editor.

## Description
This task focuses on adding the ability to create and switch between different environment configurations (.env files) for different contexts (development, testing, production, etc.). The currently active profile will be the main .env file, while other profiles will be stored as separate files with naming convention .env_[profile_name].

## Technical Requirements
- Create a mechanism to detect and list available environment profiles
- Implement functionality to switch between profiles (copying the selected profile to .env)
- Add ability to create new profiles based on existing ones
- Store the profile name as a comment in the first row of each env file
- Ensure profile switching preserves all settings and comments
- Implement backup functionality before switching profiles
- Add UI components for profile management
- Handle confirmation for profile switching to prevent accidental changes

## Implementation Plan
1. Create a function to detect and list available environment profiles
2. Implement profile switching functionality (with proper backups)
3. Add profile creation functionality
4. Add profile deletion/renaming capability
5. Update the settings editor main menu to include profile management
6. Add UI components for profile selection, creation, and management
7. Implement status indicators for the current active profile
8. Add confirmation dialogs for profile switching

## Definition of Done
- Users can view a list of available environment profiles
- Users can switch between profiles with proper confirmation
- Users can create new profiles based on existing ones
- Users can rename or delete existing profiles
- The current active profile is clearly indicated in the UI
- Profile switching is safe and preserves all settings
- Profiles are stored with proper naming conventions (.env, .env_dev, .env_prod, etc.)
- Profile names are stored as comments in the first row of each env file

## Dependencies
- Task 001 (Settings Editor Implementation)
- Task 003 (Environment File Operations)
- Python's os, io, and shutil modules

## Related Tasks
- [001-env-settings-editor.md](001-env-settings-editor.md)
- [003-env-settings-file-operations.md](003-env-settings-file-operations.md)

## Estimated Effort
Medium - Approximately 3-4 hours of development time

## Priority
High - This is an essential feature for workflow efficiency

## Assignee
TBD

## Status
Not Started 