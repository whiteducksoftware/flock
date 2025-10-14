"""Generate API reference pages automatically from docstrings."""

from pathlib import Path

import mkdocs_gen_files


# Define the source directory
SRC_ROOT = Path("src/flock")

# Define which modules to include in API reference
INCLUDE_MODULES = [
    "orchestrator",
    "agent",
    "artifacts",
    "visibility",
    "components",
    "subscription",
    "runtime",
    "store",
    "registry",
    "service",
]

# Define subdirectories to include (only proper Python packages with __init__.py)
# Note: Starting with core directories, will expand later
INCLUDE_DIRS = [
    "engines",
    "dashboard",
    # "mcp",  # Skip MCP for now due to complex dependencies
]

# Directories to process non-recursively (only top-level files)
INCLUDE_NON_RECURSIVE = [
    "logging",
]

# Navigation structure
nav = mkdocs_gen_files.Nav()

# Process main modules (top-level files)
for module_name in INCLUDE_MODULES:
    module_path = SRC_ROOT / f"{module_name}.py"

    if not module_path.exists():
        continue

    # Create doc path
    doc_path = Path("reference", "api", f"{module_name}.md")

    # Module import path
    full_module = f"flock.{module_name}"

    # Generate markdown content
    with mkdocs_gen_files.open(doc_path, "w") as f:
        print(f"# {module_name.replace('_', ' ').title()}", file=f)
        print(file=f)
        print(f"::: {full_module}", file=f)
        print("    options:", file=f)
        print("      show_source: true", file=f)
        print("      show_root_heading: true", file=f)
        print("      show_root_full_path: false", file=f)
        print("      members_order: source", file=f)
        print("      group_by_category: true", file=f)
        print("      show_category_heading: true", file=f)
        print("      show_if_no_docstring: false", file=f)
        print("      heading_level: 2", file=f)

    # Add to navigation (just the filename, not the full path)
    nav[module_name.replace("_", " ").title()] = f"{module_name}.md"

# Process subdirectories
for dir_name in INCLUDE_DIRS:
    dir_path = SRC_ROOT / dir_name

    if not dir_path.exists():
        continue

    # Create directory index
    dir_doc_path = Path("reference", "api", dir_name, "index.md")

    with mkdocs_gen_files.open(dir_doc_path, "w") as f:
        print(f"# {dir_name.replace('_', ' ').title()}", file=f)
        print(file=f)
        print(f"API reference for `flock.{dir_name}` module.", file=f)
        print(file=f)

    # Process Python files in the directory
    for py_file in sorted(dir_path.rglob("*.py")):
        # Skip __pycache__, __init__.py, and test files
        if (
            "__pycache__" in str(py_file)
            or py_file.name.startswith("test_")
            or py_file.name.startswith("_")
        ):
            continue

        # Get relative path from the directory (not from SRC_ROOT)
        rel_path = py_file.relative_to(dir_path)

        # Create module path (e.g., dspy_engine.py -> engines.dspy_engine)
        module_parts = [dir_name, *rel_path.parts[:-1], rel_path.stem]
        module_path_str = ".".join(module_parts)
        full_module = f"flock.{module_path_str}"

        # Create doc path (e.g., reference/api/engines/dspy_engine.md)
        doc_path = Path("reference", "api", dir_name, *rel_path.parts[:-1], f"{rel_path.stem}.md")

        # Generate markdown content
        with mkdocs_gen_files.open(doc_path, "w") as f:
            module_title = rel_path.stem.replace("_", " ").title()
            print(f"# {module_title}", file=f)
            print(file=f)
            print(f"::: {full_module}", file=f)
            print("    options:", file=f)
            print("      show_source: true", file=f)
            print("      show_root_heading: false", file=f)
            print("      show_root_full_path: false", file=f)
            print("      members_order: source", file=f)
            print("      group_by_category: true", file=f)
            print("      show_category_heading: true", file=f)
            print("      show_if_no_docstring: false", file=f)
            print("      heading_level: 2", file=f)

        # Add to navigation (nested under directory, relative path from api/)
        # Create relative path from reference/api/
        rel_doc_path = Path(dir_name, *rel_path.parts[:-1], f"{rel_path.stem}.md")
        nav_key = f"{dir_name.replace('_', ' ').title()}/{module_title}"
        nav[nav_key] = rel_doc_path.as_posix()

# Process non-recursive directories (only top-level Python files)
for dir_name in INCLUDE_NON_RECURSIVE:
    dir_path = SRC_ROOT / dir_name

    if not dir_path.exists():
        continue

    # Create directory index
    dir_doc_path = Path("reference", "api", dir_name, "index.md")

    with mkdocs_gen_files.open(dir_doc_path, "w") as f:
        print(f"# {dir_name.replace('_', ' ').title()}", file=f)
        print(file=f)
        print(f"API reference for `flock.{dir_name}` module.", file=f)
        print(file=f)

    # Process only top-level Python files (not subdirectories)
    for py_file in sorted(dir_path.glob("*.py")):
        # Skip __init__.py and test files
        if py_file.name.startswith("test_") or py_file.name.startswith("_"):
            continue

        # Module path
        module_name = py_file.stem
        full_module = f"flock.{dir_name}.{module_name}"

        # Create doc path
        doc_path = Path("reference", "api", dir_name, f"{module_name}.md")

        # Generate markdown content
        with mkdocs_gen_files.open(doc_path, "w") as f:
            module_title = module_name.replace("_", " ").title()
            print(f"# {module_title}", file=f)
            print(file=f)
            print(f"::: {full_module}", file=f)
            print("    options:", file=f)
            print("      show_source: true", file=f)
            print("      show_root_heading: false", file=f)
            print("      show_root_full_path: false", file=f)
            print("      members_order: source", file=f)
            print("      group_by_category: true", file=f)
            print("      show_category_heading: true", file=f)
            print("      show_if_no_docstring: false", file=f)
            print("      heading_level: 2", file=f)

        # Add to navigation
        nav_key = f"{dir_name.replace('_', ' ').title()}/{module_title}"
        nav[nav_key] = f"{dir_name}/{module_name}.md"

# Write the navigation file
with mkdocs_gen_files.open("reference/api/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
