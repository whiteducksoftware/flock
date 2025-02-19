import os
from pathlib import Path

import yaml

# The mkdocs navigation structure
NAV_STRUCTURE = """
nav:
  - Home: index.md
  
  - Getting Started:
    - Quick Start: getting-started/quickstart.md
    - Installation: getting-started/installation.md
    - Basic Concepts: getting-started/concepts.md
    - Configuration: getting-started/configuration.md
    
  - Core Concepts:
    - Agents: core-concepts/agents.md
    - Type System: core-concepts/type-system.md
    - Workflows: core-concepts/workflows.md
    - Declarative Programming: core-concepts/declarative.md
    - Error Handling: core-concepts/error-handling.md
    
  - Features:
    - Agent Definition: features/agent-definition.md
    - Type Safety: features/type-safety.md
    - Pydantic Integration: features/pydantic.md
    - Agent Chaining: features/agent-chaining.md
    - Lifecycle Hooks: features/lifecycle-hooks.md
    
  - Integrations:
    - Temporal: integrations/temporal.md
    - DSPy: integrations/dspy.md
    - LiteLLM: integrations/litellm.md
    - Tavily: integrations/tavily.md
    
  - Advanced Usage:
    - Custom Agents: advanced/custom-agents.md
    - Complex Workflows: advanced/complex-workflows.md
    - Testing: advanced/testing.md
    - Performance Optimization: advanced/performance.md
    
  - Deployment:
    - Production Setup: deployment/production-setup.md
    - Monitoring: deployment/monitoring.md
    - Scalability: deployment/scalability.md
    - Security: deployment/security.md
    
  - Tutorials:
    - Basic Blog Generator: tutorials/blog-generator.md
    - Multi-Agent Systems: tutorials/multi-agent.md
    - Custom Tool Integration: tutorials/custom-tools.md
    - Error Recovery: tutorials/error-recovery.md
    
  - API Reference:
    - FlockAgent: api/flockagent.md
    - Flock Core: api/flock-core.md
    - Types: api/types.md
    - Utilities: api/utilities.md
    
  - Contributing:
    - Development Setup: contributing/development.md
    - Code Style: contributing/code-style.md
    - Testing Guide: contributing/testing.md
    - Documentation Guide: contributing/documentation.md
    
  - Architecture:
    - Overview: architecture/overview.md
    - Components: architecture/components.md
    - Design Decisions: architecture/design-decisions.md
    
  - Examples:
    - Hello Flock: examples/hello-flock.md
    - Type System Usage: examples/type-system.md
    - Pydantic Models: examples/pydantic.md
    - Chain Gang: examples/chain-gang.md
"""


def create_markdown_file(file_path: Path, title: str) -> None:
    """Create a markdown file with a title and placeholder content."""
    content = f"""# {title}

Documentation in progress...
"""
    file_path.write_text(content)


def extract_paths_from_nav(
    nav_dict: dict, paths: list, current_path: str = ""
) -> None:
    """Recursively extract all markdown file paths from the nav structure."""
    for item in nav_dict:
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, str):
                    paths.append(value)
                elif isinstance(value, list):
                    extract_paths_from_nav(value, paths, current_path)


def main():
    # Parse the YAML structure
    nav_data = yaml.safe_load(NAV_STRUCTURE)

    # Extract all markdown file paths
    markdown_paths = []
    extract_paths_from_nav(nav_data["nav"], markdown_paths)

    # Create docs directory if it doesn't exist
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    # Create all necessary directories and markdown files
    for md_path in markdown_paths:
        # Convert path to Path object relative to docs directory
        full_path = docs_dir / md_path

        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate title from the filename
        title = os.path.splitext(full_path.name)[0].replace("-", " ").title()

        # Create the markdown file
        create_markdown_file(full_path, title)
        print(f"Created: {full_path}")


if __name__ == "__main__":
    main()
