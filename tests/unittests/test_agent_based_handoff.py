"""Unit tests for the agent-based auto-handoff functionality."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from flock.core.context.context import FlockContext
from flock.core.execution.agent_based_handoff_router import AgentBasedHandoffRouter
from flock.core.execution.handoff_agent import AgentInfo, HandoffAgent, HandoffDecision
from flock.core.flock_agent import FlockAgent, HandOffRequest
from flock.core.registry.agent_registry import Registry


class TestHandoffAgent(unittest.TestCase):
    """Test cases for the HandoffAgent class."""

    def setUp(self):
        """Set up test fixtures."""
        self.agent = HandoffAgent(model="openai/gpt-4o")

    def test_initialization(self):
        """Test that the HandoffAgent initializes correctly."""
        self.assertEqual(self.agent.name, "handoff_agent")
        self.assertEqual(
            self.agent.description,
            "An agent that determines the best next agent in a workflow",
        )
        self.assertIn("current_agent_name", self.agent.input)
        self.assertIn("current_agent_description", self.agent.input)
        self.assertIn("current_agent_input", self.agent.input)
        self.assertIn("current_agent_output", self.agent.input)
        self.assertIn("current_result", self.agent.input)
        self.assertIn("available_agents", self.agent.input)
        self.assertIn("decision", self.agent.output)

    @patch.object(FlockAgent, "evaluate", new_callable=AsyncMock)
    async def test_evaluate(self, mock_evaluate):
        """Test that the HandoffAgent's evaluate method works correctly."""
        # Mock the evaluate method to return a decision
        mock_evaluate.return_value = {
            "decision": HandoffDecision(
                agent_name="summary_agent",
                confidence=0.9,
                input_mapping={"findings": "findings"},
                reasoning="The research is complete and needs to be summarized.",
            )
        }

        # Create test inputs
        inputs = {
            "current_agent_name": "research_agent",
            "current_agent_description": "Researches topics",
            "current_agent_input": "topic: str",
            "current_agent_output": "findings: str",
            "current_result": {"findings": "Some research findings"},
            "available_agents": [
                AgentInfo(
                    name="summary_agent",
                    description="Creates summaries",
                    input_schema={"findings": "str"},
                    output_schema={"summary": "str"},
                )
            ],
        }

        # Call evaluate
        result = await self.agent.evaluate(inputs)

        # Check that evaluate was called with the correct inputs
        mock_evaluate.assert_called_once_with(inputs)

        # Check the result
        self.assertIn("decision", result)
        self.assertEqual(result["decision"].agent_name, "summary_agent")
        self.assertEqual(result["decision"].confidence, 0.9)
        self.assertEqual(result["decision"].input_mapping, {"findings": "findings"})
        self.assertEqual(
            result["decision"].reasoning,
            "The research is complete and needs to be summarized.",
        )


class TestAgentBasedHandoffRouter(unittest.TestCase):
    """Test cases for the AgentBasedHandoffRouter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = MagicMock(spec=Registry)
        self.router = AgentBasedHandoffRouter(self.registry)
        
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
        
        # Create context
        self.context = FlockContext()

    def test_initialization(self):
        """Test that the AgentBasedHandoffRouter initializes correctly."""
        self.assertEqual(self.router.registry, self.registry)
        self.assertIsInstance(self.router.handoff_agent, HandoffAgent)
        self.registry.register_agent.assert_called_once_with(self.router.handoff_agent)

    def test_get_available_agents(self):
        """Test getting available agents."""
        # Set up the registry
        self.registry._agents = [self.agent1, self.agent2, self.router.handoff_agent]
        
        # Get available agents excluding agent1
        available_agents = self.router._get_available_agents("agent1")
        
        # Check that agent1 and handoff_agent are excluded
        self.assertEqual(len(available_agents), 1)
        self.assertEqual(available_agents[0].name, "agent2")
        self.assertEqual(available_agents[0].description, "Agent 2 description")

    def test_get_schema_from_agent(self):
        """Test extracting schema from an agent."""
        # Extract input schema
        input_schema = self.router._get_schema_from_agent(self.agent2, "input")
        
        # Check that the schema is extracted correctly
        self.assertEqual(len(input_schema), 2)
        self.assertIn("input2", input_schema)
        self.assertIn("output1", input_schema)
        
        # Extract output schema
        output_schema = self.router._get_schema_from_agent(self.agent2, "output")
        
        # Check that the schema is extracted correctly
        self.assertEqual(len(output_schema), 1)
        self.assertIn("output2", output_schema)

    def test_get_input_keys(self):
        """Test extracting input keys from an agent."""
        # Mock _get_schema_from_agent to return a schema
        self.router._get_schema_from_agent = MagicMock(
            return_value={"input2": "str", "output1": "str"}
        )
        
        # Extract input keys
        input_keys = self.router._get_input_keys(self.agent2)
        
        # Check that the keys are extracted correctly
        self.assertEqual(len(input_keys), 2)
        self.assertIn("input2", input_keys)
        self.assertIn("output1", input_keys)

    def test_create_next_input_with_mapping(self):
        """Test creating next input with mapping."""
        # Create result
        result = {"output1": "Test output"}
        
        # Create input mapping
        input_mapping = {"input2": "output1"}
        
        # Mock _get_input_keys to return input keys
        self.router._get_input_keys = MagicMock(return_value=["input2", "output1"])
        
        # Create next input
        next_input = self.router._create_next_input(
            self.agent1, result, self.agent2, input_mapping
        )
        
        # Check that the next input contains the expected information
        self.assertIn("previous_agent_output", next_input)
        self.assertEqual(next_input["previous_agent_output"]["agent_name"], "agent1")
        self.assertEqual(next_input["previous_agent_output"]["result"], result)
        
        # Check that the output1 field is mapped to input2
        self.assertIn("input2", next_input)
        self.assertEqual(next_input["input2"], "Test output")

    def test_create_next_input_without_mapping(self):
        """Test creating next input without mapping."""
        # Create result
        result = {"output1": "Test output"}
        
        # Mock _get_input_keys to return input keys
        self.router._get_input_keys = MagicMock(return_value=["input2", "output1"])
        
        # Create next input
        next_input = self.router._create_next_input(
            self.agent1, result, self.agent2
        )
        
        # Check that the next input contains the expected information
        self.assertIn("previous_agent_output", next_input)
        self.assertEqual(next_input["previous_agent_output"]["agent_name"], "agent1")
        self.assertEqual(next_input["previous_agent_output"]["result"], result)
        
        # Check that the output1 field is directly mapped
        self.assertIn("output1", next_input)
        self.assertEqual(next_input["output1"], "Test output")

    @patch.object(HandoffAgent, "run_async", new_callable=AsyncMock)
    async def test_route_success(self, mock_run_async):
        """Test routing with a successful selection."""
        # Mock the run_async method to return a decision
        mock_run_async.return_value = {
            "decision": HandoffDecision(
                agent_name="agent2",
                confidence=0.9,
                input_mapping={"input2": "output1"},
                reasoning="Agent 2 is the best match because it accepts output1 as input.",
            )
        }
        
        # Set up the registry
        self.registry._agents = [self.agent1, self.agent2, self.router.handoff_agent]
        self.registry.get_agent = MagicMock(return_value=self.agent2)
        
        # Mock _get_available_agents to return available agents
        self.router._get_available_agents = MagicMock(
            return_value=[
                AgentInfo(
                    name="agent2",
                    description="Agent 2 description",
                    input_schema={"input2": "str", "output1": "str"},
                    output_schema={"output2": "str"},
                )
            ]
        )
        
        # Mock _create_next_input to return next input
        self.router._create_next_input = MagicMock(
            return_value={"input2": "Test output"}
        )
        
        # Create result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await self.router.route(self.agent1, result, self.context)
        
        # Check that the handoff is correct
        self.assertEqual(handoff.next_agent, "agent2")
        self.assertEqual(handoff.input, {"input2": "Test output"})

    @patch.object(HandoffAgent, "run_async", new_callable=AsyncMock)
    async def test_route_no_agents(self, mock_run_async):
        """Test routing with no available agents."""
        # Mock _get_available_agents to return no agents
        self.router._get_available_agents = MagicMock(return_value=[])
        
        # Create result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await self.router.route(self.agent1, result, self.context)
        
        # Check that no agent was selected
        self.assertEqual(handoff.next_agent, "")
        self.assertEqual(handoff.input, {})
        
        # Check that run_async was not called
        mock_run_async.assert_not_called()

    @patch.object(HandoffAgent, "run_async", new_callable=AsyncMock)
    async def test_route_low_confidence(self, mock_run_async):
        """Test routing with low confidence."""
        # Mock the run_async method to return a decision with low confidence
        mock_run_async.return_value = {
            "decision": HandoffDecision(
                agent_name="agent2",
                confidence=0.4,  # Below threshold
                input_mapping={"input2": "output1"},
                reasoning="Not sure if this is the right agent.",
            )
        }
        
        # Set up the registry
        self.registry._agents = [self.agent1, self.agent2, self.router.handoff_agent]
        
        # Mock _get_available_agents to return available agents
        self.router._get_available_agents = MagicMock(
            return_value=[
                AgentInfo(
                    name="agent2",
                    description="Agent 2 description",
                    input_schema={"input2": "str", "output1": "str"},
                    output_schema={"output2": "str"},
                )
            ]
        )
        
        # Create result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await self.router.route(self.agent1, result, self.context)
        
        # Check that no agent was selected
        self.assertEqual(handoff.next_agent, "")
        self.assertEqual(handoff.input, {})

    @patch.object(HandoffAgent, "run_async", new_callable=AsyncMock)
    async def test_route_invalid_decision(self, mock_run_async):
        """Test routing with an invalid decision."""
        # Mock the run_async method to return an invalid decision
        mock_run_async.return_value = {"not_a_decision": "invalid"}
        
        # Set up the registry
        self.registry._agents = [self.agent1, self.agent2, self.router.handoff_agent]
        
        # Mock _get_available_agents to return available agents
        self.router._get_available_agents = MagicMock(
            return_value=[
                AgentInfo(
                    name="agent2",
                    description="Agent 2 description",
                    input_schema={"input2": "str", "output1": "str"},
                    output_schema={"output2": "str"},
                )
            ]
        )
        
        # Create result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await self.router.route(self.agent1, result, self.context)
        
        # Check that no agent was selected
        self.assertEqual(handoff.next_agent, "")
        self.assertEqual(handoff.input, {})

    @patch.object(HandoffAgent, "run_async", new_callable=AsyncMock)
    async def test_route_agent_not_found(self, mock_run_async):
        """Test routing with an agent that is not found."""
        # Mock the run_async method to return a decision
        mock_run_async.return_value = {
            "decision": HandoffDecision(
                agent_name="non_existent_agent",
                confidence=0.9,
                input_mapping={"input2": "output1"},
                reasoning="This agent would be perfect, but it doesn't exist.",
            )
        }
        
        # Set up the registry
        self.registry._agents = [self.agent1, self.agent2, self.router.handoff_agent]
        self.registry.get_agent = MagicMock(return_value=None)
        
        # Mock _get_available_agents to return available agents
        self.router._get_available_agents = MagicMock(
            return_value=[
                AgentInfo(
                    name="agent2",
                    description="Agent 2 description",
                    input_schema={"input2": "str", "output1": "str"},
                    output_schema={"output2": "str"},
                )
            ]
        )
        
        # Create result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await self.router.route(self.agent1, result, self.context)
        
        # Check that no agent was selected
        self.assertEqual(handoff.next_agent, "")
        self.assertEqual(handoff.input, {})

    @patch.object(HandoffAgent, "run_async", new_callable=AsyncMock)
    async def test_route_error(self, mock_run_async):
        """Test routing with an error."""
        # Mock the run_async method to raise an exception
        mock_run_async.side_effect = Exception("Test error")
        
        # Set up the registry
        self.registry._agents = [self.agent1, self.agent2, self.router.handoff_agent]
        
        # Mock _get_available_agents to return available agents
        self.router._get_available_agents = MagicMock(
            return_value=[
                AgentInfo(
                    name="agent2",
                    description="Agent 2 description",
                    input_schema={"input2": "str", "output1": "str"},
                    output_schema={"output2": "str"},
                )
            ]
        )
        
        # Create result
        result = {"output1": "Test output"}
        
        # Route to the next agent
        handoff = await self.router.route(self.agent1, result, self.context)
        
        # Check that no agent was selected
        self.assertEqual(handoff.next_agent, "")
        self.assertEqual(handoff.input, {})


class TestIntegration(unittest.TestCase):
    """Integration tests for the agent-based auto-handoff functionality."""

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
        self.context.set_variable("use_agent_based_handoff", True)

    @patch("flock.core.registry.agent_registry.Registry.get_agent")
    @patch("flock.core.flock_agent.FlockAgent.run_async")
    @patch("flock.core.execution.agent_based_handoff_router.AgentBasedHandoffRouter.route")
    async def test_agent_based_auto_handoff(self, mock_route, mock_run_async, mock_get_agent):
        """Test agent-based auto-handoff with a successful handoff."""
        # Import the run_agent function
        from flock.workflow.activities import run_agent
        
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
        mock_route.return_value = HandOffRequest(
            next_agent="agent2",
            input={
                "output1": "Test output",
                "previous_agent_output": {
                    "agent_name": "agent1",
                    "result": {"output1": "Test output"},
                },
            },
        )
        
        # Set up the context
        self.context.set_variable("FLOCK_CURRENT_AGENT", "agent1")
        self.context.set_variable("init_input", {"input1": "Test input"})
        
        # Run the agent
        result = await run_agent(self.context)
        
        # Check that the agent was run
        mock_run_async.assert_called()
        
        # Check that the route method was called
        mock_route.assert_called_once()
        
        # Check that the result is from agent2
        self.assertEqual(result, {"output2": "Test output"})


def run_tests():
    """Run the tests."""
    unittest.main()


if __name__ == "__main__":
    run_tests()
