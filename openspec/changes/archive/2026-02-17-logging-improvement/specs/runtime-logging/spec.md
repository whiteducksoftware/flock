## ADDED Requirements

### Requirement: Logger SHALL Handle `exc_info` Without Formatting Side Effects
The logging wrapper MUST normalize stdlib-style `exc_info` usage into backend-native exception binding and MUST NOT forward `exc_info` as message-format kwargs.

#### Scenario: JSON-rich error message with `exc_info=True`
- GIVEN a log message containing JSON braces
- WHEN logger is called with `exc_info=True`
- THEN logging succeeds without format-key errors
- AND exception context is bound to the backend logger

#### Scenario: Explicit exception instance in `exc_info`
- GIVEN an exception object in `exc_info`
- WHEN logger emits an error
- THEN the backend logger receives that exception binding
- AND message text is emitted without kwargs-based format pollution

### Requirement: Orchestrator Error Logging SHALL Preserve Root Cause Visibility
Agent failure logging in the orchestrator MUST preserve original exception details and traceback without introducing secondary logging failures.

#### Scenario: Agent failure message contains JSON braces
- GIVEN an agent error whose text includes JSON payload snippets
- WHEN orchestrator logs the failure
- THEN no secondary formatter exception occurs
- AND the original failure information remains visible in logs
