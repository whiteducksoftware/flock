# Codex 02: FEAT - Add Streaming In The UI

### Requirements: 
- flock-showcase in ".showcase/"

### Prompt

please read @AGENTS.md to get an overview of this repository.
It's an agent framework managed with uv (so use uv commands where applicable)

analyze the code in src/flock in-depth until you have an understanding on how this codebase works and do a sanity check by running
"uv run .showcase/00-new-examples/00-sanity.py"
to see it live in action.

Flock's answer is getting streamed per default (stream=True property)
Pleaes make it so, that answer generation in the UI is also streamed and the text "Results will appear here after running the Flock." will get replaced with an actual streaming output.

if this helps: declarative_evaluation_component offers the possibility to register streaming callbacks!


Files of interest could be:
src\flock\components\evaluation\declarative_evaluation_component.py
src\flock\core\agent\default_agent.py
src\flock\webapp

Screenshot:
.codex-demo\image.png
