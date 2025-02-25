"""Unit tests for the HandoffRouter class."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from flock.core.context.context import FlockContext
from flock.core.execution.handoff_router import HandoffRouter
from flock.core.flock_agent import FlockAgent, HandOff
from flock.core.registry.agent_registry import Registry


class TestHandoffRouter(unittest.TestCase):
    """Test cases for the HandoffRouter class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock registry instead of using the real one
        self.registry = MagicMock()
        self.router = HandoffRouter(self.registry)
        
        # Create mock agents
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
        
        self.agent3 = FlockAgent(
            name="agent3",
            model="openai/gpt-4o",
            description="Agent 3 description",
            input="input3: str | Input 3 description",
            output="output3: str | Output 3 description",
        )
        
        # Set up the mock registry
        self.registry._agents = [self.agent1, self.agent2, self.agent3]
        self.registry.get_agent.side_effect = lambda name: next((a for a in self.registry._agents if a.name == name), None)
        
        # Create context
        self.context = FlockContext()

    def test_get_available_agents(self):
        """Test getting available agents."""
        # Get available agents excluding agent1
        available_agents = self.router._get_available_agents("agent1")
        
        # Check that agent1 is excluded
        self.assertEqual(len(available_agents), 2)
        self.assertIn(self.agent2, available_agents)
        self.assertIn(self.agent3, available_agents)
        
        # Get available agents excluding agent2
        available_agents = self.router._get_available_agents("agent2")
        
        # Check that agent2 is excluded
        self.assertEqual(len(available_agents), 2)
        self.assertIn(self.agent1, available_agents)
        self.assertIn(self.agent3, available_agents)

    def test_create_selection_prompt(self):
        """Test creating the selection prompt."""
        # Create a result
        result = {"output1": "Test output"}
        
        # Get available agents
        available_agents = [self.agent2, self.agent3]
        
        # Create the prompt
        prompt = self.router._create_selection_prompt(
            self.agent1, result, available_agents
        )
        
        # Check that the prompt contains the expected information
        self.assertIn("CURRENT AGENT:", prompt)
        self.assertIn("agent1", prompt)
        self.assertIn("Agent 1 description", prompt)
        
        self.assertIn("CURRENT AGENT'S OUTPUT:", prompt)
        self.assertIn("Test output", prompt)
        
        self.assertIn("AVAILABLE AGENTS:", prompt)
        self.assertIn("agent2", prompt)
        self.assertIn("Agent 2 description", prompt)
        self.assertIn("agent3", prompt)
        self.assertIn("Agent 3 description", prompt)

    def test_create_next_input(self):
        """Test creating the next input."""
        # Create a result
        result = {"output1": "Test output"}
        
        # Create the next input
        next_input = self.router._create_next_input(
            self.agent1, result, self.agent2
        )
        
        # Check that the next input contains the expected information
        self.assertIn("previous_agent_output", next_input)
        self.assertEqual(next_input["previous_agent_output"]["agent_name"], "agent1")
        self.assertEqual(next_input["previous_agent_output"]["result"], result)
        
        # Check that the output1 field is mapped to the next agent's input
        self.assertIn("output1", next_input)
        self.assertEqual(next_input["output1"], "Test output")

    @patch("litellm.acompletion")
    async def test_select_next_agent_success(self, mock_acompletion):
        """Test selecting the next agent with a successful LLM response."""
        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "next_agent": "agent2",
                        "score": 0.8,
                        "reasoning": "Agent 2 is the best match because it accepts output1 as input."
                    })
                )
            )
        ]
        mock_acompletion.return_value = mock_response
        
        # Create a result
        result = {"output1": "Test output"}
        
        # Get available agents
        available_agents = [self.agent2, self.agent3]
        
        # Select the next agent
        next_agent, score = await self.router._select_next_agent(
            self.agent1, result, available_agents
        )
        
        # Check that the next agent is agent2
        self.assertEqual(next_agent, "agent2")
        self.assertEqual(score, 0.8)
        
        # Check that the LLM was called with the expected arguments
        mock_acompletion.assert_called_once()
        args, kwargs = mock_acompletion.call_args
        self.assertEqual(kwargs["model"], "openai/gpt-4o")
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertEqual(kwargs["max_tokens"], 500)
        self.assertEqual(len(kwargs["messages"]), 1)
        self.assertEqual(kwargs["messages"][0]["role"], "user")

    @patch("litellm.acompletion")
    async def test_select_next_agent_invalid_json(self, mock_acompletion):
        """Test selecting the next agent with an invalid JSON response."""
        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="This is not valid JSON"
                )
            )
        ]
        mock_acompletion.return_value = mock_response
        
        # Create a result
        result = {"output1": "Test output"}
        
        # Get available agents
        available_agents = [self.agent2, self.agent3]
        
        # Select the next agent
        next_agent, score = await self.router._select_next_agent(
            self.agent1, result, available_agents
        )
        
        # Check that no agent was selected
        self.assertEqual(next_agent, "")
        self.assertEqual(score, 0.0)

    @patch("litellm.acompletion")
    async def test_select_next_agent_fallback(self, mock_acompletion):
        """Test selecting the next agent with a fallback."""
        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="I think agent2 would be the best choice."
                )
            )
        ]
        mock_acompletion.return_value = mock_response
        
        # Create a result
        result = {"output1": "Test output"}
        
        # Get available agents
        available_agents = [self.agent2, self.agent3]
        
        # Select the next agent
        next_agent, score = await self.router._select_next_agent(
            self.agent1, result, available_agents
        )
        
        # Check that agent2 was selected as a fallback
        self.assertEqual(next_agent, "agent2")
        self.assertEqual(score, 0.6)

    @patch("litellm.acompletion")
    async def test_select_next_agent_error(self, mock_acompletion):
        """Test selecting the next agent with an error."""
        # Mock the LLM response to raise an exception
        mock_acompletion.side_effect = Exception("Test error")
        
        # Create a result
        result = {"output1": "Test output"}
        
        # Get available agents
        available_agents = [self.agent2, self.agent3]
        
        # Select the next agent
        next_agent, score = await self.router._select_next_agent(
            self.agent1, result, available_agents
        )
        
        # Check that no agent was selected
        self.assertEqual(next_agent, "")
        self.assertEqual(score, 0.0)

    @patch("flock.core.execution.handoff_router.HandoffRouter._select_next_agent")
    async def test_route_success(self, mock_select_next_agent):
        """Test routing with a successful selection."""
        # Mock the select_next_agent method
        mock_select_next_agent.return_value = ("agent2", 0.8)
        
        # Create a result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await self.router.route(self.agent1, result, self.context)
        
        # Check that the handoff is correct
        self.assertEqual(handoff.next_agent, "agent2")
        self.assertIn("previous_agent_output", handoff.input)
        self.assertEqual(handoff.input["previous_agent_output"]["agent_name"], "agent1")
        self.assertEqual(handoff.input["previous_agent_output"]["result"], result)
        self.assertIn("output1", handoff.input)
        self.assertEqual(handoff.input["output1"], "Test output")

    @patch("flock.core.execution.handoff_router.HandoffRouter._select_next_agent")
    async def test_route_no_agents(self, mock_select_next_agent):
        """Test routing with no available agents."""
        # Create a registry with only one agent
        registry = Registry()
        registry.register_agent(self.agent1)
        router = HandoffRouter(registry)
        
        # Create a result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await router.route(self.agent1, result, self.context)
        
        # Check that no agent was selected
        self.assertEqual(handoff.next_agent, "")
        self.assertEqual(handoff.input, {})
        
        # Check that select_next_agent was not called
        mock_select_next_agent.assert_not_called()

    @patch("flock.core.execution.handoff_router.HandoffRouter._select_next_agent")
    async def test_route_no_suitable_agent(self, mock_select_next_agent):
        """Test routing with no suitable agent."""
        # Mock the select_next_agent method
        mock_select_next_agent.return_value = ("", 0.0)
        
        # Create a result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await self.router.route(self.agent1, result, self.context)
        
        # Check that no agent was selected
        self.assertEqual(handoff.next_agent, "")
        self.assertEqual(handoff.input, {})

    @patch("flock.core.execution.handoff_router.HandoffRouter._select_next_agent")
    async def test_route_agent_not_found(self, mock_select_next_agent):
        """Test routing with an agent that is not found."""
        # Mock the select_next_agent method
        mock_select_next_agent.return_value = ("non_existent_agent", 0.8)
        
        # Create a result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await self.router.route(self.agent1, result, self.context)
        
        # Check that no agent was selected
        self.assertEqual(handoff.next_agent, "")
        self.assertEqual(handoff.input, {})


def run_tests():
    """Run the tests."""
    unittest.main()


if __name__ == "__main__":
    run_tests()
