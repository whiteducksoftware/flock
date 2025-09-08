#!/usr/bin/env python3
"""Direct test of output module config and default behavior."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_output_config_defaults():
    """Test OutputModuleConfig defaults directly."""
    print("=== Testing OutputModuleConfig Defaults ===")
    
    try:
        # Direct import of just the config
        from pydantic import BaseModel, Field
        from flock.core.flock_module import FlockModuleConfig
        from flock.core.logging.formatters.themes import OutputTheme
        
        # Mock the config class
        class OutputModuleConfig(FlockModuleConfig):
            """Configuration for output formatting and display."""

            theme: OutputTheme = Field(
                default=OutputTheme.afterglow, description="Theme for output formatting"
            )
            render_table: bool = Field(
                default=False, description="Whether to render output as a table"
            )
            max_length: int = Field(
                default=1000, description="Maximum length for displayed output"
            )
            truncate_long_values: bool = Field(
                default=True, description="Whether to truncate long values in display"
            )
            show_metadata: bool = Field(
                default=True, description="Whether to show metadata like timestamps"
            )
            format_code_blocks: bool = Field(
                default=True,
                description="Whether to apply syntax highlighting to code blocks",
            )
            custom_formatters: dict[str, str] = Field(
                default_factory=dict,
                description="Custom formatters for specific output types",
            )
            no_output: bool = Field(
                default=False,  # THIS IS THE KEY DEFAULT!
                description="Whether to suppress output",
            )
            print_context: bool = Field(
                default=False,  # THIS TOO!
                description="Whether to print the context",
            )

        # Create default instance
        config = OutputModuleConfig()
        
        print(f"Default no_output: {config.no_output}")
        print(f"Default print_context: {config.print_context}")
        print(f"Default render_table: {config.render_table}")
        print(f"Default show_metadata: {config.show_metadata}")
        print(f"Default max_length: {config.max_length}")
        print(f"Default theme: {config.theme}")
        
        # Test explicit settings
        silent_config = OutputModuleConfig(no_output=True)
        verbose_config = OutputModuleConfig(print_context=True, render_table=True)
        
        print(f"Explicit silent no_output: {silent_config.no_output}")
        print(f"Explicit verbose print_context: {verbose_config.print_context}")
        print(f"Explicit verbose render_table: {verbose_config.render_table}")
        
    except ImportError as e:
        print(f"Import error (expected): {e}")
        print("This shows the dependencies are complex, but we can see the pattern")


def analyze_problem():
    """Analyze the output verbosity problem."""
    print("\n=== Problem Analysis ===")
    print("Current defaults:")
    print("- no_output = False  # Means output is ON by default")
    print("- print_context = False  # Context not printed by default")
    print("- render_table = False  # Simple format by default")
    print("- show_metadata = True  # Metadata shown by default")
    print()
    print("Issues identified:")
    print("1. no_output=False means every agent run produces console output by default")
    print("2. This becomes verbose in batch processing and programmatic use")
    print("3. Users need to explicitly set no_output=True for quieter operation")
    print("4. The default should probably be less verbose for programmatic contexts")
    print()
    print("Proposed solutions:")
    print("1. Keep current defaults but improve batch handling")
    print("2. Change factory defaults to be less verbose")
    print("3. Add context-aware default behavior")


def examine_factory_defaults():
    """Look at how FlockFactory sets defaults."""
    print("\n=== Factory Default Analysis ===")
    print("From the code inspection:")
    print("FlockFactory.create_default_agent() parameters:")
    print("- no_output: bool = False  # Default is verbose")
    print("- print_context: bool = False")
    print("- enable_rich_tables: bool = False")
    print()
    print("This means:")
    print("- Every agent created via factory will output to console by default")
    print("- Users must explicitly set no_output=True for quieter agents")
    print("- Batch operations rely on silent_mode to suppress individual outputs")


def suggest_changes():
    """Suggest minimal changes to address the issue."""
    print("\n=== Suggested Minimal Changes ===")
    print("1. Keep current OutputModuleConfig defaults unchanged (for backward compatibility)")
    print("2. Modify FlockFactory.create_default_agent() to be smarter about context:")
    print("   - Keep no_output=False for single agent runs") 
    print("   - Consider environment variables for default behavior")
    print("3. Ensure batch operations properly respect silent_mode")
    print("4. Add programmatic context detection")
    print("5. Improve documentation about output control")
    print()
    print("Key files to modify:")
    print("- src/flock/core/flock_factory.py (factory defaults)")
    print("- src/flock/modules/output/output_module.py (ensure consistent behavior)")
    print("- src/flock/core/execution/batch_executor.py (batch handling)")


if __name__ == "__main__":
    test_output_config_defaults()
    analyze_problem()
    examine_factory_defaults() 
    suggest_changes()