import pytest

from flock.core.flock import Flock


pytestmark = pytest.mark.p0


def test_flock_run_simple(simple_agent):
    flock = Flock(name="t", show_flock_banner=False)
    flock.add_agent(simple_agent)
    out = flock.run(agent="agent1", input={"message": "hi"})
    assert out == {"result": "hi:agent1"}


@pytest.mark.asyncio
async def test_flock_run_async(simple_agent):
    flock = Flock(name="t2", show_flock_banner=False)
    flock.add_agent(simple_agent)
    out = await flock.run_async(input={"message": "yo"}, agent="agent1")
    assert out == {"result": "yo:agent1"}
