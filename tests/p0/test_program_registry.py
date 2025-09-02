import pytest

from flock.core.eval.program_base import ProgramRegistry, Program


class _DummyProgram(Program):
    async def run(self, *, inputs: dict[str, object]) -> dict[str, object]:
        return {"ok": True, **inputs}

    async def run_stream(self, *, inputs: dict[str, object]):  # pragma: no cover - unused here
        yield {"event": "final", "result": await self.run(inputs=inputs)}


@pytest.mark.p0
def test_program_registry_register_and_get():
    # ensure clean registry snapshot for this test
    ProgramRegistry._REGISTRY.clear()

    ProgramRegistry.register("dummy", lambda **kw: _DummyProgram(**kw))
    factory = ProgramRegistry.get("dummy")
    prog = factory()
    assert isinstance(prog, _DummyProgram)


@pytest.mark.p0
def test_program_registry_unknown_program_lists_available():
    ProgramRegistry._REGISTRY.clear()
    ProgramRegistry.register("alpha", lambda **kw: _DummyProgram(**kw))

    with pytest.raises(KeyError) as exc:
        ProgramRegistry.get("beta")
    msg = str(exc.value)
    assert "alpha" in msg and "beta" in msg

