import sys
import types
from pathlib import Path

import pytest

from flock.core.registry import get_registry


pytestmark = pytest.mark.integration


def test_module_discovery(tmp_path: Path):
    pkg = tmp_path / "tpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        """
from pydantic import BaseModel
from flock.core.component.agent_component_base import AgentComponent

def hello():
    return "ok"

class TModel(BaseModel):
    x: int

class TinyComponent(AgentComponent):
    name: str
        """
    )

    sys.path.insert(0, str(tmp_path))
    try:
        reg = get_registry()
        reg.register_module_components("tpkg.mod")
        # Callable
        assert callable(reg.get_callable("hello"))
        # Component
        cls = reg.get_component("TinyComponent")
        assert cls.__name__ == "TinyComponent"
    finally:
        sys.path = [p for p in sys.path if p != str(tmp_path)]

