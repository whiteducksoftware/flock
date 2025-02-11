
import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent

# This is the model that will be used for the tests
MODEL = "ollama_chat/qwen"

@pytest.fixture
def flock():
    return Flock(local_debug=True)


@pytest.fixture
def temporal_flock():
    return Flock()

class TestAgentIntegration:
    @pytest.mark.asyncio
    async def test_small_agent_integration(self, flock: Flock):
        bloggy = FlockAgent(
            name="bloggy", 
            input="blog_idea", 
            output="funny_blog_title, blog_headers"
        )
        flock.add_agent(bloggy)
        result = await flock.run_async(
            start_agent=bloggy, 
            input={"blog_idea": "A blog about cats"}
        )
        assert result.funny_blog_title not in [None, ""]
        assert result.blog_headers not in [None, []]


    @pytest.mark.asyncio
    async def test_temporal_small_agent_integration(self, temporal_flock: Flock):
        bloggy = FlockAgent(
            name="bloggy", 
            input="blog_idea", 
            output="funny_blog_title, blog_headers"
        )
        temporal_flock.add_agent(bloggy)
        result = await temporal_flock.run_async(
            start_agent=bloggy, 
            input={"blog_idea": "A blog about cats"}
        )
        assert result.funny_blog_title not in [None, ""]
        assert result.blog_headers not in [None, []]