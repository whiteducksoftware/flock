"""Integration tests for the auto-handoff functionality."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_CURRENT_AGENT
from flock.core.flock_agent import FlockAgent, HandOff
from flock.core.registry.agent_registry import Registry
from flock.workflow.activities import run_agent


class TestAutoHandoff(unittest.TestCase):
    """Test cases for the auto-handoff functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create registry
        self.registry = Registry()
        
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
        
        # Register agents
        self.registry.register_agent(self.agent1)
        self.registry.register_agent(self.agent2)
        
        # Create context
        self.context = FlockContext()
        self.context.set_variable(FLOCK_CURRENT_AGENT, "agent1")
        self.context.set_variable("init_input", {"input1": "Test input"})

    @patch("flock.core.registry.agent_registry.Registry.get_agent")
    @patch("flock.core.flock_agent.FlockAgent.run_async")
    @patch("flock.core.execution.handoff_router.HandoffRouter.route")
    async def test_auto_handoff_success(self, mock_route, mock_run_async, mock_get_agent):
        """Test auto-handoff with a successful handoff."""
        # Set up the agent1 to use auto-handoff
        self.agent1.hand_off = "auto_handoff"
        
        # Mock the run_async method to return a result
        mock_run_async.return_value = {"output1": "Test output"}
        
        # Mock the get_agent method to return the agents
        mock_get_agent.side_effect = lambda name: {
            "agent1": self.agent1,
            "agent2": self.agent2,
        }.get(name)
        
        # Mock the route method to return a handoff to agent2
        mock_route.return_value = HandOff(
            next_agent="agent2",
            input={
                "output1": "Test output",
                "previous_agent_output": {
                    "agent_name": "agent1",
                    "result": {"output1": "Test output"},
                },
            },
        )
        
        # Run the agent
        result = await run_agent(self.context)
        
        # Check that the agent was run
        mock_run_async.assert_called()
        
        # Check that the route method was called
        mock_route.assert_called_once()
        
        # Check that the result is from agent2
        self.assertEqual(result, {"output2": "Test output"})

    @patch("flock.core.registry.agent_registry.Registry.get_agent")
    @patch("flock.core.flock_agent.FlockAgent.run_async")
    @patch("flock.core.execution.handoff_router.HandoffRouter.route")
    async def test_auto_handoff_no_suitable_agent(self, mock_route, mock_run_async, mock_get_agent):
        """Test auto-handoff with no suitable agent."""
        # Set up the agent1 to use auto-handoff
        self.agent1.hand_off = "auto_handoff"
        
        # Mock the run_async method to return a result
        mock_run_async.return_value = {"output1": "Test output"}
        
        # Mock the get_agent method to return the agents
        mock_get_agent.side_effect = lambda name: {
            "agent1": self.agent1,
            "agent2": self.agent2,
        }.get(name)
        
        # Mock the route method to return a handoff with no next agent
        mock_route.return_value = HandOff(
            next_agent="",
            input={},
        )
        
        # Run the agent
        result = await run_agent(self.context)
        
        # Check that the agent was run
        mock_run_async.assert_called()
        
        # Check that the route method was called
        mock_route.assert_called_once()
        
        # Check that the result is from agent1
        self.assertEqual(result, {"output1": "Test output"})

    @patch("flock.core.registry.agent_registry.Registry.get_agent")
    @patch("flock.core.flock_agent.FlockAgent.run_async")
    @patch("flock.core.execution.handoff_router.HandoffRouter.route")
    async def test_auto_handoff_error(self, mock_route, mock_run_async, mock_get_agent):
        """Test auto-handoff with an error."""
        # Set up the agent1 to use auto-handoff
        self.agent1.hand_off = "auto_handoff"
        
        # Mock the run_async method to return a result
        mock_run_async.return_value = {"output1": "Test output"}
        
        # Mock the get_agent method to return the agents
        mock_get_agent.side_effect = lambda name: {
            "agent1": self.agent1,
            "agent2": self.agent2,
        }.get(name)
        
        # Mock the route method to raise an exception
        mock_route.side_effect = Exception("Test error")
        
        # Run the agent
        result = await run_agent(self.context)
        
        # Check that the agent was run
        mock_run_async.assert_called()
        
        # Check that the route method was called
        mock_route.assert_called_once()
        
        # Check that the result is an error
        self.assertIn("error", result)
        self.assertIn("Auto-handoff error", result["error"])

    @patch("flock.core.registry.agent_registry.Registry.get_agent")
    @patch("flock.core.flock_agent.FlockAgent.run_async")
    async def test_regular_handoff(self, mock_run_async, mock_get_agent):
        """Test regular handoff (not auto-handoff)."""
        # Set up the agent1 to hand off to agent2
        self.agent1.hand_off = "agent2"
        
        # Mock the run_async method to return a result
        mock_run_async.side_effect = [
            {"output1": "Test output"},  # agent1 result
            {"output2": "Test output"},  # agent2 result
        ]
        
        # Mock the get_agent method to return the agents
        mock_get_agent.side_effect = lambda name: {
            "agent1": self.agent1,
            "agent2": self.agent2,
        }.get(name)
        
        # Run the agent
        result = await run_agent(self.context)
        
        # Check that the agent was run twice
        self.assertEqual(mock_run_async.call_count, 2)
        
        # Check that the result is from agent2
        self.assertEqual(result, {"output2": "Test output"})

    @patch("flock.core.registry.agent_registry.Registry.get_agent")
    @patch("flock.core.flock_agent.FlockAgent.run_async")
    async def test_no_handoff(self, mock_run_async, mock_get_agent):
        """Test with no handoff."""
        # Set up the agent1 to have no handoff
        self.agent1.hand_off = None
        
        # Mock the run_async method to return a result
        mock_run_async.return_value = {"output1": "Test output"}
        
        # Mock the get_agent method to return the agents
        mock_get_agent.side_effect = lambda name: {
            "agent1": self.agent1,
            "agent2": self.agent2,
        }.get(name)
        
        # Run the agent
        result = await run_agent(self.context)
        
        # Check that the agent was run once
        mock_run_async.assert_called_once()
        
        # Check that the result is from agent1
        self.assertEqual(result, {"output1": "Test output"})


def run_tests():
    """Run the tests."""
    unittest.main()


if __name__ == "__main__":
    run_tests()
