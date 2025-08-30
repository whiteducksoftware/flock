import pytest

from flock.core.registry.decorators import flock_component, flock_tool, flock_type


pytestmark = pytest.mark.p0


def test_flock_component_invalid_raises():
    with pytest.raises(TypeError):
        flock_component(123)  # type: ignore[arg-type]


def test_flock_tool_invalid_raises():
    with pytest.raises(TypeError):
        flock_tool(123)  # type: ignore[arg-type]


def test_flock_type_invalid_raises():
    with pytest.raises(TypeError):
        flock_type(123)  # type: ignore[arg-type]

