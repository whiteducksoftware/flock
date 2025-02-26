"""
Repository Analyzer with LLM Support

This example demonstrates how to use Flock to create a system that analyzes a repository
and generates a comprehensive knowledge database about it, using LLMs for the analysis.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

from flock.core import Flock, FlockAgent
from flock.core.tools import basic_tools
import litellm

# Define the agents

# Custom tool to get repository structure
def get_repo_files_tool(repo_path: str) -> Dict[str, List[str]]:
    """
    Get a flat list of all files in the repository.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary mapping directory paths to lists of files
    """
    return get_repo_structure(repo_path)

# Custom tool to read file content
def read_file_tool(repo_path: str, file_path: str) -> str:
    """
    Read the content of a file in the repository.
    
    Args:
        repo_path: Path to the repository
        file_path: Path to the file relative to the repository root
        
    Returns:
        Content of the file
    """
    full_path = os.path.join(repo_path, file_path)
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

# 1. Repository Structure Analyzer
# This agent analyzes the repository structure and identifies key files to analyze
repo_structure_analyzer = FlockAgent(
    name="repo_structure_analyzer",
    model="openai/gpt-4o",
    description="""
    You are a repository structure analyzer. Your task is to analyze the structure of a repository
    and identify key files that should be analyzed in detail to understand the codebase.
    
    You will be given a list of files in the repository. You should identify the most important
    files that would help understand the codebase, such as:
    - Main module files (__init__.py)
    - Core implementation files
    - Configuration files
    - Documentation files
    
    Focus on files that are likely to contain important information about the architecture,
    components, and functionality of the codebase.
    """,
    input="repo_path: str | Path to the repository to analyze",
    output="""
        repo_name: str | Name of the repository,
        key_files: list[str] | List of key files to analyze in detail,
        file_structure: dict | Dictionary representing the repository structure,
        readme_content: str | Content of the README file if it exists
    """,
    tools=[get_repo_files_tool, read_file_tool],
)

# 2. File Content Analyzer
# This agent analyzes the content of key files to understand their purpose and functionality
file_content_analyzer = FlockAgent(
    name="file_content_analyzer",
    model="openai/gpt-4o",
    description="""
    You are a file content analyzer. Your task is to analyze the content of key files in a repository
    to understand their purpose and functionality.
    
    For each file, you should:
    1. Identify the purpose of the file
    2. Extract core components (classes, functions, etc.)
    3. Identify key concepts and their relationships
    
    Your analysis should be detailed and focus on understanding the architecture and design of the codebase.
    
    For each core component you identify, provide:
    - Name: The name of the component
    - Description: A brief description of what the component does
    - Detailed Description: A more detailed explanation of the component
    - File Path: The path to the file where the component is defined
    - Features: A list of key features or methods of the component
    
    For each key concept you identify, provide:
    - Name: The name of the concept
    - Description: A brief description of the concept
    - Detailed Description: A more detailed explanation of the concept
    """,
    input="""
        repo_path: str | Path to the repository,
        key_files: list[str] | List of key files to analyze
    """,
    output="""
        file_analyses: dict | Dictionary mapping file paths to their analysis,
        core_components: list[dict] | List of core components identified in the codebase,
        key_concepts: list[dict] | List of key concepts identified in the codebase
    """,
    tools=[read_file_tool],
)

# 3. Documentation Generator
# This agent generates comprehensive documentation based on the repository analysis
documentation_generator = FlockAgent(
    name="documentation_generator",
    model="openai/gpt-4o",
    description="""
    You are a documentation generator. Your task is to generate comprehensive documentation
    for a codebase based on the analysis of its structure and content.
    
    You should create a set of documentation files that provide a complete overview of the codebase,
    including:
    - Overview of the codebase
    - Core components and their relationships
    - Key concepts and features
    - Architecture and design decisions
    - Examples of usage
    
    The documentation should be organized in a way that makes it easy to navigate and understand.
    
    Create the following documentation files:
    1. README.md - Introduction to the documentation
    2. index.md - Table of contents and overview of the documentation
    3. overview.md - High-level overview of the framework
    4. core-components.md - Detailed information about the core components
    5. architecture.md - Information about the architecture and design decisions
    6. features.md - Key features of the framework
    7. examples.md - Example usage patterns
    8. file_lookup.md - Links between key concepts and code files
    9. tasks/task_log.md - Log of all activities performed related to this documentation
    
    The documentation should be comprehensive, well-organized, and easy to navigate.
    """,
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
    tools=[read_file_tool, basic_tools.save_to_file],
)

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

def main():
    """Main function to run the repository analyzer."""
    if len(sys.argv) < 2:
        print("Usage: python repo_analyzer_llm.py <repo_path> [output_path]")
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
