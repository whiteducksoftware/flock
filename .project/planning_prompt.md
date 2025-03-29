# Planning Prompt Template

Use this prompt template when you want to create a new user story and related tasks for a feature in the Flock project.

## Prompt Template

```
I need to implement a new feature in my Flock CLI application. The feature is [BRIEF DESCRIPTION OF FEATURE].

Please help me plan this implementation by:

1. Creating a detailed user story that describes:
   - The current state of the system related to this feature
   - The desired state after implementation
   - Technical details about the project structure and relevant files
   - Clear acceptance criteria
   - UI mockups (if applicable)
   - Any edge cases or special considerations

2. Breaking down the implementation into specific tasks, where each task:
   - Has a clear focus and scope
   - Includes technical requirements
   - Has a step-by-step implementation plan
   - Defines "done" criteria
   - Lists dependencies and related tasks
   - Estimates effort required

3. Creating a task index that organizes all tasks with their priorities and statuses

Follow the structure and format used in the Settings Editor feature:
- Create files in `.project/userstories/` for the user story
- Create files in `.project/tasks/` for each task
- Update `.project/USERSTORIES.md` to include the new user story
- Update `.project/TASKS.md` to include the new tasks

Additional context about my project:
[PROVIDE ANY RELEVANT CONTEXT ABOUT YOUR PROJECT, SUCH AS CURRENT STRUCTURE, LIBRARIES USED, OR SPECIFIC REQUIREMENTS]

Before continuing with implementing the code, please let me review the user story and tasks first.
```

## Example Use

Here's an example of how to use this template for a specific feature:

```
I need to implement a new feature in my Flock CLI application. The feature is a command-line plugin system that allows users to create, install, and manage custom plugins to extend the functionality of the CLI.

Please help me plan this implementation by:

1. Creating a detailed user story that describes:
   - The current state of the system related to this feature
   - The desired state after implementation
   - Technical details about the project structure and relevant files
   - Clear acceptance criteria
   - UI mockups (if applicable)
   - Any edge cases or special considerations

2. Breaking down the implementation into specific tasks, where each task:
   - Has a clear focus and scope
   - Includes technical requirements
   - Has a step-by-step implementation plan
   - Defines "done" criteria
   - Lists dependencies and related tasks
   - Estimates effort required

3. Creating a task index that organizes all tasks with their priorities and statuses

Follow the structure and format used in the Settings Editor feature:
- Create files in `.project/userstories/` for the user story
- Create files in `.project/tasks/` for each task
- Update `.project/USERSTORIES.md` to include the new user story
- Update `.project/TASKS.md` to include the new tasks

Additional context about my project:
- The CLI is built in Python using Rich for UI and Questionary for input
- We use a plugin architecture similar to the one in Poetry/Pip
- Plugins should be installable from Git repositories or local directories
- The CLI currently has a modular structure in src/flock/cli/

Before continuing with implementing the code, please let me review the user story and tasks first.
```

## Tips for Getting the Best Results

1. **Be specific** about the feature you want to implement
2. **Provide context** about your project's structure and current state
3. **Mention any libraries or technologies** that should be used
4. **Include any specific requirements** or constraints
5. **Share examples** of similar features if available
6. **Identify potential edge cases** or challenges
7. **Specify the target audience** of the feature
8. **Indicate priority level** if relevant

## Template for User Story Structure

Your user story should typically follow this structure:

```markdown
# User Story: [Feature Name]

## ID
[ID Number]

## Title
[Concise Title]

## Description
As a [type of user], I want to [goal/action] so that [benefit/reason].

## Current State
[Description of how things currently work or the absence of functionality]

## Desired State
[Description of how things should work after implementation]

## Technical Details
[Technical information about implementation, including project structure and technologies]

## Related Tasks
[Links to related task files]

## Acceptance Criteria
[List of specific criteria that must be met for the feature to be considered complete]

## UI Mockups
[Text-based mockups if the feature has a UI component]

## Notes
[Any additional information, cautions, or special considerations]

## Stakeholders
[Who will be affected by or interested in this feature]

## Priority
[Priority level]

## Story Points / Effort
[Estimated effort required]
```

## Template for Task Structure

Your tasks should typically follow this structure:

```markdown
# [Task Name]

## Summary
[Brief description of the task]

## Description
[More detailed explanation of what this task entails]

## User Story
[Link to the related user story]

## Technical Requirements
[Specific technical requirements for this task]

## Implementation Plan
[Step-by-step plan for implementing this task]

## Definition of Done
[Specific criteria that must be met for this task to be considered complete]

## Dependencies
[Libraries, tools, or other tasks that this task depends on]

## Related Tasks
[Links to related task files]

## Estimated Effort
[Estimated time or complexity]

## Priority
[Priority level]

## Assignee
[Who is assigned to this task]

## Status
[Current status of the task]
``` 