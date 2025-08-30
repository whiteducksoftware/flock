import sys
from pathlib import Path
import pytest

from flock.core.registry import get_registry


pytestmark = pytest.mark.integration


def test_register_module_components_nested(tmp_path: Path):
    pkg = tmp_path / "pkg"
    sub = pkg / "sub"
    pkg.mkdir(); sub.mkdir()
    (pkg / "__init__.py").write_text("")
    (sub / "__init__.py").write_text("")

    (pkg / "a.py").write_text("""
def fa():
    return "A"
""")
    (sub / "b.py").write_text("""
def fb():
    return "B"
""")

    sys.path.insert(0, str(tmp_path))
    try:
        reg = get_registry()
        reg.register_module_components("pkg.a")
        reg.register_module_components("pkg.sub.b")
        assert reg.get_callable("fa")() == "A"
        assert reg.get_callable("fb")() == "B"
    finally:
        sys.path = [p for p in sys.path if p != str(tmp_path)]

