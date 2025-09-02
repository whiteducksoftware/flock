"""Native evaluator scaffolding (LiteLLM-backed) — experimental.

This package hosts a minimal, modular execution layer designed to replace the
DSPy dependency over time. It intentionally mirrors Flock's component ethos:

- LMClient: provider-agnostic wrapper (LiteLLM-backed) for generation/streaming
- PromptBuilder: builds instruction + JSON schema from Flock contracts
- ToolAdapter: uniform interface for native + MCP tools
- Program interface/registry: pluggable reasoning/planning algorithms

Note: These are initial skeletons and are not yet wired as the default path.
"""

from .program_base import Program, ProgramRegistry

__all__ = [
    "Program",
    "ProgramRegistry",
]

