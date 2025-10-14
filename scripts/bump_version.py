#!/usr/bin/env python3
"""Smart version bumping script for Flock.

Only bumps versions for components that actually changed:
- Backend (src/) → pyproject.toml
- Frontend (src/flock/frontend/) → package.json
- Docs only → no version bump

Usage:
    python scripts/bump_version.py patch          # Bump changed components (patch)
    python scripts/bump_version.py minor          # Bump changed components (minor)
    python scripts/bump_version.py major          # Bump changed components (major)
    python scripts/bump_version.py --check        # Check what would be bumped
    python scripts/bump_version.py patch --force-backend  # Force bump backend
    python scripts/bump_version.py patch --force-frontend # Force bump frontend
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import toml


class VersionBumper:
    """Smart version bumper that detects changed components."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.pyproject_path = repo_root / "pyproject.toml"
        self.package_json_path = repo_root / "src" / "flock" / "frontend" / "package.json"

    def get_changed_files(self, since: str = "HEAD~1") -> list[str]:
        """Get list of changed files since a git reference.

        Args:
            since: Git reference to compare against (default: HEAD~1)

        Returns:
            List of changed file paths
        """
        try:
            # Get staged files
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            staged = result.stdout.strip().split("\n") if result.stdout.strip() else []

            # Get unstaged files
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            unstaged = result.stdout.strip().split("\n") if result.stdout.strip() else []

            # Combine and deduplicate
            changed = list(set(staged + unstaged))
            return [f for f in changed if f]  # Filter empty strings

        except subprocess.CalledProcessError:
            print("⚠️  Not a git repository or git not available")
            return []

    def detect_changes(self, changed_files: list[str]) -> tuple[bool, bool]:
        """Detect which components changed.

        Args:
            changed_files: List of changed file paths

        Returns:
            Tuple of (backend_changed, frontend_changed)
        """
        backend_changed = False
        frontend_changed = False

        backend_paths = ["src/", "tests/", "pyproject.toml", "uv.lock"]
        frontend_paths = ["src/flock/frontend/"]

        # Exclude docs, README, and config files from triggering version bumps
        excluded_paths = [
            "docs/",
            "README.md",
            "AGENTS.md",
            ".github/",
            ".gitignore",
            ".pre-commit-config.yaml",
            "LICENSE",
        ]

        for file in changed_files:
            # Skip excluded paths
            if any(file.startswith(excluded) for excluded in excluded_paths):
                continue

            # Check backend
            if any(file.startswith(path) for path in backend_paths):
                backend_changed = True

            # Check frontend
            if any(file.startswith(path) for path in frontend_paths):
                frontend_changed = True

        return backend_changed, frontend_changed

    def bump_semver(self, version: str, bump_type: str) -> str:
        """Bump a semantic version string.

        Args:
            version: Current version (e.g., "0.1.18")
            bump_type: Type of bump ("major", "minor", "patch")

        Returns:
            New version string
        """
        try:
            parts = version.split(".")
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2].split("-")[0])  # Handle dev versions like "0.2.0-dev"

            if bump_type == "major":
                major += 1
                minor = 0
                patch = 0
            elif bump_type == "minor":
                minor += 1
                patch = 0
            elif bump_type == "patch":
                patch += 1
            else:
                raise ValueError(f"Invalid bump type: {bump_type}")

            return f"{major}.{minor}.{patch}"
        except (ValueError, IndexError) as e:
            print(f"❌ Error parsing version '{version}': {e}")
            sys.exit(1)

    def get_current_versions(self) -> tuple[str, str]:
        """Get current versions from pyproject.toml and package.json.

        Returns:
            Tuple of (backend_version, frontend_version)
        """
        # Read backend version
        pyproject = toml.load(self.pyproject_path)
        backend_version = pyproject["project"]["version"]

        # Read frontend version
        with open(self.package_json_path) as f:
            package = json.load(f)
        frontend_version = package["version"]

        return backend_version, frontend_version

    def update_backend_version(self, new_version: str) -> None:
        """Update version in pyproject.toml.

        Args:
            new_version: New version string
        """
        pyproject = toml.load(self.pyproject_path)
        old_version = pyproject["project"]["version"]
        pyproject["project"]["version"] = new_version

        with open(self.pyproject_path, "w") as f:
            toml.dump(pyproject, f)

        print(f"✅ Backend: {old_version} → {new_version} (pyproject.toml)")

    def update_frontend_version(self, new_version: str) -> None:
        """Update version in package.json.

        Args:
            new_version: New version string
        """
        with open(self.package_json_path) as f:
            package = json.load(f)

        old_version = package["version"]
        package["version"] = new_version

        with open(self.package_json_path, "w") as f:
            json.dump(package, f, indent=2)
            f.write("\n")  # Add trailing newline

        print(f"✅ Frontend: {old_version} → {new_version} (package.json)")

    def bump_versions(
        self,
        bump_type: str,
        force_backend: bool = False,
        force_frontend: bool = False,
        dry_run: bool = False,
    ) -> None:
        """Intelligently bump versions based on what changed.

        Args:
            bump_type: Type of bump ("major", "minor", "patch")
            force_backend: Force bump backend version
            force_frontend: Force bump frontend version
            dry_run: Don't actually change files, just show what would happen
        """
        # Get current versions
        backend_version, frontend_version = self.get_current_versions()

        print("\n📦 Current versions:")
        print(f"   Backend:  {backend_version}")
        print(f"   Frontend: {frontend_version}")
        print()

        # Detect changes
        if force_backend or force_frontend:
            backend_changed = force_backend
            frontend_changed = force_frontend
            print("🔧 Force mode enabled")
        else:
            changed_files = self.get_changed_files()

            if not changed_files:
                print("Info: No changed files detected (checking git diff)")
                print("   To bump versions anyway, use --force-backend or --force-frontend")
                return

            backend_changed, frontend_changed = self.detect_changes(changed_files)

            print("🔍 Detected changes:")
            print(f"   Changed files: {len(changed_files)}")
            print(f"   Backend changed:  {backend_changed}")
            print(f"   Frontend changed: {frontend_changed}")
            print()

        # Calculate new versions
        if backend_changed:
            new_backend_version = self.bump_semver(backend_version, bump_type)
        else:
            new_backend_version = backend_version

        if frontend_changed:
            new_frontend_version = self.bump_semver(frontend_version, bump_type)
        else:
            new_frontend_version = frontend_version

        # Show what will happen
        if not backend_changed and not frontend_changed:
            print("✨ No code changes detected - only docs/config changed")
            print("   No version bump needed!")
            return

        print(f"🚀 Bumping versions ({bump_type}):")
        if backend_changed:
            print(f"   Backend:  {backend_version} → {new_backend_version}")
        else:
            print(f"   Backend:  {backend_version} (unchanged)")

        if frontend_changed:
            print(f"   Frontend: {frontend_version} → {new_frontend_version}")
        else:
            print(f"   Frontend: {frontend_version} (unchanged)")

        print()

        if dry_run:
            print("🔍 Dry run - no files modified")
            return

        # Update versions
        if backend_changed:
            self.update_backend_version(new_backend_version)

        if frontend_changed:
            self.update_frontend_version(new_frontend_version)

        print()
        print("✅ Version bump complete!")
        print()
        print("📝 Next steps:")
        print("   1. Review the changes: git diff")
        print(
            "   2. Stage the version files: git add pyproject.toml src/flock/frontend/package.json"
        )
        print(
            f"   3. Commit: git commit -m 'chore: bump version to {new_backend_version if backend_changed else new_frontend_version}'"
        )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Smart version bumping for Flock",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Bump patch version for changed components
  python scripts/bump_version.py patch

  # Bump minor version for changed components
  python scripts/bump_version.py minor

  # Check what would be bumped without changing files
  python scripts/bump_version.py patch --check

  # Force bump backend only
  python scripts/bump_version.py patch --force-backend

  # Force bump both frontend and backend
  python scripts/bump_version.py minor --force-backend --force-frontend
        """,
    )

    parser.add_argument(
        "bump_type",
        choices=["major", "minor", "patch"],
        help="Type of version bump",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry run - show what would be bumped without changing files",
    )
    parser.add_argument(
        "--force-backend",
        action="store_true",
        help="Force bump backend version even if no backend changes detected",
    )
    parser.add_argument(
        "--force-frontend",
        action="store_true",
        help="Force bump frontend version even if no frontend changes detected",
    )

    args = parser.parse_args()

    # Get repo root (script is in scripts/, repo root is parent)
    repo_root = Path(__file__).parent.parent

    # Create bumper and run
    bumper = VersionBumper(repo_root)
    bumper.bump_versions(
        bump_type=args.bump_type,
        force_backend=args.force_backend,
        force_frontend=args.force_frontend,
        dry_run=args.check,
    )


if __name__ == "__main__":
    main()
