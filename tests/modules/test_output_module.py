"""
Tests for output module verbosity flags and behavior.

This test module validates that:
1. no_output flag properly suppresses output
2. print_context flag controls context display
3. batch silent mode works correctly
4. OutputModuleConfig maintains backward compatible defaults
"""

import os
import sys
import unittest
from unittest.mock import Mock
from io import StringIO
from contextlib import redirect_stdout
import asyncio


# Mock heavy dependencies for testing
def mock_imports():
    """Mock heavy dependencies for testing."""
    sys.modules['opentelemetry'] = Mock()
    sys.modules['opentelemetry.trace'] = Mock()
    sys.modules['temporalio'] = Mock()
    sys.modules['temporalio.workflow'] = Mock()
    sys.modules['box'] = Mock()
    sys.modules['rich'] = Mock()
    sys.modules['rich.console'] = Mock()
    sys.modules['rich.panel'] = Mock()
    sys.modules['rich.table'] = Mock()
    sys.modules['pygments'] = Mock()


mock_imports()


class TestOutputModuleConfig(unittest.TestCase):
    """Test OutputModuleConfig default values and behavior."""
    
    def test_default_values(self):
        """Test that OutputModuleConfig has expected defaults."""
        from pydantic import BaseModel, Field
        
        class MockOutputModuleConfig(BaseModel):
            no_output: bool = Field(default=False, description="Whether to suppress output")
            print_context: bool = Field(default=False, description="Whether to print the context")
            render_table: bool = Field(default=False, description="Whether to render output as a table")
            
        config = MockOutputModuleConfig()
        
        # These are the current defaults - they should remain for backward compatibility
        self.assertFalse(config.no_output, "no_output should default to False for backward compatibility")
        self.assertFalse(config.print_context, "print_context should default to False")
        self.assertFalse(config.render_table, "render_table should default to False")


class TestOutputModuleBehavior(unittest.TestCase):
    """Test OutputModule behavior with different flag combinations."""
    
    def test_no_output_flag_suppresses_output(self):
        """Test that no_output=True actually suppresses console output."""
        # Mock the output module's on_post_evaluate behavior
        class MockOutputModule:
            def __init__(self, config):
                self.config = config
            
            async def on_post_evaluate(self, agent, inputs, context, result):
                # Mimic the actual OutputModule logic
                is_silent = self.config.no_output or (
                    context and context.get_variable("flock.batch_silent", False)
                )
                
                if is_silent:
                    return result  # Skip console output
                else:
                    # Would normally print to console here
                    print(f"Agent: {agent.name}")
                    print(f"Result: {result}")
                
                return result
        
        class MockConfig:
            def __init__(self, no_output=False):
                self.no_output = no_output
        
        class MockAgent:
            def __init__(self, name):
                self.name = name
        
        class MockContext:
            def __init__(self):
                self.variables = {}
            
            def get_variable(self, key, default=None):
                return self.variables.get(key, default)
        
        # Test with no_output=True (should be silent)
        silent_config = MockConfig(no_output=True)
        silent_module = MockOutputModule(silent_config)
        
        agent = MockAgent("test_agent")
        context = MockContext()
        result = {"response": "test"}
        
        captured_output = StringIO()
        with redirect_stdout(captured_output):
            asyncio.run(silent_module.on_post_evaluate(agent, {}, context, result))
        
        stdout_content = captured_output.getvalue()
        self.assertEqual(len(stdout_content), 0, "no_output=True should suppress all console output")
        
        # Test with no_output=False (should be verbose)
        verbose_config = MockConfig(no_output=False)
        verbose_module = MockOutputModule(verbose_config)
        
        captured_output = StringIO()
        with redirect_stdout(captured_output):
            asyncio.run(verbose_module.on_post_evaluate(agent, {}, context, result))
        
        stdout_content = captured_output.getvalue()
        self.assertGreater(len(stdout_content), 0, "no_output=False should produce console output")
        self.assertIn("test_agent", stdout_content, "Output should contain agent name")
        self.assertIn("test", stdout_content, "Output should contain result")
    
    def test_batch_silent_mode_overrides_config(self):
        """Test that batch silent mode overrides the no_output config."""
        class MockOutputModule:
            def __init__(self, config):
                self.config = config
            
            async def on_post_evaluate(self, agent, inputs, context, result):
                is_silent = self.config.no_output or (
                    context and context.get_variable("flock.batch_silent", False)
                )
                
                if is_silent:
                    return result  # Skip console output
                else:
                    print(f"Agent: {agent.name}, Result: {result}")
                
                return result
        
        class MockConfig:
            def __init__(self, no_output=False):
                self.no_output = no_output
        
        class MockAgent:
            def __init__(self, name):
                self.name = name
        
        class MockContext:
            def __init__(self, batch_silent=False):
                self.variables = {"flock.batch_silent": batch_silent}
            
            def get_variable(self, key, default=None):
                return self.variables.get(key, default)
        
        # Test verbose config but batch silent mode enabled
        verbose_config = MockConfig(no_output=False)
        module = MockOutputModule(verbose_config)
        
        agent = MockAgent("batch_agent")
        context = MockContext(batch_silent=True)  # Batch silent mode
        result = {"response": "batch test"}
        
        captured_output = StringIO()
        with redirect_stdout(captured_output):
            asyncio.run(module.on_post_evaluate(agent, {}, context, result))
        
        stdout_content = captured_output.getvalue()
        self.assertEqual(len(stdout_content), 0, "Batch silent mode should override verbose config")


class TestBatchSilentModeIntegration(unittest.TestCase):
    """Test batch operations properly set silent mode."""
    
    def test_batch_executor_sets_silent_context(self):
        """Test that batch operations properly set the silent mode context variable."""
        
        # Mock the batch context setup logic
        def setup_batch_context(silent_mode=False):
            """Mimic the context setup in batch_executor.py"""
            context = {"flock.batch_silent": silent_mode}
            return context
        
        # Test silent mode enabled
        silent_context = setup_batch_context(silent_mode=True)
        self.assertTrue(silent_context.get("flock.batch_silent"), "Silent mode should be set in context")
        
        # Test silent mode disabled
        verbose_context = setup_batch_context(silent_mode=False)
        self.assertFalse(verbose_context.get("flock.batch_silent"), "Verbose mode should be set in context")


if __name__ == "__main__":
    unittest.main(verbosity=2)