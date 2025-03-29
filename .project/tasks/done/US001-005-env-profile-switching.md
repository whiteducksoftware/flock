# Environment Profile Switching

## Summary
Implement the ability to create, switch between, and manage different environment profiles (.env configurations).

## Description
Users need the ability to manage multiple environment configurations for different contexts (e.g., development, testing, production). This task involves creating functionality to switch between these profiles, create new profiles, and manage existing ones.

## User Story
[US001 - Environment Settings Editor](../../userstories/done/US001-Settings-Editor.md)

## Technical Requirements
- Create a profile management submenu in the settings editor
- Implement functionality to list available profiles
- Add ability to switch between profiles
- Implement profile creation functionality
- Add profile renaming capability
- Implement profile deletion with confirmation
- Create profile duplication functionality
- Ensure the active profile is clearly indicated
- Store profiles in a dedicated directory structure
- Preserve the last active profile between sessions

## Implementation Plan
1. Create a profiles directory structure
2. Implement profile listing functionality
3. Add profile switching capability
4. Create functionality for creating new profiles
5. Implement profile renaming
6. Add profile deletion with safety checks
7. Implement profile duplication
8. Create state tracking for the active profile
9. Integrate profile management into the main settings menu

## Definition of Done
- Users can see a list of available profiles
- Users can switch between different profiles
- Active profile is clearly indicated
- Users can create new profiles from scratch or by duplicating
- Users can rename existing profiles
- Users can delete profiles (with confirmation)
- The system remembers the last active profile
- All profile operations are intuitive and well-documented

## Dependencies
- Core settings editor functionality
- Environment file operations
- Settings security features

## Related Tasks
- [US001-001-env-settings-editor.md](US001-001-env-settings-editor.md)
- [US001-003-env-settings-file-operations.md](US001-003-env-settings-file-operations.md)

## Estimated Effort
Medium - Approximately 3-4 hours of development time

## Priority
High

## Assignee
TBD

## Status
Completed - May 23, 2024

## Implementation Notes
- Created a profiles directory in the user's home directory
- Implemented list_profiles() function to show available profiles
- Added switch_profile() function to change the active profile
- Created create_profile() function for new profiles
- Implemented rename_profile() for changing profile names
- Added delete_profile() with confirmation and backup
- Created duplicate_profile() for creating copies of existing profiles
- Added profile_info.json to track the active profile
- Implemented automatic profile creation for first-time users
- Added profile indicator in the settings menu header
- Created migration functionality for existing .env files 