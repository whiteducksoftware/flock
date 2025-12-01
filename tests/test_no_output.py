"""Tests for the no_output feature - suppressing all terminal output."""

import pytest
from pydantic import BaseModel

from flock import Flock, flock_type
from flock.components.agent import OutputUtilityComponent, OutputUtilityConfig
from flock.engines import DSPyEngine


@flock_type
class SimpleInput(BaseModel):
    """Simple input artifact for testing."""

    message: str


class SimpleOutput(BaseModel):
    """Simple output artifact for testing."""

    result: str


class TestNoOutputFlag:
    """Tests for the no_output configuration flag."""

    def test_flock_accepts_no_output_parameter(self):
        """Flock should accept no_output parameter."""
        flock = Flock("openai/gpt-4.1", no_output=True)
        assert flock.no_output is True

    def test_flock_no_output_defaults_to_false(self):
        """Flock should default no_output to False."""
        flock = Flock("openai/gpt-4.1", no_output=False)
        assert flock.no_output is False

    def test_agent_inherits_no_output_from_orchestrator(self):
        """Agents should inherit no_output from their orchestrator."""
        flock = Flock("openai/gpt-4.1", no_output=True)
        agent_builder = flock.agent("test_agent").consumes(SimpleInput).publishes(SimpleOutput)
        
        # Access the internal agent
        agent = agent_builder._agent
        assert agent.no_output is True

    def test_agent_no_output_false_when_orchestrator_false(self):
        """Agents should have no_output=False when orchestrator has no_output=False."""
        flock = Flock("openai/gpt-4.1", no_output=False)
        agent_builder = flock.agent("test_agent").consumes(SimpleInput).publishes(SimpleOutput)
        
        agent = agent_builder._agent
        assert agent.no_output is False

    def test_output_utility_config_no_output(self):
        """OutputUtilityConfig should accept no_output parameter."""
        config = OutputUtilityConfig(no_output=True)
        assert config.no_output is True

    def test_output_utility_config_no_output_default(self):
        """OutputUtilityConfig should default no_output to False."""
        config = OutputUtilityConfig()
        assert config.no_output is False

    def test_output_utility_component_with_no_output(self):
        """OutputUtilityComponent should respect no_output in config."""
        config = OutputUtilityConfig(no_output=True)
        component = OutputUtilityComponent(config=config)
        assert component.config.no_output is True

    def test_dspy_engine_accepts_no_output(self):
        """DSPyEngine should accept no_output parameter."""
        engine = DSPyEngine(no_output=True)
        assert engine.no_output is True

    def test_dspy_engine_no_output_default(self):
        """DSPyEngine should default no_output to False."""
        engine = DSPyEngine()
        assert engine.no_output is False

    def test_resolved_engine_inherits_no_output(self):
        """Default DSPy engine resolved by agent should inherit no_output."""
        flock = Flock("openai/gpt-4.1", no_output=True)
        agent_builder = flock.agent("test_agent").consumes(SimpleInput).publishes(SimpleOutput)
        
        agent = agent_builder._agent
        # Trigger engine resolution
        engines = agent._resolve_engines()
        
        assert len(engines) == 1
        assert engines[0].no_output is True

    def test_resolved_utilities_inherit_no_output(self):
        """Default OutputUtilityComponent resolved by agent should inherit no_output."""
        flock = Flock("openai/gpt-4.1", no_output=True)
        agent_builder = flock.agent("test_agent").consumes(SimpleInput).publishes(SimpleOutput)
        
        agent = agent_builder._agent
        # Trigger utilities resolution
        utilities = agent._resolve_utilities()
        
        # Find the OutputUtilityComponent
        output_utility = None
        for util in utilities:
            if isinstance(util, OutputUtilityComponent):
                output_utility = util
                break
        
        assert output_utility is not None
        assert output_utility.config.no_output is True


class TestNoOutputBannerSuppression:
    """Tests for banner suppression when no_output=True."""

    def test_banner_not_shown_with_no_output(self, capsys):
        """Banner should not be displayed when no_output=True."""
        # Create flock with no_output=True
        _flock = Flock("openai/gpt-4.1", no_output=True)
        
        captured = capsys.readouterr()
        # Banner contains the FLOCK ASCII art and duck emojis
        assert "🦆" not in captured.out
        assert "FLOCK" not in captured.out.upper() or "▒█" not in captured.out


class TestNoOutputIntegration:
    """Integration tests for no_output propagation through the system."""

    def test_full_propagation_chain(self):
        """Test that no_output propagates: Flock -> Agent -> Engine + Utilities."""
        flock = Flock("openai/gpt-4.1", no_output=True)
        
        # Create agent
        agent_builder = flock.agent("propagation_test").consumes(SimpleInput).publishes(SimpleOutput)
        agent = agent_builder._agent
        
        # Check agent
        assert agent.no_output is True
        
        # Check resolved engine
        engines = agent._resolve_engines()
        assert len(engines) > 0
        assert engines[0].no_output is True
        
        # Check resolved utilities
        utilities = agent._resolve_utilities()
        output_utils = [u for u in utilities if isinstance(u, OutputUtilityComponent)]
        assert len(output_utils) > 0
        assert output_utils[0].config.no_output is True

    def test_custom_engine_not_affected(self):
        """Custom engines should not be affected by agent's no_output."""
        flock = Flock("openai/gpt-4.1", no_output=True)
        
        # Create custom engine without no_output
        custom_engine = DSPyEngine(model="openai/gpt-4.1", no_output=False)
        
        agent_builder = (
            flock.agent("custom_engine_test")
            .consumes(SimpleInput)
            .publishes(SimpleOutput)
            .with_engines(custom_engine)
        )
        agent = agent_builder._agent
        
        # Agent should have no_output=True
        assert agent.no_output is True
        
        # But custom engine should keep its own setting
        engines = agent._resolve_engines()
        assert len(engines) == 1
        assert engines[0].no_output is False  # Custom engine keeps its setting

    def test_custom_utilities_not_affected(self):
        """Custom utilities should not be affected by agent's no_output."""
        flock = Flock("openai/gpt-4.1", no_output=True)
        
        # Create custom utility without no_output
        custom_config = OutputUtilityConfig(no_output=False)
        custom_utility = OutputUtilityComponent(config=custom_config)
        
        agent_builder = (
            flock.agent("custom_utility_test")
            .consumes(SimpleInput)
            .publishes(SimpleOutput)
            .with_utilities(custom_utility)
        )
        agent = agent_builder._agent
        
        # Agent should have no_output=True
        assert agent.no_output is True
        
        # But custom utility should keep its own setting
        utilities = agent._resolve_utilities()
        output_utils = [u for u in utilities if isinstance(u, OutputUtilityComponent)]
        assert len(output_utils) == 1
        assert output_utils[0].config.no_output is False  # Custom utility keeps its setting
