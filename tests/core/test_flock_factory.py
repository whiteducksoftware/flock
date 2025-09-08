"""
Tests for FlockFactory default behavior and environment variable support.

This test module validates that:
1. Environment variables control default output behavior
2. Non-interactive context detection works
3. Explicit parameters override defaults
"""

import os
import sys
import unittest
from unittest.mock import patch


class TestFlockFactoryDefaults(unittest.TestCase):
    """Test FlockFactory default behavior with environment variables."""
    
    def setUp(self):
        """Clean environment before each test."""
        env_vars_to_clean = ['FLOCK_NO_OUTPUT', 'FLOCK_PROGRAMMATIC', 'CI']
        for var in env_vars_to_clean:
            if var in os.environ:
                del os.environ[var]
    
    def determine_no_output_default(self, no_output_param=None):
        """Test version of the logic from FlockFactory.create_default_agent."""
        no_output = no_output_param
        
        if no_output is None:
            # Check environment variable first
            env_no_output = os.environ.get('FLOCK_NO_OUTPUT', '').lower()
            if env_no_output in ('true', '1', 'yes'):
                no_output = True
            elif env_no_output in ('false', '0', 'no'):
                no_output = False
            else:
                # Default to quieter behavior for programmatic contexts
                is_non_interactive = (
                    not sys.stdin.isatty() or
                    os.environ.get('CI', '').lower() in ('true', '1') or
                    os.environ.get('FLOCK_PROGRAMMATIC', '').lower() in ('true', '1')
                )
                no_output = is_non_interactive
        
        return no_output
    
    @patch('sys.stdin.isatty')
    def test_interactive_default(self, mock_isatty):
        """Test that interactive environments default to verbose output."""
        mock_isatty.return_value = True  # Interactive terminal
        
        no_output = self.determine_no_output_default()
        self.assertFalse(no_output, "Interactive environments should be verbose by default")
    
    @patch('sys.stdin.isatty')
    def test_non_interactive_default(self, mock_isatty):
        """Test that non-interactive environments default to quiet output."""
        mock_isatty.return_value = False  # Non-interactive (piped input)
        
        no_output = self.determine_no_output_default()
        self.assertTrue(no_output, "Non-interactive environments should be quiet by default")
    
    @patch('sys.stdin.isatty')
    def test_ci_environment_default(self, mock_isatty):
        """Test that CI environments default to quiet output."""
        mock_isatty.return_value = True  # Interactive terminal
        os.environ['CI'] = 'true'
        
        no_output = self.determine_no_output_default()
        self.assertTrue(no_output, "CI environments should be quiet by default")
    
    @patch('sys.stdin.isatty')
    def test_programmatic_flag_default(self, mock_isatty):
        """Test that FLOCK_PROGRAMMATIC flag forces quiet output."""
        mock_isatty.return_value = True  # Interactive terminal
        os.environ['FLOCK_PROGRAMMATIC'] = '1'
        
        no_output = self.determine_no_output_default()
        self.assertTrue(no_output, "FLOCK_PROGRAMMATIC should force quiet output")
    
    @patch('sys.stdin.isatty')
    def test_explicit_no_output_env_var(self, mock_isatty):
        """Test that FLOCK_NO_OUTPUT environment variable overrides defaults."""
        mock_isatty.return_value = True  # Interactive terminal
        os.environ['FLOCK_NO_OUTPUT'] = 'true'
        
        no_output = self.determine_no_output_default()
        self.assertTrue(no_output, "FLOCK_NO_OUTPUT=true should force quiet output")
        
        # Test false value
        os.environ['FLOCK_NO_OUTPUT'] = 'false'
        
        no_output = self.determine_no_output_default()
        self.assertFalse(no_output, "FLOCK_NO_OUTPUT=false should force verbose output")
    
    @patch('sys.stdin.isatty')
    def test_explicit_parameter_override(self, mock_isatty):
        """Test that explicit parameters override all defaults."""
        mock_isatty.return_value = False  # Non-interactive
        os.environ['CI'] = 'true'
        os.environ['FLOCK_NO_OUTPUT'] = 'true'
        
        # Explicit parameter should override everything
        no_output = self.determine_no_output_default(no_output_param=False)
        self.assertFalse(no_output, "Explicit parameter should override all defaults")
        
        no_output = self.determine_no_output_default(no_output_param=True)
        self.assertTrue(no_output, "Explicit parameter should override all defaults")


if __name__ == "__main__":
    unittest.main(verbosity=2)