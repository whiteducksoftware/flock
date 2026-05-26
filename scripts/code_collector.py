#!/usr/bin/env python3
"""Code Repository Analyzer

This script generates a comprehensive Markdown document of a code repository,
optimized for LLM consumption and understanding.
"""

import ast
import datetime
import glob
import os
from typing import Any


def find_files(folder: str, extension: str) -> list[str]:
    """Find all files with the specified extension in the folder and subfolders."""
    pattern = os.path.join(folder, f"**/*{extension}")
    return sorted(glob.glob(pattern, recursive=True))


def get_file_metadata(file_path: str) -> dict[str, Any]:
    """Extract metadata from a file."""
    metadata = {
        "path": file_path,
        "size_bytes": 0,
        "line_count": 0,
        "last_modified": "Unknown",
        "created": "Unknown",
    }

    try:
        stats = os.stat(file_path)
        metadata["size_bytes"] = stats.st_size
        metadata["last_modified"] = datetime.datetime.fromtimestamp(
            stats.st_mtime
        ).strftime("%Y-%m-%d %H:%M:%S")
        metadata["created"] = datetime.datetime.fromtimestamp(
            stats.st_ctime
        ).strftime("%Y-%m-%d %H:%M:%S")

        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            metadata["line_count"] = len(content.splitlines())
    except Exception as e:
        print(f"Warning: Could not get complete metadata for {file_path}: {e}")

    return metadata


def extract_python_components(file_path: str) -> dict[str, Any]:
    """Extract classes, functions, and imports from Python files."""
    components = {
        "classes": [],
        "functions": [],
        "imports": [],
        "docstring": None,
    }

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        # Extract module docstring
        if ast.get_docstring(tree):
            components["docstring"] = ast.get_docstring(tree)

        # Helper to determine if a function is top-level or a method
        def is_top_level_function(node):
            # Check if the function is defined inside a class
            for parent_node in ast.walk(tree):
                if isinstance(parent_node, ast.ClassDef):
                    for child in parent_node.body:
                        if (
                            child is node
                        ):  # This is a direct reference comparison
                            return False
            return True

        # Extract top-level classes and functions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "methods": [
                        m.name
                        for m in node.body
                        if isinstance(m, ast.FunctionDef)
                    ],
                }
                components["classes"].append(class_info)
            elif isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "args": [
                        arg.arg for arg in node.args.args if hasattr(arg, "arg")
                    ],
                }
                components["functions"].append(func_info)

        # Extract all imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    components["imports"].append(name.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for name in node.names:
                    components["imports"].append(f"{module}.{name.name}")

    except Exception as e:
        print(f"Warning: Could not parse Python components in {file_path}: {e}")

    return components


def analyze_code_dependencies(files: list[str]) -> dict[str, set[str]]:
    """Analyze dependencies between Python files based on imports."""
    dependencies = {file: set() for file in files}

    # Create a mapping from module names to file paths
    module_map = {}
    package_map = {}

    for file_path in files:
        if not file_path.endswith(".py"):
            continue

        # Handle both absolute and relative paths
        abs_path = os.path.abspath(file_path)

        # Map file paths to potential module names
        # First, try to extract package structure
        parts = []
        current = abs_path

        # Build the full module path
        while current:
            parent = os.path.dirname(current)

            # If we've reached the top or left the project directory, stop
            if parent == current or not os.path.exists(
                os.path.join(parent, "__init__.py")
            ):
                break

            parts.insert(0, os.path.basename(current))
            current = parent

        # Use the file name (without .py) as the last part
        base_name = os.path.basename(file_path)
        if base_name.endswith(".py"):
            if base_name != "__init__.py":
                module_name = os.path.splitext(base_name)[0]
                parts.append(module_name)

            full_module_name = ".".join(parts) if parts else None
            if full_module_name:
                module_map[full_module_name] = file_path

            # Also map short names for common imports
            if module_name := os.path.splitext(base_name)[0]:
                # Don't overwrite existing mappings with short names
                if module_name not in module_map:
                    module_map[module_name] = file_path

            # Map package names
            for i in range(len(parts)):
                package_name = ".".join(parts[: i + 1])
                package_map[package_name] = os.path.dirname(file_path)

    # Now analyze imports in each file
    for file_path in files:
        if not file_path.endswith(".py"):
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                code = f.read()

            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Handle direct imports: import x, import x.y
                if isinstance(node, ast.Import):
                    for name in node.names:
                        # Check for the full module path
                        module_path = name.name
                        if module_path in module_map:
                            dependencies[file_path].add(module_map[module_path])

                        # Check for package imports
                        parts = module_path.split(".")
                        for i in range(len(parts), 0, -1):
                            prefix = ".".join(parts[:i])
                            if prefix in module_map:
                                dependencies[file_path].add(module_map[prefix])
                                break

                # Handle from imports: from x import y, from x.y import z
                elif isinstance(node, ast.ImportFrom):
                    if node.module:  # from x import y
                        # See if the module is in our map
                        if node.module in module_map:
                            dependencies[file_path].add(module_map[node.module])

                        # Check for package imports
                        for prefix in get_module_prefixes(node.module):
                            if prefix in module_map:
                                dependencies[file_path].add(module_map[prefix])

                    # Handle relative imports: from . import x, from .. import y
                    if node.level > 0:  # Relative import
                        # Get the directory of the current file
                        dir_path = os.path.dirname(file_path)

                        # Go up levels according to the number of dots
                        for _ in range(node.level - 1):
                            dir_path = os.path.dirname(dir_path)

                        # Try to find matching imports
                        for name in node.names:
                            if node.module:
                                target_module = f"{node.module}.{name.name}"
                            else:
                                target_module = name.name

                            # Check for the module within the relative directory
                            rel_path = os.path.join(
                                dir_path, target_module.replace(".", os.sep)
                            )

                            # Try with .py extension first
                            py_path = f"{rel_path}.py"
                            if os.path.exists(py_path) and py_path in files:
                                dependencies[file_path].add(py_path)

                            # Try as directory with __init__.py
                            init_path = os.path.join(rel_path, "__init__.py")
                            if os.path.exists(init_path) and init_path in files:
                                dependencies[file_path].add(init_path)

        except Exception as e:
            print(f"Warning: Could not analyze imports in {file_path}: {e}")

    return dependencies


def get_module_prefixes(module_name: str) -> list[str]:
    """Generate all possible module prefixes for a given module name.
    For example, 'a.b.c' would return ['a.b.c', 'a.b', 'a']
    """
    parts = module_name.split(".")
    return [".".join(parts[:i]) for i in range(len(parts), 0, -1)]


def generate_folder_tree(folder: str, included_files: list[str]) -> str:
    """Generate an ASCII folder tree representation, only showing directories and files that are included."""
    tree_output = []
    included_paths = set(included_files)

    # Get all directories containing included files
    included_dirs = set()
    for file_path in included_paths:
        dir_path = os.path.dirname(file_path)
        while dir_path and dir_path != folder:
            included_dirs.add(dir_path)
            dir_path = os.path.dirname(dir_path)

    def _generate_tree(dir_path: str, prefix: str = "", is_last: bool = True):
        # Get the directory name
        dir_name = os.path.basename(dir_path) or dir_path

        # Add the current directory to the output
        tree_output.append(
            f"{prefix}{'└── ' if is_last else '├── '}{dir_name}/"
        )

        # Update prefix for children
        new_prefix = f"{prefix}{'    ' if is_last else '│   '}"

        # Get relevant entries in the directory
        try:
            entries = os.listdir(dir_path)
            relevant_dirs = []
            relevant_files = []

            for entry in entries:
                entry_path = os.path.join(dir_path, entry)
                if os.path.isdir(entry_path):
                    # Include directory if it or any of its subdirectories contain included files
                    if (
                        any(
                            f.startswith(entry_path + os.sep)
                            for f in included_paths
                        )
                        or entry_path in included_dirs
                    ):
                        relevant_dirs.append(entry)
                elif entry_path in included_paths:
                    # Only include the specific files we're interested in
                    relevant_files.append(entry)

            # Sort entries for consistent output
            relevant_dirs.sort()
            relevant_files.sort()

            # Process relevant subdirectories
            for i, entry in enumerate(relevant_dirs):
                entry_path = os.path.join(dir_path, entry)
                is_last_dir = i == len(relevant_dirs) - 1
                is_last_item = is_last_dir and len(relevant_files) == 0
                _generate_tree(entry_path, new_prefix, is_last_item)

            # Process relevant files
            for i, entry in enumerate(relevant_files):
                is_last_file = i == len(relevant_files) - 1
                tree_output.append(
                    f"{new_prefix}{'└── ' if is_last_file else '├── '}{entry}"
                )

        except (PermissionError, FileNotFoundError):
            return

    # Start the recursion from the root folder
    _generate_tree(folder)

    return "\n".join(tree_output)


def get_common_patterns(files: list[str]) -> dict[str, list[str]]:
    """Identify common design patterns in the codebase."""
    patterns = {
        "singleton": [],
        "factory": [],
        "observer": [],
        "decorator": [],
        "mvc_components": {"models": [], "views": [], "controllers": []},
    }

    for file_path in files:
        if not file_path.endswith(".py"):
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read().lower()

            # Check for singleton pattern
            if "instance = none" in content and "__new__" in content:
                patterns["singleton"].append(file_path)

            # Check for factory pattern
            if "factory" in os.path.basename(file_path).lower() or (
                "def create" in content and "return" in content
            ):
                patterns["factory"].append(file_path)

            # Check for observer pattern
            if ("observer" in content or "listener" in content) and (
                "notify" in content or "update" in content
            ):
                patterns["observer"].append(file_path)

            # Check for decorator pattern
            if "decorator" in os.path.basename(file_path).lower() or (
                "def wrapper" in content and "return wrapper" in content
            ):
                patterns["decorator"].append(file_path)

            # Check for MVC components
            if "model" in os.path.basename(file_path).lower():
                patterns["mvc_components"]["models"].append(file_path)
            elif "view" in os.path.basename(file_path).lower():
                patterns["mvc_components"]["views"].append(file_path)
            elif (
                "controller" in os.path.basename(file_path).lower()
                or "handler" in os.path.basename(file_path).lower()
            ):
                patterns["mvc_components"]["controllers"].append(file_path)

        except Exception:
            continue

    # Remove empty categories
    for key in list(patterns.keys()):
        if isinstance(patterns[key], list) and not patterns[key]:
            patterns.pop(key)
        elif isinstance(patterns[key], dict):
            empty = True
            for subkey in patterns[key]:
                if patterns[key][subkey]:
                    empty = False
                    break
            if empty:
                patterns.pop(key)

    return patterns


def find_key_files(
    files: list[str], dependencies: dict[str, set[str]]
) -> list[str]:
    """Identify key files based on dependencies and naming conventions."""
    # Initialize scores for each file
    scores = {file: 0 for file in files}

    # Track how many files depend on each file (dependents)
    dependent_count = {file: 0 for file in files}
    for file, deps in dependencies.items():
        for dep in deps:
            if dep in dependent_count:
                dependent_count[dep] += 1

    # Score by number of files that depend on this file
    for file, count in dependent_count.items():
        scores[file] += count * 2

    # Score by file naming heuristics
    for file in files:
        base_name = os.path.basename(file).lower()

        # Core files
        if any(
            core_name in base_name
            for core_name in ["main", "app", "core", "init", "cli"]
        ):
            scores[file] += 5

        # Configuration and settings
        if any(
            config_name in base_name
            for config_name in ["config", "settings", "constants"]
        ):
            scores[file] += 3

        # Base classes and abstract components
        if any(
            base_name in base_name
            for base_name in ["base", "abstract", "interface", "factory"]
        ):
            scores[file] += 2

        # Utilities and helpers
        if any(
            util_name in base_name
            for util_name in ["util", "helper", "common", "tools"]
        ):
            scores[file] += 1

        # Score directories by importance
        dir_path = os.path.dirname(file)
        if "core" in dir_path.lower():
            scores[file] += 2
        if "main" in dir_path.lower():
            scores[file] += 1

        # Score by file size and complexity
        try:
            metadata = get_file_metadata(file)
            line_count = metadata["line_count"]
            scores[file] += min(line_count / 50, 3)  # Cap at 3 points for size

            # Additional points for very significant files
            if line_count > 200:
                scores[file] += 1
        except Exception:
            pass

        # Score by extension - Python files are often more important
        if file.endswith(".py"):
            scores[file] += 1

        # Examples and documentation are important but not as much as core files
        if "example" in file.lower() or "demo" in file.lower():
            scores[file] += 0.5

    # Sort by score in descending order
    key_files = sorted(files, key=lambda f: scores[f], reverse=True)

    # Debugging info
    print(f"Top 5 key files with scores:")
    for file in key_files[:5]:
        print(f"  {file}: {scores[file]:.1f} points")

    # Return top 25% of files or at least 5 files (if available)
    num_key_files = max(min(len(files) // 4, 20), min(5, len(files)))
    return key_files[:num_key_files]


def generate_markdown_string(
    files: list[str],
    extension: str,
    folder: str,
    key_files: list[str],
    dependencies: dict[str, set[str]],
    patterns: dict[str, list[str]],
) -> str:
    """Generate a comprehensive markdown document about the codebase as a string."""
    md_content = []

    # Write header
    md_content.append(f"# Code Repository Analysis\n")
    md_content.append(f"Generated on {datetime.datetime.now()}\n\n")

    # Write repository summary
    md_content.append("## Repository Summary\n\n")
    md_content.append(f"- **Extension analyzed**: `{extension}`\n")
    md_content.append(f"- **Number of files**: {len(files)}\n")
    md_content.append(f"- **Root folder**: `{folder}`\n")

    total_lines = sum(get_file_metadata(f)["line_count"] for f in files)
    md_content.append(f"- **Total lines of code**: {total_lines}\n\n")

    # Generate and write folder tree
    md_content.append("## Project Structure\n\n")
    md_content.append("```\n")
    md_content.append(generate_folder_tree(folder, files))
    md_content.append("\n```\n\n")

    # Write key files section
    md_content.append("## Key Files\n\n")
    md_content.append(
        "These files appear to be central to the codebase based on dependencies and naming conventions:\n\n"
    )

    for file in key_files:
        rel_path = os.path.relpath(file, folder)
        md_content.append(f"### {rel_path}\n\n")

        metadata = get_file_metadata(file)
        md_content.append(f"- **Lines**: {metadata['line_count']}\n")
        md_content.append(f"- **Last modified**: {metadata['last_modified']}\n")

        # Add dependency info
        dependent_files = [
            os.path.relpath(f, folder)
            for f in dependencies
            if file in dependencies[f]
        ]
        if dependent_files:
            md_content.append(f"- **Used by**: {len(dependent_files)} files\n")

        # For Python files, add component analysis
        if file.endswith(".py"):
            components = extract_python_components(file)

            if components["docstring"]:
                md_content.append(
                    f"\n**Description**: {components['docstring'].strip()}\n"
                )

            if components["classes"]:
                md_content.append("\n**Classes**:\n")
                for cls in components["classes"]:
                    md_content.append(
                        f"- `{cls['name']}`: {len(cls['methods'])} methods\n"
                    )

            if components["functions"]:
                md_content.append("\n**Functions**:\n")
                for func in components["functions"]:
                    md_content.append(
                        f"- `{func['name']}({', '.join(func['args'])})`\n"
                    )

        md_content.append("\n**Content**:\n")
        md_content.append(f"```{extension.lstrip('.')}\n")

        # Read and write file content
        try:
            with open(file, encoding="utf-8") as code_file:
                content = code_file.read()
                md_content.append(content)
                if not content.endswith("\n"):
                    md_content.append("\n")
        except Exception as e:
            md_content.append(f"Error reading file: {e!s}\n")

        md_content.append("```\n\n")

    # Write design patterns section if any were detected
    if patterns:
        md_content.append("## Design Patterns\n\n")
        md_content.append(
            "The following design patterns appear to be used in this codebase:\n\n"
        )

        for pattern, files_list in patterns.items():
            if isinstance(files_list, list) and files_list:
                md_content.append(f"### {pattern.title()} Pattern\n\n")
                for f in files_list:
                    md_content.append(f"- `{os.path.relpath(f, folder)}`\n")
                md_content.append("\n")
            elif isinstance(files_list, dict):
                md_content.append(
                    f"### {pattern.replace('_', ' ').title()}\n\n"
                )
                for subpattern, subfiles in files_list.items():
                    if subfiles:
                        md_content.append(f"**{subpattern.title()}**:\n")
                        for f in subfiles:
                            md_content.append(
                                f"- `{os.path.relpath(f, folder)}`\n"
                            )
                        md_content.append("\n")

    # Write all other files section
    md_content.append("## All Files\n\n")

    for file in files:
        if file in key_files:
            continue  # Skip files already detailed in key files section

        rel_path = os.path.relpath(file, folder)
        md_content.append(f"### {rel_path}\n\n")

        metadata = get_file_metadata(file)
        md_content.append(f"- **Lines**: {metadata['line_count']}\n")
        md_content.append(
            f"- **Last modified**: {metadata['last_modified']}\n\n"
        )

        md_content.append("```" + extension.lstrip(".") + "\n")

        # Read and write file content
        try:
            with open(file, encoding="utf-8") as code_file:
                content = code_file.read()
                md_content.append(content)
                if not content.endswith("\n"):
                    md_content.append("\n")
        except Exception as e:
            md_content.append(f"Error reading file: {e!s}\n")

        md_content.append("```\n\n")

    return "".join(md_content)


def collect_code(extension: str = ".py", folder: str = ".") -> str:
    """Main function to analyze code repository and generate markdown string.

    Args:
        extension: File extension to analyze
        folder: Root folder to analyze

    Returns:
        A string containing the markdown analysis
    """
    print(f"Analyzing {extension} files from {folder}...")

    # Find all matching files
    files = find_files(folder, extension)
    print(f"Found {len(files)} files")

    # Get dependencies
    dependencies = analyze_code_dependencies(files)

    # Find key files
    key_files = find_key_files(files, dependencies)

    # Get design patterns
    patterns = get_common_patterns(files)

    # Generate markdown content
    markdown_content = generate_markdown_string(
        files, extension, folder, key_files, dependencies, patterns
    )
    print(f"Repository analysis complete.")

    return markdown_content


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze code repository for LLM consumption"
    )
    parser.add_argument(
        "-c", "--extension", default=".py", help="File extension to analyze"
    )
    parser.add_argument("-f", "--folder", default=".", help="Folder to analyze")
    parser.add_argument(
        "-o",
        "--output",
        default="repository_analysis.md",
        help="Output markdown file",
    )

    args = parser.parse_args()

    # Generate the markdown content
    markdown_content = collect_code(args.extension, args.folder)

    # Write the content to the output file
    with open(args.output, "w", encoding="utf-8") as output_file:
        output_file.write(markdown_content)

    print(f"Output written to '{args.output}'")
