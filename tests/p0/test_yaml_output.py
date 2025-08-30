import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def test_flock_to_yaml_string(register_fakes):
    a1 = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval")])
    flock = Flock(name="yamltest", show_flock_banner=False)
    flock.add_agent(a1)

    y = flock.to_yaml()
    assert isinstance(y, str)
    assert "yamltest" in y and "agents" in y

