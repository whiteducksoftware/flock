#!/usr/bin/env python3
"""Update import statements for Phase 8 structure reorganization."""

from pathlib import Path


# Import mapping: old -> new
IMPORT_MAPPINGS = {
    # Core module moves
    "from flock.artifacts import": "from flock.core.artifacts import",
    "from flock.subscription import": "from flock.core.subscription import",
    "from flock.core.visibility import": "from flock.core.visibility import",
    "from flock.context_provider import": "from flock.core.context_provider import",
    "from flock.store import": "from flock.core.store import",
    # Orchestrator module moves
    "from flock.artifact_collector import": "from flock.orchestrator.artifact_collector import",
    "from flock.batch_accumulator import": "from flock.orchestrator.batch_accumulator import",
    "from flock.correlation_engine import": "from flock.orchestrator.correlation_engine import",
    # API module moves
    "from flock.service import": "from flock.api.service import",
    "from flock.api_models import": "from flock.api.models import",
    # Models module
    "from flock.system_artifacts import": "from flock.models.system_artifacts import",
    # Utils consolidation
    "from flock.utilities import": "from flock.utils.utilities import",
    "from flock.runtime import": "from flock.utils.runtime import",
    "from flock.helper.cli_helper import": "from flock.utils.cli_helper import",
}


def update_file_imports(file_path: Path) -> tuple[bool, int]:
    """Update imports in a single file.

    Returns:
        (changed, count) - Whether file was modified and number of changes
    """
    try:
        content = file_path.read_text()
    except Exception as e:
        print(f"⚠️  Error reading {file_path}: {e}")
        return False, 0

    original_content = content
    change_count = 0

    for old_import, new_import in IMPORT_MAPPINGS.items():
        if old_import in content:
            occurrences = content.count(old_import)
            content = content.replace(old_import, new_import)
            change_count += occurrences

    if content != original_content:
        try:
            file_path.write_text(content)
            return True, change_count
        except Exception as e:
            print(f"⚠️  Error writing {file_path}: {e}")
            return False, 0

    return False, 0


def main():
    """Update all Python files in the project."""
    root = Path("src/flock")
    test_root = Path("tests")
    examples_root = Path("examples")

    total_files = 0
    total_changes = 0
    modified_files: list[tuple[Path, int]] = []

    print("🔄 Updating imports across codebase...")
    print()

    # Process all Python files
    for search_root in [root, test_root, examples_root]:
        if not search_root.exists():
            continue

        for py_file in search_root.rglob("*.py"):
            changed, count = update_file_imports(py_file)
            if changed:
                modified_files.append((py_file, count))
                total_changes += count
            total_files += 1

    # Report results
    print()
    print("✅ Import update complete!")
    print("📊 Statistics:")
    print(f"  - Files scanned: {total_files}")
    print(f"  - Files modified: {len(modified_files)}")
    print(f"  - Total import changes: {total_changes}")

    if modified_files:
        print()
        print("📝 Modified files (showing top 20 by change count):")
        # Sort by change count descending
        modified_files.sort(key=lambda x: x[1], reverse=True)
        for file, count in modified_files[:20]:
            print(f"  - {file} ({count} imports)")
        if len(modified_files) > 20:
            print(f"  ... and {len(modified_files) - 20} more files")


if __name__ == "__main__":
    main()
