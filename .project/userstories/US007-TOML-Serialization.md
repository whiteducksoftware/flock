# User Story: TOML Serialization for Agents and Flock

## ID
US007

## Title
Add TOML Serialization Support for Agents and Flock Systems

## Description
As a Flock developer, I want to save and load agent definitions and complete Flock systems in TOML format so that I can have a more human-readable configuration format and easily edit agent definitions manually.

## Current State
Currently, Flock and FlockAgent instances can be serialized to and deserialized from JSON files. The JSON serialization works well for programmatic interactions but has several limitations:
1. JSON is not human-friendly for manual editing of complex nested structures
2. JSON doesn't support comments, making it difficult to document configuration
3. The current approach serializes callables as hex strings, making the files nearly impossible to edit manually
4. There's no standard way to create a human-readable representation of the agent system

## Desired State
After implementation, users should be able to:
1. Save FlockAgent instances to TOML files with a clean, readable format
2. Load FlockAgent instances from TOML files
3. Save entire Flock systems (with multiple agents) to TOML files
4. Load entire Flock systems from TOML files
5. Manually edit these TOML files with proper documentation and examples

The TOML format should:
- Support all the same capabilities as the existing JSON serialization
- Provide a more human-friendly representation of agent configurations
- Include comments that document the purpose of each section
- Handle callables in a way that makes them replaceable via configuration

## Technical Details
The implementation will build on the existing serialization framework in `src/flock/core/serialization/`. We'll need to:

1. Add TOML serialization methods to the `Serializable` base class
2. Implement `to_toml` and `from_toml` methods for both `FlockAgent` and `Flock` classes
3. Create a strategy for handling callables in TOML (likely using named references to registered functions)
4. Add support for TOML file detection based on extension
5. Update relevant documentation

**Required Dependencies:**
- `toml` package (already used in the codebase for theme configuration)

## Related Tasks
- Create TOML serialization for FlockAgent
- Create TOML serialization for Flock systems
- Implement callable reference system
- Add tests for TOML serialization
- Update documentation with TOML examples

## Acceptance Criteria
1. A FlockAgent can be saved to a TOML file and loaded back with identical functionality
2. A complete Flock system can be saved to a TOML file and loaded back with identical functionality
3. TOML files are human-readable and include comments explaining structure
4. Serialization properly handles tools, routers, evaluators, and other complex components
5. Unit tests verify the serialization cycle works correctly
6. Documentation is updated with examples

## UI Mockups
Example TOML file format for an agent:

```toml
# FlockAgent: example_agent
# Created: 2023-06-15 14:30:00
# This file defines a Flock agent that summarizes text

name = "example_agent"
model = "openai/gpt-4o"
description = "An agent that summarizes text"
input = "text: str | The text to summarize"
output = "summary: str | The summarized text"
use_cache = true

[evaluator]
name = "default_evaluator"
type = "NaturalLanguageEvaluator"

# Tools available to this agent
[tools]
# List of tool references (from tools registry)
references = ["web_search", "code_eval"]

# Module configurations
[modules.output_module]
enabled = true
render_table = true
wait_for_input = false
```

## Notes
1. We should maintain backward compatibility with the existing JSON serialization
2. The format should be extensible for future enhancements
3. Consider supporting conversion between formats (JSON to TOML and vice versa)
4. Handle the challenge of representing callable objects in a text format

## Stakeholders
- Flock developers
- Flock users who want to manually configure agents
- Flock contributors who need to debug agent configurations

## Priority
Medium

## Story Points / Effort
3 points 