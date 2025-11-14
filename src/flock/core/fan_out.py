"""Core types for fan-out configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class FanOutRange:
    """Represents a fan-out range (min/max) for published outputs."""

    min: int
    max: int

    def __post_init__(self) -> None:
        if self.min < 1:
            raise ValueError(f"fan_out min must be >= 1, got {self.min}")
        if self.max < self.min:
            raise ValueError(f"fan_out max ({self.max}) must be >= min ({self.min})")

    def is_fixed(self) -> bool:
        """Return True if this range represents a fixed count."""
        return self.min == self.max

    def fixed_count(self) -> int | None:
        """Return fixed count if this is a fixed range, otherwise None."""
        return self.min if self.is_fixed() else None

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        if self.is_fixed():
            return f"FanOutRange({self.min})"
        return f"FanOutRange(min={self.min}, max={self.max})"


FanOutSpec = Union[int, tuple[int, int], FanOutRange]


def normalize_fan_out(spec: FanOutSpec | None) -> FanOutRange | None:
    """Normalize a fan_out specification to FanOutRange.

    Args:
        spec: int, (min, max) tuple, FanOutRange, or None

    Returns:
        FanOutRange instance or None.
    """
    if spec is None:
        return None

    if isinstance(spec, int):
        # Backwards compatibility: fan_out=1 behaves like the default (no fan-out).
        # Explicit ranges (via tuple or FanOutRange) are required to trigger list semantics.
        if spec < 1:
            raise ValueError(f"fan_out must be >= 1, got {spec}")
        if spec == 1:
            return None
        return FanOutRange(min=spec, max=spec)

    if isinstance(spec, tuple):
        if len(spec) != 2:
            raise ValueError(
                f"fan_out tuple must be (min, max), got length {len(spec)}"
            )
        min_val, max_val = spec
        return FanOutRange(min=min_val, max=max_val)

    if isinstance(spec, FanOutRange):
        return spec

    raise TypeError(
        f"fan_out must be int, tuple[int, int], or FanOutRange, got {type(spec)}"
    )


__all__ = ["FanOutRange", "FanOutSpec", "normalize_fan_out"]
