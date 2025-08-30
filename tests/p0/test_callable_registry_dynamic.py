import importlib
import sys
import types
import pytest

from flock.core.registry import get_registry


pytestmark = pytest.mark.p0


def test_dynamic_import_by_path():
    mod = types.ModuleType("tmp_mod_dyn")

    def f(x):
        return x * 3

    mod.f = f
    sys.modules["tmp_mod_dyn"] = mod

    reg = get_registry()
    out = reg.get_callable("tmp_mod_dyn.f")
    assert out(3) == 9


def test_get_callable_exact_name_registration():
    def z(x):
        return x + 5

    reg = get_registry()
    reg.register_callable(z, name="plus5")
    fn = reg.get_callable("plus5")
    assert fn(7) == 12

