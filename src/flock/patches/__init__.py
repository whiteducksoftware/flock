"""Monkey-patches for third-party libraries to fix known issues."""

from flock.patches.dspy_streaming_patch import apply_patch, restore_original


__all__ = ["apply_patch", "restore_original"]
