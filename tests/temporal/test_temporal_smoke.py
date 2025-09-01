import asyncio
import socket

import pytest


pytestmark = pytest.mark.temporal


def _temporal_available(host: str = "localhost", port: int = 7233, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.asyncio
async def test_temporal_simple_run_smoke(register_fakes):
    if not _temporal_available():
        pytest.skip("Temporal server not available on localhost:7233")

    from flock.core.flock import Flock
    from flock.core.flock_agent import FlockAgent
    from tests._helpers.fakes import FakeEvaluator

    agent = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval")])
    flock = Flock(name="temporal-smoke", enable_temporal=True, show_flock_banner=False)
    flock.add_agent(agent)

    out = await flock.run_async(agent="a1", input={"message": "hi"}, box_result=False)
    assert out == {"result": "hi:a1"}


def test_temporal_client_uses_config_address(monkeypatch, register_fakes):
    # Arrange a sentinel address by patching the constant used by temporal executor
    import flock.core.execution.temporal_executor as te

    calls = {}

    async def fake_create_temporal_client(server_address=None):
        # record argument and raise to short-circuit
        calls["server_address"] = server_address
        class _Dummy:  # minimal stub to satisfy type if accessed (not expected)
            pass
        return _Dummy()

    async def fake_setup_worker(client, task_queue, workflow, activities):
        class _W:
            async def run(self):
                return None
            async def shutdown(self):
                return None
        return _W()

    monkeypatch.setattr(te, "TEMPORAL_SERVER_URL", "temporal-test:7233", raising=False)
    monkeypatch.setattr(te, "create_temporal_client", fake_create_temporal_client, raising=True)
    monkeypatch.setattr(te, "setup_worker", fake_setup_worker, raising=True)

    from flock.core.flock import Flock
    from flock.core.flock_agent import FlockAgent
    from tests._helpers.fakes import FakeEvaluator

    agent = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval")])
    flock = Flock(name="temporal-config", enable_temporal=True, show_flock_banner=False)
    flock.add_agent(agent)

    # Act: attempt to run; since client is faked, run should progress until awaiting result
    # To avoid hanging on result, we also monkeypatch the workflow start to raise immediately;
    # but since our fake client lacks methods, code will error before starting. Catch it.
    with pytest.raises(Exception):
        flock.run(agent="a1", input={"message": "x"})

    # Assert the client factory was called with our patched address
    assert calls.get("server_address") == "temporal-test:7233"

