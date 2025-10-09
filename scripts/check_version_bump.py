#!/usr/bin/env python3
"""Check if version should be bumped based on changed files.

This is used as a pre-push hook to warn developers if they're pushing
code changes without bumping versions.

Exit codes:
    0 - No version bump needed or versions already bumped
    1 - Warning: code changed but versions not bumped (non-blocking)
"""

import subprocess
import sys
from pathlib import Path

import toml


def get_changed_files_since_last_tag() -> list[str]:
    """Get files changed since last git tag."""
    try:
        # Get last tag
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True,
        )
        last_tag = result.stdout.strip()

        # Get changed files since last tag
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{last_tag}..HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout.strip().split("\n") if result.stdout.strip() else []

    except subprocess.CalledProcessError:
        # No tags yet or git not available, check all staged files
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip().split("\n") if result.stdout.strip() else []
        except subprocess.CalledProcessError:
            return []


def check_version_changed(file_path: Path, compare_to: str = "HEAD~1") -> bool:
    """Check if version in file changed since a git reference."""
    try:
        # Get old version
        result = subprocess.run(
            ["git", "show", f"{compare_to}:{file_path}"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # File didn't exist before, version is "new"
            return True

        old_content = result.stdout

        # Compare based on file type
        if file_path.name == "pyproject.toml":
            old_pyproject = toml.loads(old_content)
            current_pyproject = toml.load(file_path)

            old_version = old_pyproject.get("project", {}).get("version", "0.0.0")
            current_version = current_pyproject.get("project", {}).get("version", "0.0.0")

            return old_version != current_version

        if file_path.name == "package.json":
            import json

            old_package = json.loads(old_content)
            with open(file_path) as f:
                current_package = json.load(f)

            old_version = old_package.get("version", "0.0.0")
            current_version = current_package.get("version", "0.0.0")

            return old_version != current_version

    except Exception as e:
        print(f"⚠️  Error checking version change: {e}")
        return False

    return False


def main():
    """Main entry point."""
    repo_root = Path(__file__).parent.parent

    # Get changed files
    changed_files = get_changed_files_since_last_tag()

    if not changed_files:
        print("✅ No changes detected")
        return 0

    # Detect what changed
    backend_changed = False
    frontend_changed = False

    backend_paths = ["src/", "tests/", "pyproject.toml"]
    frontend_paths = ["src/flock/frontend/src/", "src/flock/frontend/package.json"]
    excluded_paths = ["docs/", "README.md", "AGENTS.md", ".github/", "LICENSE"]

    for file in changed_files:
        if any(file.startswith(excluded) for excluded in excluded_paths):
            continue

        if any(file.startswith(path) for path in backend_paths):
            backend_changed = True

        if any(file.startswith(path) for path in frontend_paths):
            frontend_changed = True

    if not backend_changed and not frontend_changed:
        print("✅ Only docs/config changed - no version bump needed")
        return 0

    # Check if versions were bumped
    backend_version_bumped = check_version_changed(repo_root / "pyproject.toml")
    frontend_version_bumped = check_version_changed(repo_root / "frontend" / "package.json")

    # Report findings
    warnings = []

    if backend_changed and not backend_version_bumped:
        warnings.append("   ⚠️  Backend code changed but version not bumped in pyproject.toml")

    if frontend_changed and not frontend_version_bumped:
        warnings.append("   ⚠️  Frontend code changed but version not bumped in package.json")

    if warnings:
        print()
        print("⚠️  Version bump recommended:")
        for warning in warnings:
            print(warning)
        print()
        print("💡 To bump versions:")
        print("   poe version-patch   # Patch version (0.1.18 → 0.1.19)")
        print("   poe version-minor   # Minor version (0.1.18 → 0.2.0)")
        print("   poe version-major   # Major version (0.1.18 → 1.0.0)")
        print()
        print("   Or check what would be bumped:")
        print("   poe version-check")
        print()
        print("This is just a reminder - push will continue.")
        print()
        return 1  # Warning, but non-blocking

    print("✅ Versions updated appropriately")
    return 0


if __name__ == "__main__":
    sys.exit(main())
