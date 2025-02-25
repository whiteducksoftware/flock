"""
Repository Analyzer

This example demonstrates how to use Flock to create a system that analyzes a repository
and generates a comprehensive knowledge database about it.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from flock.core import Flock, FlockAgent
from flock.core.tools import basic_tools

# Define custom evaluators for the agents

class RepoStructureEvaluator:
    """Custom evaluator for the repository structure analyzer agent."""
    
    async def evaluate(self, agent, inputs, tools):
        """
        Analyze the repository structure and identify key files.
        
        Args:
            agent: The agent instance
            inputs: The input parameters
            tools: The available tools
            
        Returns:
            Dictionary with the repository analysis results
        """
        repo_path = inputs["repo_path"]
        
        # Get the repository name from the path
        repo_name = os.path.basename(os.path.abspath(repo_path))
        
        # Get the repository structure
        file_structure = get_repo_structure(repo_path)
        
        # Check if README.md exists
        readme_path = os.path.join(repo_path, "README.md")
        readme_content = ""
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8", errors="ignore") as f:
                readme_content = f.read()
        
        # Identify key files
        key_files = identify_key_files(file_structure, readme_content)
        
        return {
            "repo_name": repo_name,
            "key_files": key_files,
            "file_structure": file_structure,
            "readme_content": readme_content
        }

# Define the agents

# 1. Repository Structure Analyzer
# This agent analyzes the repository structure and identifies key files
repo_structure_analyzer = FlockAgent(
    name="repo_structure_analyzer",
    input="repo_path: str | Path to the repository to analyze",
    output="""
        repo_name: str | Name of the repository,
        key_files: list[str] | List of key files to analyze in detail,
        file_structure: dict | Dictionary representing the repository structure,
        readme_content: str | Content of the README file if it exists
    """,
    tools=[basic_tools.read_from_file],
)

# Set custom evaluator
repo_structure_analyzer.evaluate = RepoStructureEvaluator().evaluate

class FileContentEvaluator:
    """Custom evaluator for the file content analyzer agent."""
    
    async def evaluate(self, agent, inputs, tools):
        """
        Analyze the content of key files to understand their purpose and functionality.
        
        Args:
            agent: The agent instance
            inputs: The input parameters
            tools: The available tools
            
        Returns:
            Dictionary with the file analysis results
        """
        repo_path = inputs["repo_path"]
        key_files = inputs["key_files"]
        
        file_analyses = {}
        core_components = []
        key_concepts = []
        
        # Analyze each key file
        for file_path in key_files:
            full_path = os.path.join(repo_path, file_path)
            if not os.path.exists(full_path):
                continue
                
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    
                # Basic analysis of the file
                analysis = self._analyze_file(file_path, content)
                file_analyses[file_path] = analysis
                
                # Identify core components
                if analysis["type"] == "class" or analysis["type"] == "module":
                    component = {
                        "name": analysis["name"],
                        "description": analysis["summary"],
                        "detailed_description": analysis["description"],
                        "file_path": file_path,
                        "features": analysis["features"]
                    }
                    core_components.append(component)
                    
                # Identify key concepts
                for concept in analysis["concepts"]:
                    key_concept = {
                        "name": concept["name"],
                        "description": concept["description"],
                        "detailed_description": concept["detailed_description"]
                    }
                    
                    # Check if the concept already exists
                    if not any(c["name"] == key_concept["name"] for c in key_concepts):
                        key_concepts.append(key_concept)
            except Exception as e:
                file_analyses[file_path] = {
                    "error": str(e),
                    "type": "unknown",
                    "name": os.path.basename(file_path),
                    "summary": "Error analyzing file",
                    "description": f"Error analyzing file: {str(e)}",
                    "features": [],
                    "concepts": []
                }
        
        return {
            "file_analyses": file_analyses,
            "core_components": core_components,
            "key_concepts": key_concepts
        }
    
    def _analyze_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Analyze a file to understand its purpose and functionality.
        
        Args:
            file_path: Path to the file
            content: Content of the file
            
        Returns:
            Dictionary with the file analysis results
        """
        # Determine the file type
        file_type = "unknown"
        name = os.path.basename(file_path)
        summary = ""
        description = ""
        features = []
        concepts = []
        
        # Extract the file extension
        _, ext = os.path.splitext(file_path)
        
        if ext == ".py":
            file_type = "python"
            
            # Check if it's a class definition
            if "class " in content:
                file_type = "class"
                
                # Extract class name
                import re
                class_match = re.search(r"class\s+(\w+)", content)
                if class_match:
                    name = class_match.group(1)
                    
                # Extract docstring
                docstring_match = re.search(r'class\s+\w+.*?:\s*?"""(.*?)"""', content, re.DOTALL)
                if docstring_match:
                    docstring = docstring_match.group(1).strip()
                    lines = docstring.split("\n")
                    if lines:
                        summary = lines[0].strip()
                        description = "\n".join(lines[1:]).strip()
                        
                # Extract methods as features
                method_matches = re.finditer(r"def\s+(\w+)\s*\(", content)
                for match in method_matches:
                    method_name = match.group(1)
                    if not method_name.startswith("_") or method_name.startswith("__"):
                        features.append(method_name)
                        
            # Check if it's a module
            elif "__init__.py" in file_path:
                file_type = "module"
                
                # Extract module name
                name = os.path.basename(os.path.dirname(file_path))
                
                # Extract docstring
                docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                if docstring_match:
                    docstring = docstring_match.group(1).strip()
                    lines = docstring.split("\n")
                    if lines:
                        summary = lines[0].strip()
                        description = "\n".join(lines[1:]).strip()
                        
                # Extract functions and classes as features
                function_matches = re.finditer(r"def\s+(\w+)\s*\(", content)
                for match in function_matches:
                    function_name = match.group(1)
                    if not function_name.startswith("_"):
                        features.append(function_name)
                        
                class_matches = re.finditer(r"class\s+(\w+)", content)
                for match in class_matches:
                    class_name = match.group(1)
                    features.append(class_name)
        
        elif ext == ".md":
            file_type = "markdown"
            
            # Extract title
            import re
            title_match = re.search(r"#\s+(.*)", content)
            if title_match:
                name = title_match.group(1).strip()
                
            # Extract summary
            lines = content.split("\n")
            for line in lines:
                if line.strip() and not line.startswith("#"):
                    summary = line.strip()
                    break
                    
            # Extract description
            description = content
            
            # Extract concepts
            concept_matches = re.finditer(r"##\s+(.*)", content)
            for match in concept_matches:
                concept_name = match.group(1).strip()
                concept_start = match.end()
                
                # Find the end of the concept
                concept_end = len(content)
                next_match = re.search(r"##\s+", content[concept_start:])
                if next_match:
                    concept_end = concept_start + next_match.start()
                    
                concept_content = content[concept_start:concept_end].strip()
                
                # Extract the first paragraph as the description
                concept_description = ""
                concept_lines = concept_content.split("\n")
                for line in concept_lines:
                    if line.strip():
                        concept_description = line.strip()
                        break
                        
                concepts.append({
                    "name": concept_name,
                    "description": concept_description,
                    "detailed_description": concept_content
                })
        
        # If we couldn't extract a summary, use the first non-empty line
        if not summary:
            lines = content.split("\n")
            for line in lines:
                if line.strip():
                    summary = line.strip()
                    break
        
        # If we couldn't extract a description, use the first few lines
        if not description:
            lines = content.split("\n")
            description = "\n".join(lines[:10])
        
        # If we couldn't extract any features, use the file name
        if not features:
            features.append(name)
        
        # If we couldn't extract any concepts, create a default one
        if not concepts:
            concepts.append({
                "name": name,
                "description": summary,
                "detailed_description": description
            })
        
        return {
            "type": file_type,
            "name": name,
            "summary": summary,
            "description": description,
            "features": features,
            "concepts": concepts
        }

# 2. File Content Analyzer
# This agent analyzes the content of key files to understand their purpose and functionality
file_content_analyzer = FlockAgent(
    name="file_content_analyzer",
    input="""
        repo_path: str | Path to the repository,
        key_files: list[str] | List of key files to analyze
    """,
    output="""
        file_analyses: dict | Dictionary mapping file paths to their analysis,
        core_components: list[dict] | List of core components identified in the codebase,
        key_concepts: list[dict] | List of key concepts identified in the codebase
    """,
    tools=[basic_tools.read_from_file],
)

# Set custom evaluator
file_content_analyzer.evaluate = FileContentEvaluator().evaluate

class DocumentationGeneratorEvaluator:
    """Custom evaluator for the documentation generator agent."""
    
    async def evaluate(self, agent, inputs, tools):
        """
        Generate comprehensive documentation based on the repository analysis.
        
        Args:
            agent: The agent instance
            inputs: The input parameters
            tools: The available tools
            
        Returns:
            Dictionary with the documentation files
        """
        repo_path = inputs["repo_path"]
        repo_name = inputs["repo_name"]
        file_structure = inputs["file_structure"]
        readme_content = inputs["readme_content"]
        file_analyses = inputs["file_analyses"]
        core_components = inputs["core_components"]
        key_concepts = inputs["key_concepts"]
        
        # Create the documentation structure
        documentation_files = create_documentation_structure(repo_name, core_components, key_concepts)
        
        return {
            "documentation_files": documentation_files
        }

# 3. Documentation Generator
# This agent generates comprehensive documentation based on the repository analysis
documentation_generator = FlockAgent(
    name="documentation_generator",
    input="""
        repo_path: str | Path to the repository,
        repo_name: str | Name of the repository,
        file_structure: dict | Dictionary representing the repository structure,
        readme_content: str | Content of the README file if it exists,
        file_analyses: dict | Dictionary mapping file paths to their analysis,
        core_components: list[dict] | List of core components identified in the codebase,
        key_concepts: list[dict] | List of key concepts identified in the codebase
    """,
    output="""
        documentation_files: dict | Dictionary mapping file paths to their content
    """,
    tools=[basic_tools.save_to_file],
)

# Set custom evaluator
documentation_generator.evaluate = DocumentationGeneratorEvaluator().evaluate

# Set up the agent chain
repo_structure_analyzer.hand_off = file_content_analyzer
file_content_analyzer.hand_off = documentation_generator

# Alternative way to set up the agent chain (as shown in examples/02_cook_book/long_research_no_handoff.py)
# This would be used if we wanted to do custom processing between agent runs
# For example:
"""
# Instead of using hand_off, we could do:
result = flock.run(
    start_agent=repo_structure_analyzer,
    input={"repo_path": repo_path}
)

# Then process the result and run the next agent
file_analysis_result = flock.run(
    start_agent=file_content_analyzer,
    input={
        "repo_path": repo_path,
        "key_files": result["key_files"]
    }
)

# Then process the result and run the next agent
documentation_result = flock.run(
    start_agent=documentation_generator,
    input={
        "repo_path": repo_path,
        "repo_name": result["repo_name"],
        "file_structure": result["file_structure"],
        "readme_content": result["readme_content"],
        "file_analyses": file_analysis_result["file_analyses"],
        "core_components": file_analysis_result["core_components"],
        "key_concepts": file_analysis_result["key_concepts"]
    }
)
"""

# Helper functions for the agents

def get_repo_structure(repo_path: str) -> Dict[str, Any]:
    """
    Recursively get the structure of a repository.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary representing the repository structure
    """
    result = {}
    
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories and files
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]
        
        # Skip virtual environments
        if 'venv' in dirs:
            dirs.remove('venv')
        if 'env' in dirs:
            dirs.remove('env')
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
            
        # Get the relative path
        rel_path = os.path.relpath(root, repo_path)
        if rel_path == '.':
            rel_path = ''
            
        # Add files to the result
        if files:
            result[rel_path] = files
            
    return result

def identify_key_files(repo_structure: Dict[str, Any], readme_content: str = "") -> List[str]:
    """
    Identify key files in the repository based on the structure and README content.
    
    Args:
        repo_structure: Dictionary representing the repository structure
        readme_content: Content of the README file if it exists
        
    Returns:
        List of key files to analyze in detail
    """
    key_files = []
    
    # Look for common important files
    for path, files in repo_structure.items():
        for file in files:
            file_path = os.path.join(path, file) if path else file
            
            # Main module files
            if file == '__init__.py':
                key_files.append(file_path)
                
            # Main implementation files
            if file.endswith('.py') and not file.startswith('test_'):
                key_files.append(file_path)
                
            # Configuration files
            if file in ['setup.py', 'pyproject.toml', 'requirements.txt']:
                key_files.append(file_path)
                
            # Documentation files
            if file.endswith('.md') and file != 'README.md':
                key_files.append(file_path)
    
    # Limit to a reasonable number of files
    return key_files[:20]  # Limit to 20 key files

def create_documentation_structure(repo_name: str, core_components: List[Dict], key_concepts: List[Dict]) -> Dict[str, str]:
    """
    Create a documentation structure based on the repository analysis.
    
    Args:
        repo_name: Name of the repository
        core_components: List of core components identified in the codebase
        key_concepts: List of key concepts identified in the codebase
        
    Returns:
        Dictionary mapping file paths to their content
    """
    docs = {}
    
    # Create README.md
    docs["README.md"] = f"""# {repo_name} Documentation

This folder contains comprehensive documentation about the {repo_name} framework.

## Purpose

This documentation serves as a knowledge base for understanding the {repo_name} framework, its architecture, components, features, and usage patterns. It is designed to provide a complete overview that can be quickly consumed to gain a deep understanding of the framework.

This is a living document that should be continuously updated. Whenever new information about the framework is discovered that is not yet included in this documentation, it should be added to the appropriate files. This ensures that the documentation remains comprehensive and up-to-date.

The `tasks` subfolder contains a log of all activities performed related to this documentation, which helps track what has been done and what still needs to be done.

## Contents

- [index.md](index.md) - Table of contents and overview of the documentation
- [overview.md](overview.md) - High-level overview of the framework
- [core-components.md](core-components.md) - Detailed information about the core components
- [architecture.md](architecture.md) - Information about the architecture and design decisions
- [features.md](features.md) - Key features
- [examples.md](examples.md) - Example usage patterns
- [file_lookup.md](file_lookup.md) - Links between key concepts and code files
- [tasks/](tasks/) - Log of all activities performed related to this documentation

## How to Use This Documentation

Start with the [index.md](index.md) file, which provides a table of contents and overview of the documentation. From there, you can navigate to specific topics of interest.

For a quick understanding, read the [overview.md](overview.md) file, which provides a high-level overview of the framework.

For more detailed information about specific aspects, refer to the corresponding documentation files.
"""
    
    # Create index.md
    docs["index.md"] = f"""# {repo_name} Framework Documentation

This documentation provides a comprehensive overview of the {repo_name} framework.

## Table of Contents

1. [Overview](overview.md)
   - Key Concepts
   - Core Components
   - Architecture

2. [Core Components](core-components.md)
   {os.linesep.join([f"   - {component['name']}" for component in core_components])}

3. [Architecture](architecture.md)
   - High-Level Architecture
   - Component Relationships
   - Design Decisions

4. [Features](features.md)
   {os.linesep.join([f"   - {concept['name']}" for concept in key_concepts])}

5. [Examples](examples.md)
   - Basic Example
   - Advanced Examples

6. [File Lookup](file_lookup.md)
   - Core Components
   - Key Files
   - Examples
"""
    
    # Create overview.md
    docs["overview.md"] = f"""# {repo_name} Framework Overview

This document provides a high-level overview of the {repo_name} framework.

## Key Concepts

{os.linesep.join([f"- **{concept['name']}**: {concept['description']}" for concept in key_concepts])}

## Core Components

{os.linesep.join([f"- **{component['name']}**: {component['description']}" for component in core_components])}

## Architecture

The {repo_name} framework is designed with a modular architecture that separates concerns and allows for flexibility and extensibility.
"""
    
    # Create core-components.md
    docs["core-components.md"] = f"""# {repo_name} Core Components

This document provides detailed information about the core components of the {repo_name} framework.

{os.linesep.join([f"## {component['name']}{os.linesep}{os.linesep}{component['detailed_description']}{os.linesep}" for component in core_components])}
"""
    
    # Create file_lookup.md
    docs["file_lookup.md"] = f"""# {repo_name} Framework Code File Lookup

This document provides links between key concepts in the {repo_name} framework and the corresponding code files where they are implemented.

## Core Components

{os.linesep.join([f"### {component['name']}{os.linesep}{os.linesep}- **Implementation**: {component['file_path']}{os.linesep}- **Key Features**:{os.linesep}{os.linesep.join(['  - ' + feature for feature in component['features']])}{os.linesep}" for component in core_components])}
"""
    
    # Create tasks folder and task_log.md
    docs["tasks/task_log.md"] = f"""# Task Log

This file logs all tasks performed related to the {repo_name} framework documentation.

## Initial Documentation Creation

1. Created the documentation folder as a knowledge base for {repo_name} framework information.
2. Analyzed the {repo_name} framework by examining key source files.
3. Created comprehensive documentation files:
   - overview.md - High-level overview of the framework
   - core-components.md - Detailed information about the core components
   - architecture.md - Information about the architecture and design decisions
   - features.md - Key features
   - examples.md - Example usage patterns
   - file_lookup.md - Links between key concepts and code files
   - index.md - Table of contents and overview of the documentation
   - README.md - Introduction to the documentation
4. Created a tasks subfolder to protocol all activities.

### Future Tasks

1. Continue to update documentation as new information is discovered.
2. Add more detailed information about specific components as needed.
3. Keep the file_lookup.md updated with new files and components.
4. Add more examples and use cases as they are discovered.
"""
    
    # Create empty files for other documentation
    docs["architecture.md"] = f"""# {repo_name} Architecture

This document provides an overview of the {repo_name} framework's architecture and design decisions.

## High-Level Architecture

The {repo_name} framework is designed with a modular architecture that separates concerns and allows for flexibility and extensibility.

## Component Relationships

The main components of the {repo_name} framework and their relationships.

## Design Decisions

Key design decisions that shaped the {repo_name} framework.
"""
    
    docs["features.md"] = f"""# {repo_name} Key Features

This document outlines the key features of the {repo_name} framework.

{os.linesep.join([f"## {concept['name']}{os.linesep}{os.linesep}{concept['detailed_description']}{os.linesep}" for concept in key_concepts])}
"""
    
    docs["examples.md"] = f"""# {repo_name} Examples

This document provides examples of how to use the {repo_name} framework for various use cases.

## Basic Example

A simple example of using the {repo_name} framework.

## Advanced Examples

More complex examples of using the {repo_name} framework.
"""
    
    return docs

def main():
    """Main function to run the repository analyzer."""
    if len(sys.argv) < 2:
        print("Usage: python repo_analyzer.py <repo_path> [output_path]")
        sys.exit(1)
        
    repo_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(repo_path, "docs", "generated")
    
    # Create the Flock instance
    flock = Flock(model="openai/gpt-4o")
    
    # Add the agents to the flock
    flock.add_agent(repo_structure_analyzer)
    flock.add_agent(file_content_analyzer)
    flock.add_agent(documentation_generator)
    
    # Run the flock
    result = flock.run(
        start_agent=repo_structure_analyzer,
        input={"repo_path": repo_path}
    )
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)
    os.makedirs(os.path.join(output_path, "tasks"), exist_ok=True)
    
    # Save the documentation files
    for file_path, content in result["documentation_files"].items():
        full_path = os.path.join(output_path, file_path)
        
        # Create directories if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write the file
        with open(full_path, "w") as f:
            f.write(content)
            
    print(f"Documentation generated successfully in {output_path}")

if __name__ == "__main__":
    main()
