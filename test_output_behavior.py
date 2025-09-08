#!/usr/bin/env python3
"""Test script to understand current output behavior and validate flags."""

import sys
import os
import asyncio
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flock.core.flock import Flock
from flock.core.flock_factory import FlockFactory
from flock.modules.output.output_module import OutputModule, OutputModuleConfig
from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_BATCH_SILENT_MODE


def test_default_output_behavior():
    """Test what happens with default output settings."""
    print("=== Testing Default Output Behavior ===")
    
    try:
        # Create a simple agent with default settings
        agent = FlockFactory.create_default_agent(
            name="test_agent",
            input="message: str",
            output="response: str",
            model="openai/gpt-4o-mini"  # Use a smaller model for testing
        )
        
        print(f"Agent created with default no_output: {agent.modules['output'].config.no_output}")
        print(f"Agent created with default print_context: {agent.modules['output'].config.print_context}")
        
        # Create a flock instance
        flock = Flock(name="test_flock")
        flock.add_agent(agent)
        
        # Capture output
        captured_output = StringIO()
        captured_error = StringIO()
        
        with redirect_stdout(captured_output), redirect_stderr(captured_error):
            try:
                # This will likely fail due to API key, but we want to see the output behavior
                result = flock.run(
                    start_agent="test_agent",
                    input={"message": "Hello, test!"}
                )
            except Exception as e:
                print(f"Expected error (no API key): {e}")
        
        stdout_content = captured_output.getvalue()
        stderr_content = captured_error.getvalue()
        
        print(f"Stdout length: {len(stdout_content)}")
        print(f"Stderr length: {len(stderr_content)}")
        print("First 200 chars of stdout:", stdout_content[:200] if stdout_content else "None")
        print("First 200 chars of stderr:", stderr_content[:200] if stderr_content else "None")
        
    except Exception as e:
        print(f"Error in test: {e}")
        import traceback
        traceback.print_exc()


def test_no_output_flag():
    """Test that no_output flag actually suppresses output."""
    print("\n=== Testing no_output=True ===")
    
    try:
        # Create agent with no_output=True
        agent = FlockFactory.create_default_agent(
            name="silent_agent",
            input="message: str", 
            output="response: str",
            no_output=True,  # This should suppress output
            model="openai/gpt-4o-mini"
        )
        
        print(f"Silent agent no_output setting: {agent.modules['output'].config.no_output}")
        
        # Create a flock instance
        flock = Flock(name="silent_flock")
        flock.add_agent(agent)
        
        # Capture output
        captured_output = StringIO()
        captured_error = StringIO()
        
        with redirect_stdout(captured_output), redirect_stderr(captured_error):
            try:
                result = flock.run(
                    start_agent="silent_agent",
                    input={"message": "Hello, silent test!"}
                )
            except Exception as e:
                print(f"Expected error (no API key): {e}")
        
        stdout_content = captured_output.getvalue()
        stderr_content = captured_error.getvalue()
        
        print(f"Silent stdout length: {len(stdout_content)}")
        print(f"Silent stderr length: {len(stderr_content)}")
        print("Silent stdout content:", stdout_content[:200] if stdout_content else "None")
        
    except Exception as e:
        print(f"Error in silent test: {e}")
        import traceback
        traceback.print_exc()


def test_batch_silent_mode():
    """Test batch processing with silent mode."""
    print("\n=== Testing Batch Silent Mode ===")
    
    try:
        # Create agent
        agent = FlockFactory.create_default_agent(
            name="batch_agent",
            input="message: str",
            output="response: str", 
            model="openai/gpt-4o-mini"
        )
        
        # Create a flock instance
        flock = Flock(name="batch_flock")
        flock.add_agent(agent)
        
        # Test batch with silent_mode=True
        batch_inputs = [
            {"message": "Test 1"},
            {"message": "Test 2"}, 
            {"message": "Test 3"}
        ]
        
        captured_output = StringIO()
        captured_error = StringIO()
        
        with redirect_stdout(captured_output), redirect_stderr(captured_error):
            try:
                results = flock.run_batch(
                    start_agent="batch_agent",
                    batch_inputs=batch_inputs,
                    silent_mode=True,  # This should show progress bar instead of verbose output
                    return_errors=True  # Don't stop on first error
                )
            except Exception as e:
                print(f"Batch error: {e}")
        
        stdout_content = captured_output.getvalue()
        stderr_content = captured_error.getvalue()
        
        print(f"Batch silent stdout length: {len(stdout_content)}")
        print(f"Batch silent stderr length: {len(stderr_content)}")
        print("Batch stdout preview:", stdout_content[:300] if stdout_content else "None")
        
    except Exception as e:
        print(f"Error in batch test: {e}")
        import traceback
        traceback.print_exc()


def test_output_module_directly():
    """Test OutputModule behavior directly."""
    print("\n=== Testing OutputModule Directly ===")
    
    try:
        # Test with default config
        default_config = OutputModuleConfig()
        print(f"Default no_output: {default_config.no_output}")
        print(f"Default print_context: {default_config.print_context}")
        
        # Test with silent config
        silent_config = OutputModuleConfig(no_output=True)
        print(f"Silent no_output: {silent_config.no_output}")
        
        # Test output module behavior
        output_module = OutputModule("test", config=default_config)
        context = FlockContext()
        
        test_result = {
            "response": "This is a test response",
            "metadata": {"tokens": 100, "latency": 1.5}
        }
        
        # Capture output from module
        captured_output = StringIO()
        with redirect_stdout(captured_output):
            # This should trigger output
            asyncio.run(output_module.on_post_evaluate(
                agent=None,  # We'll need to mock this
                inputs={"message": "test"}, 
                context=context,
                result=test_result
            ))
        
        stdout_content = captured_output.getvalue()
        print(f"Module output length: {len(stdout_content)}")
        print("Module output preview:", stdout_content[:200] if stdout_content else "None")
        
    except Exception as e:
        print(f"Error in module test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Testing Flock Output Behavior\n")
    
    # Run tests
    test_default_output_behavior()
    test_no_output_flag()
    test_batch_silent_mode()
    test_output_module_directly()
    
    print("\n=== Tests completed ===")