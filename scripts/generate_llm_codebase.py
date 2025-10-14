#!/usr/bin/env python3
"""
Generate LLM-ready codebase documentation.

Merges source files into a single markdown document with metadata,
perfect for sharing your codebase with LLMs who don't have repo access.
"""

import argparse
import fnmatch
import sys
from datetime import datetime
from pathlib import Path


# Language mapping for syntax highlighting
LANG_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "bash",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}


def get_repo_root() -> Path:
    """Get the repository root directory."""
    # Start from script location and go up to find project root
    current = Path(__file__).parent.parent
    if (current / ".git").exists() or (current / "pyproject.toml").exists():
        return current
    return Path.cwd()


def should_exclude_path(path: Path, exclude_patterns: list[str], tests_mode: str) -> bool:
    """Check if a path should be excluded."""
    path_str = str(path)

    # Always exclude these
    always_exclude = [
        "*.pyc",
        "__pycache__",
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        "dist",
        "build",
        "*.egg-info",
        ".DS_Store",
    ]

    for pattern in always_exclude:
        if fnmatch.fnmatch(path_str, f"*{pattern}*"):
            return True

    # Handle test files based on mode
    is_test = any(
        [
            "/test/" in path_str,
            "/tests/" in path_str,
            path.name.startswith("test_"),
            path.name.endswith("_test.py"),
            path.name.endswith(".test.ts"),
            path.name.endswith(".test.tsx"),
            path.name.endswith(".spec.ts"),
            path.name.endswith(".spec.tsx"),
        ]
    )

    if tests_mode == "exclude" and is_test:
        return True
    if tests_mode == "only" and not is_test:
        return True

    # Check custom exclude patterns
    if any(fnmatch.fnmatch(path_str, f"*{pattern}*") for pattern in exclude_patterns):
        return True

    return False


def get_file_metadata(path: Path, root: Path) -> dict:
    """Get metadata for a file."""
    stat = path.stat()
    relative_path = path.relative_to(root)

    # Count lines
    try:
        with open(path, encoding="utf-8") as f:
            lines = len(f.readlines())
    except Exception:
        lines = 0

    return {
        "path": str(relative_path),
        "size": stat.st_size,
        "lines": lines,
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"


def get_language_marker(path: Path) -> str:
    """Get the markdown language marker for syntax highlighting."""
    return LANG_MAP.get(path.suffix, "")


def collect_files(
    root: Path,
    extensions: list[str],
    exclude_patterns: list[str],
    tests_mode: str,
    max_size_mb: float = None,
) -> list[Path]:
    """Collect all files matching criteria."""
    files = []
    max_size_bytes = max_size_mb * 1024 * 1024 if max_size_mb else None

    # Normalize extensions (ensure they start with .)
    extensions = [f".{ext}" if not ext.startswith(".") else ext for ext in extensions]

    for ext in extensions:
        for path in root.rglob(f"*{ext}"):
            if path.is_file() and not should_exclude_path(path, exclude_patterns, tests_mode):
                # Check file size
                if max_size_bytes and path.stat().st_size > max_size_bytes:
                    print(f"⏭️  Skipping {path.relative_to(root)} (too large)", file=sys.stderr)
                    continue
                files.append(path)

    # Sort by path for consistent ordering
    return sorted(files)


def generate_tree(files: list[Path], root: Path) -> str:
    """Generate a directory tree structure."""
    tree_lines = ["## 📁 Directory Structure\n", "```"]

    # Build tree structure
    dirs: set[Path] = set()
    for file in files:
        current = file.parent
        while current != root:
            dirs.add(current)
            current = current.parent

    # Sort and format
    all_paths = sorted(dirs | set(files))
    for path in all_paths:
        rel_path = path.relative_to(root)
        depth = len(rel_path.parts) - 1
        indent = "  " * depth
        name = path.name
        if path.is_dir():
            tree_lines.append(f"{indent}📂 {name}/")
        else:
            tree_lines.append(f"{indent}📄 {name}")

    tree_lines.append("```\n")
    return "\n".join(tree_lines)


def generate_toc(files: list[Path], root: Path) -> str:
    """Generate table of contents."""
    toc_lines = [
        "## 📑 Table of Contents\n",
        f"**Total Files: {len(files)}**\n",
    ]

    for i, file in enumerate(files, 1):
        rel_path = file.relative_to(root)
        # Create anchor link (GitHub markdown style)
        anchor = str(rel_path).replace("/", "").replace(".", "").replace("_", "-")
        toc_lines.append(f"{i}. [{rel_path}](#{anchor})")

    toc_lines.append("")
    return "\n".join(toc_lines)


def generate_stats(files: list[Path]) -> str:
    """Generate statistics summary."""
    total_size = sum(f.stat().st_size for f in files)
    total_lines = 0

    for file in files:
        try:
            with open(file, encoding="utf-8") as f:
                total_lines += len(f.readlines())
        except:
            pass

    ext_counts = {}
    for file in files:
        ext = file.suffix or "no extension"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    stats_lines = [
        "## 📊 Statistics\n",
        f"- **Total Files:** {len(files)}",
        f"- **Total Size:** {format_size(total_size)}",
        f"- **Total Lines:** {total_lines:,}",
        "\n### Files by Type:",
    ]

    for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True):
        stats_lines.append(f"- {ext}: {count} files")

    stats_lines.append("")
    return "\n".join(stats_lines)


def read_frontmatter() -> str:
    """Read AGENTS.md as frontmatter."""
    root = get_repo_root()
    agents_md = root / "AGENTS.md"

    if agents_md.exists():
        try:
            with open(agents_md, encoding="utf-8") as f:
                content = f.read()
            return f"# 🚀 Flock Framework Documentation\n\n{content}\n\n{'=' * 80}\n\n"
        except Exception as e:
            print(f"⚠️  Warning: Could not read AGENTS.md: {e}", file=sys.stderr)
    else:
        print(f"⚠️  Warning: AGENTS.md not found at {agents_md}", file=sys.stderr)

    return ""


def generate_file_entry(file: Path, root: Path) -> str:
    """Generate markdown entry for a single file."""
    metadata = get_file_metadata(file, root)
    lang = get_language_marker(file)

    # Read file content
    try:
        with open(file, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        content = "[Binary file - content not shown]"
    except Exception as e:
        content = f"[Error reading file: {e}]"

    lines = [
        f"\n## 📄 `{metadata['path']}`\n",
        "```yaml",
        f"path: {metadata['path']}",
        f"size: {format_size(metadata['size'])}",
        f"lines: {metadata['lines']}",
        f"modified: {metadata['modified']}",
        "```\n",
        f"```{lang}",
        content,
        "```\n",
        "-" * 80 + "\n",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate LLM-ready codebase documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage - Python, TypeScript, and Markdown files
  generate_llm_codebase py ts md

  # Include tests
  generate_llm_codebase py ts --add_tests

  # Only tests
  generate_llm_codebase py --only_tests

  # Save to file with tree and stats
  generate_llm_codebase py ts md --output codebase.md --tree --stats

  # Exclude patterns and size limit
  generate_llm_codebase py --exclude "migrations" --exclude "cache" --max-size 0.5
        """,
    )

    parser.add_argument(
        "extensions",
        nargs="+",
        help="File extensions to include (e.g., py ts md)",
    )

    parser.add_argument(
        "--add_tests",
        action="store_true",
        help="Include test files (excluded by default)",
    )

    parser.add_argument(
        "--only_tests",
        action="store_true",
        help="Only include test files",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    )

    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Patterns to exclude (can be used multiple times)",
    )

    parser.add_argument(
        "--max-size",
        type=float,
        help="Maximum file size in MB (larger files will be skipped)",
    )

    parser.add_argument(
        "--tree",
        action="store_true",
        help="Include directory tree structure",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Include statistics summary",
    )

    parser.add_argument(
        "--no-frontmatter",
        action="store_true",
        help="Don't include AGENTS.md as frontmatter",
    )

    args = parser.parse_args()

    # Determine test mode
    if args.only_tests:
        tests_mode = "only"
    elif args.add_tests:
        tests_mode = "include"
    else:
        tests_mode = "exclude"

    # Get repo root
    root = get_repo_root()
    print(f"📦 Scanning repository: {root}", file=sys.stderr)

    # Collect files
    files = collect_files(
        root,
        args.extensions,
        args.exclude,
        tests_mode,
        args.max_size,
    )

    if not files:
        print("❌ No files found matching criteria", file=sys.stderr)
        sys.exit(1)

    print(f"✅ Found {len(files)} files", file=sys.stderr)

    # Generate output
    output_lines = []

    # Add frontmatter
    if not args.no_frontmatter:
        print("📖 Adding AGENTS.md frontmatter...", file=sys.stderr)
        output_lines.append(read_frontmatter())

    # Add tree
    if args.tree:
        print("🌳 Generating directory tree...", file=sys.stderr)
        output_lines.append(generate_tree(files, root))

    # Add table of contents
    print("📑 Generating table of contents...", file=sys.stderr)
    output_lines.append(generate_toc(files, root))

    # Add stats
    if args.stats:
        print("📊 Generating statistics...", file=sys.stderr)
        output_lines.append(generate_stats(files))

    # Add files
    print("📝 Processing files...", file=sys.stderr)
    for i, file in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {file.relative_to(root)}", file=sys.stderr)
        output_lines.append(generate_file_entry(file, root))

    # Output
    output = "".join(output_lines)

    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n🎉 Generated: {output_path}", file=sys.stderr)
        print(f"📏 Size: {format_size(len(output.encode('utf-8')))}", file=sys.stderr)
    else:
        print(output)

    print("✨ Done!", file=sys.stderr)


if __name__ == "__main__":
    main()
