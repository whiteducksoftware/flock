#!/usr/bin/env python3
"""Ensure `uv` is available.

Used by Poe tasks to provide a friendly message if UV is missing.
This script is intentionally lightweight and has no side effects.
"""

import shutil
import sys


def main() -> int:
    if shutil.which("uv") is None:
        print(
            "⚠️  UV not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh",
            file=sys.stderr,
        )
        # Non-zero to signal missing tool, but let callers decide behavior
        return 1
    print("✅ UV detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
