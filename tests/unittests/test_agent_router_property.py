"""Unit tests for the handoff router property."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent, HandOffRequest
from flock.core.registry.agent_registry import Registry
from flock.routers.agent.agent_router import AgentRouter, AgentRouterConfig
from flock.core.flock_router import FlockRouter
from flock.routers.llm.llm_router import LLMRouter, LLMRouterConfig


class TestHandoffRouterProperty(unittest.TestCase):
    """Test cases for the handoff router property."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock registry
        self.registry = MagicMock(spec=Registry)
        
        # Create agents
        self.agent1 = FlockAgent(
            name="agent1",
            model="openai/gpt-4o",
            description="Agent 1 description",
            input="input1: str | Input 1 description",
            output="output1: str | Output 1 description",
        )
        
        self.agent2 = FlockAgent(
            name="agent2",
            model="openai/gpt-4o",
            description="Agent 2 description",
            input="input2: str | Input 2 description, output1: str | Output from agent 1",
            output="output2: str | Output 2 description",
        )
        
        # Set up the mock registry
        self.registry._agents = [self.agent1, self.agent2]
        self.registry.get_agent.side_effect = lambda name: next((a for a in self.registry._agents if a.name == name), None)
        
        # Create context
        self.context = FlockContext()

    def test_agent_router_property(self):
        """Test that the agent router property is set correctly."""
        # Create a router
        router = AgentRouter(
            registry=self.registry,
            config=AgentRouterConfig(confidence_threshold=0.6),
        )
        
        # Set the router on the agent
        self.agent1.handoff_router = router
        
        # Check that the router is set correctly
        self.assertEqual(self.agent1.handoff_router, router)
        self.assertIsInstance(self.agent1.handoff_router, FlockRouter)
        self.assertIsInstance(self.agent1.handoff_router, AgentRouter)
        self.assertEqual(self.agent1.handoff_router.config.confidence_threshold, 0.6)

    def test_llm_router_property(self):
        """Test that the LLM router property is set correctly."""
        # Create a router
        router = LLMRouter(
            registry=self.registry,
            config=LLMRouterConfig(
                temperature=0.1,
                confidence_threshold=0.7,
            ),
        )
        
        # Set the router on the agent
        self.agent1.handoff_router = router
        
        # Check that the router is set correctly
        self.assertEqual(self.agent1.handoff_router, router)
        self.assertIsInstance(self.agent1.handoff_router, FlockRouter)
        self.assertIsInstance(self.agent1.handoff_router, LLMRouter)
        self.assertEqual(self.agent1.handoff_router.config.temperature, 0.1)
        self.assertEqual(self.agent1.handoff_router.config.confidence_threshold, 0.7)

    @patch("flock.workflow.activities.run_agent")
    async def test_agent_with_router_in_workflow(self, mock_run_agent):
        """Test that the agent's router is used in the workflow."""
        # Import the run_agent function
        from flock.workflow.activities import run_agent
        
        # Create a router
        router = MagicMock(spec=FlockRouter)
        router.route = AsyncMock(
            return_value=HandOffRequest(
                next_agent="agent2",
                input={"output1": "Test output"},
            )
        )
        
        # Set the router on the agent
        self.agent1.handoff_router = router
        
        # Set up the context
        self.context.set_variable("FLOCK_CURRENT_AGENT", "agent1")
        self.context.set_variable("init_input", {"input1": "Test input"})
        
        # Mock the run_agent function to return a result
        mock_run_agent.return_value = {"output2": "Test output"}
        
        # Run the agent
        result = await run_agent(self.context)
        
        # Check that the router's route method was called
        router.route.assert_called_once()
        
        # Check that the result is from agent2
        self.assertEqual(result, {"output2": "Test output"})


def run_tests():
    """Run the tests."""
    unittest.main()


if __name__ == "__main__":
    run_tests()
