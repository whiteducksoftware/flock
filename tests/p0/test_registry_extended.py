import pytest

from flock.core.registry import get_registry


pytestmark = pytest.mark.p0


def test_type_registry_register_and_get():
    class MyType:
        pass

    reg = get_registry()
    name = reg.register_type(MyType)
    assert name == "MyType"
    assert reg.get_type("MyType") is MyType


def test_config_mapping_roundtrip():
    reg = get_registry()

    class Cfg:  # dummy config class
        pass

    class Comp:  # dummy component class
        pass

    reg.register_config_component_pair(Cfg, Comp)
    assert reg.get_component_class_for_config(Cfg) is Comp


def test_server_registry_register_and_get():
    # Minimal dummy object that satisfies server interface for registry
    class _Cfg:
        def __init__(self, name: str):
            self.name = name

    class _DummyServer:
        def __init__(self, name: str):
            self.config = _Cfg(name)

    reg = get_registry()
    srv = _DummyServer("srv")
    reg.register_server(srv)  # type: ignore[arg-type]
    assert reg.get_server("srv") is srv
    assert "srv" in reg.get_all_server_names()


def test_registry_hub_summary_and_clear():
    reg = get_registry()

    # Ensure there is at least some state
    reg.register_type(dict)
    summary = reg.get_registry_summary()
    assert set(["agents","servers","callables","types","components","config_mappings"]).issubset(summary.keys())

    reg.clear_all()
    cleared = reg.get_registry_summary()
    # At minimum, servers/agents/callables should be reset to 0
    assert cleared["servers"] == 0
    assert cleared["agents"] == 0
    assert cleared["callables"] == 0
