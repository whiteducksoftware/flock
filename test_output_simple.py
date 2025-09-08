#!/usr/bin/env python3
"""Simple test to understand output module behavior without API calls."""

import sys
import os
import asyncio
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flock.modules.output.output_module import OutputModule, OutputModuleConfig
from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_BATCH_SILENT_MODE


class MockAgent:
    """Mock agent for testing."""
    def __init__(self, name):
        self.name = name


async def test_output_module_default():
    """Test OutputModule with default configuration."""
    print("=== Testing OutputModule with Default Config ===")
    
    # Create default config
    config = OutputModuleConfig()
    print(f"Default no_output: {config.no_output}")
    print(f"Default print_context: {config.print_context}")
    
    # Create module
    output_module = OutputModule("test", config=config)
    
    # Mock data
    agent = MockAgent("test_agent")
    inputs = {"message": "Hello world"}
    context = FlockContext()
    result = {
        "response": "This is a test response with some content",
        "metadata": {"tokens": 150, "latency": 2.5},
        "details": "Additional details here"
    }
    
    # Capture output
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    
    with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
        returned_result = await output_module.on_post_evaluate(
            agent=agent,
            inputs=inputs,
            context=context,
            result=result
        )
    
    stdout_content = captured_stdout.getvalue()
    stderr_content = captured_stderr.getvalue()
    
    print(f"Stdout length: {len(stdout_content)}")
    print(f"Stderr length: {len(stderr_content)}")
    print("Stdout preview (first 300 chars):")
    print(stdout_content[:300] if stdout_content else "None")
    print("\n" + "="*50 + "\n")
    

async def test_output_module_silent():
    """Test OutputModule with no_output=True."""
    print("=== Testing OutputModule with no_output=True ===")
    
    # Create silent config
    config = OutputModuleConfig(no_output=True)
    print(f"Silent no_output: {config.no_output}")
    
    # Create module
    output_module = OutputModule("test", config=config)
    
    # Mock data
    agent = MockAgent("test_agent")
    inputs = {"message": "Hello world"}
    context = FlockContext()
    result = {
        "response": "This should be silent",
        "metadata": {"tokens": 100, "latency": 1.0}
    }
    
    # Capture output
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    
    with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
        returned_result = await output_module.on_post_evaluate(
            agent=agent,
            inputs=inputs,
            context=context,
            result=result
        )
    
    stdout_content = captured_stdout.getvalue()
    stderr_content = captured_stderr.getvalue()
    
    print(f"Silent stdout length: {len(stdout_content)} (should be 0)")
    print(f"Silent stderr length: {len(stderr_content)}")
    print("Silent stdout content:", repr(stdout_content[:100]) if stdout_content else "None")
    print("\n" + "="*50 + "\n")


async def test_output_module_batch_silent():
    """Test OutputModule with batch silent mode via context."""
    print("=== Testing OutputModule with Batch Silent Mode ===")
    
    # Create default config (no_output=False)
    config = OutputModuleConfig(no_output=False)
    print(f"Config no_output: {config.no_output}")
    
    # Create module
    output_module = OutputModule("test", config=config)
    
    # Mock data with batch silent mode in context
    agent = MockAgent("test_agent")
    inputs = {"message": "Hello world"}
    context = FlockContext()
    context.set_variable(FLOCK_BATCH_SILENT_MODE, True)  # This should suppress output
    result = {
        "response": "This should be silent due to batch mode",
        "metadata": {"tokens": 120, "latency": 1.5}
    }
    
    # Capture output
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    
    with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
        returned_result = await output_module.on_post_evaluate(
            agent=agent,
            inputs=inputs,
            context=context,
            result=result
        )
    
    stdout_content = captured_stdout.getvalue()
    stderr_content = captured_stderr.getvalue()
    
    print(f"Batch silent stdout length: {len(stdout_content)} (should be 0)")
    print(f"Batch silent stderr length: {len(stderr_content)}")
    print("Batch silent stdout content:", repr(stdout_content[:100]) if stdout_content else "None")
    print("\n" + "="*50 + "\n")


async def test_output_module_print_context():
    """Test OutputModule with print_context=True."""
    print("=== Testing OutputModule with print_context=True ===")
    
    # Create config with print_context enabled
    config = OutputModuleConfig(no_output=False, print_context=True)
    print(f"Config no_output: {config.no_output}")
    print(f"Config print_context: {config.print_context}")
    
    # Create module
    output_module = OutputModule("test", config=config)
    
    # Mock data with some context
    agent = MockAgent("test_agent")
    inputs = {"message": "Hello world"}
    context = FlockContext()
    context.set_variable("test_var", "test_value")
    context.set_variable("another_var", {"nested": "data"})
    result = {
        "response": "This should include context",
        "metadata": {"tokens": 80, "latency": 1.2}
    }
    
    # Capture output
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    
    with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
        returned_result = await output_module.on_post_evaluate(
            agent=agent,
            inputs=inputs,
            context=context,
            result=result
        )
    
    stdout_content = captured_stdout.getvalue()
    stderr_content = captured_stderr.getvalue()
    
    print(f"Context stdout length: {len(stdout_content)}")
    print(f"Context stderr length: {len(stderr_content)}")
    print("Context stdout preview (first 500 chars):")
    print(stdout_content[:500] if stdout_content else "None")
    print("\n" + "="*50 + "\n")


async def main():
    """Run all tests."""
    print("Testing Flock OutputModule Behavior\n")
    
    try:
        await test_output_module_default()
        await test_output_module_silent()
        await test_output_module_batch_silent()
        await test_output_module_print_context()
    except Exception as e:
        print(f"Error in tests: {e}")
        import traceback
        traceback.print_exc()
    
    print("=== Tests completed ===")


if __name__ == "__main__":
    asyncio.run(main())