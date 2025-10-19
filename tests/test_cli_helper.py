"""Tests for the CLI helper module."""

import sys
from unittest.mock import MagicMock, patch


class TestVersionHandling:
    """Test version detection and handling."""

    def test_version_from_package(self):
        """Test that version is loaded from package metadata."""
        # We can't easily reload the module to test the try block,
        # so we test that the version was successfully loaded
        import flock.utils.cli_helper

        # The version should be loaded from the package
        assert hasattr(flock.utils.cli_helper, "__version__")
        # It should be a string
        assert isinstance(flock.utils.cli_helper.__version__, str)
        # It should match semantic versioning pattern
        import re

        assert re.match(r"^\d+\.\d+\.\d+", flock.utils.cli_helper.__version__)

    def test_version_fallback_on_package_not_found(self):
        """Test fallback version when package is not installed."""
        # Test the exception handling by patching at import time
        import sys

        # Remove the module from cache to force reload
        if "flock.utils.cli_helper" in sys.modules:
            del sys.modules["flock.utils.cli_helper"]

        with patch("importlib.metadata.version") as mock_version:
            from importlib.metadata import PackageNotFoundError

            mock_version.side_effect = PackageNotFoundError("flock-flow")

            # Now import the module - this will trigger the exception
            import flock.utils.cli_helper

            # Should have fallen back to default version
            assert flock.utils.cli_helper.__version__ == "0.5.0b"


class TestDisplayHummingbird:
    """Test the display_hummingbird function."""

    def test_display_hummingbird_prints_output(self, capsys):
        """Test that display_hummingbird prints the expected content."""
        from flock.utils.cli_helper import display_hummingbird

        display_hummingbird()
        captured = capsys.readouterr()

        # Check that output contains ANSI escape codes (the bird is colored)
        assert "\033[" in captured.out
        # Check that output contains the bird pattern (the blocks)
        assert "▀" in captured.out
        # Check that it's multi-line
        assert "\n" in captured.out


class TestInitConsole:
    """Test the init_console function."""

    @patch("rich.console.Console")
    def test_init_console_default_params(self, mock_console_class):
        """Test init_console with default parameters."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console()

        # Verify console was created
        mock_console_class.assert_called_once()
        # Verify clear was called (default clear_screen=True)
        mock_console.clear.assert_called_once()
        # Verify banner was printed (default show_banner=True)
        assert mock_console.print.call_count >= 2  # Banner and attribution

    @patch("rich.console.Console")
    def test_init_console_no_clear_screen(self, mock_console_class):
        """Test init_console with clear_screen=False."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(clear_screen=False)

        # Verify clear was not called
        mock_console.clear.assert_not_called()
        # Verify banner was still printed
        assert mock_console.print.call_count >= 2

    @patch("rich.console.Console")
    def test_init_console_no_banner(self, mock_console_class):
        """Test init_console with show_banner=False."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(show_banner=False)

        # Verify clear was called
        mock_console.clear.assert_called_once()
        # Verify banner was not printed
        mock_console.print.assert_not_called()

    @patch("rich.console.Console")
    def test_init_console_with_model(self, mock_console_class):
        """Test init_console with a model parameter."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(model="gpt-4")

        # Verify console was created
        mock_console_class.assert_called_once()
        # Verify model info was printed
        print_calls = mock_console.print.call_args_list
        model_printed = any("gpt-4" in str(call) for call in print_calls)
        assert model_printed, f"Model not found in print calls: {print_calls}"

    @patch("rich.console.Console")
    def test_init_console_all_false_with_model(self, mock_console_class):
        """Test init_console with all flags False but with model."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(clear_screen=False, show_banner=False, model="claude-3")

        # Verify clear was not called
        mock_console.clear.assert_not_called()
        # Only model should be printed
        assert mock_console.print.call_count == 1
        print_call = str(mock_console.print.call_args_list[0])
        assert "claude-3" in print_call

    @patch("rich.console.Console")
    @patch("flock.utils.cli_helper.__version__", "test-version")
    def test_init_console_version_in_banner(self, mock_console_class):
        """Test that version is included in the banner."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console()

        # Check that version was included in banner
        print_calls = str(mock_console.print.call_args_list)
        assert "test-version" in print_calls

    @patch("rich.console.Console")
    def test_init_console_banner_content(self, mock_console_class):
        """Test that banner contains expected elements."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console()

        print_calls = str(mock_console.print.call_args_list)
        # Check for duck emojis
        assert "🦆" in print_calls
        assert "🐓" in print_calls
        assert "🐤" in print_calls
        assert "🐧" in print_calls
        # Check for FLOCK text
        assert "▒█" in print_calls
        # Check for company info
        assert "white duck GmbH" in print_calls
        assert "https://whiteduck.de" in print_calls


class TestDisplayBannerNoVersion:
    """Test the display_banner_no_version function."""

    @patch("rich.console.Console")
    def test_display_banner_no_version_basic(self, mock_console_class):
        """Test that display_banner_no_version prints expected content."""
        from flock.utils.cli_helper import display_banner_no_version

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        display_banner_no_version()

        # Verify console was created
        mock_console_class.assert_called_once()
        # Verify banner was printed (should be 2 print calls)
        assert mock_console.print.call_count == 2

    @patch("rich.console.Console")
    def test_display_banner_no_version_content(self, mock_console_class):
        """Test content of display_banner_no_version."""
        from flock.utils.cli_helper import display_banner_no_version

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        display_banner_no_version()

        print_calls = str(mock_console.print.call_args_list)
        # Check for duck emojis
        assert "🦆" in print_calls
        assert "🐓" in print_calls
        assert "🐤" in print_calls
        assert "🐧" in print_calls
        # Check for FLOCK text
        assert "▒█" in print_calls
        # Check for company info
        assert "white duck GmbH" in print_calls
        assert "https://whiteduck.de" in print_calls
        # Ensure no version is included (unlike init_console)
        # We can't check for absence of version directly, but we know
        # it shouldn't reference __version__ in the banner text

    @patch("rich.console.Console")
    def test_display_banner_no_version_no_clear(self, mock_console_class):
        """Test that display_banner_no_version doesn't clear screen."""
        from flock.utils.cli_helper import display_banner_no_version

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        display_banner_no_version()

        # Verify clear was NOT called (unlike init_console)
        mock_console.clear.assert_not_called()

    @patch("rich.console.Console")
    def test_display_banner_no_version_text_styling(self, mock_console_class):
        """Test that banner text has proper styling."""
        from flock.utils.cli_helper import display_banner_no_version

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        display_banner_no_version()

        # Get the first print call (banner text)
        first_call = mock_console.print.call_args_list[0]
        text_arg = first_call[0][0]  # First positional argument

        # Check that it's a Text object with styling
        from rich.text import Text

        assert isinstance(text_arg, Text)
        assert text_arg.justify == "center"
        assert text_arg.style == "bold orange3"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("rich.console.Console")
    def test_init_console_empty_model_string(self, mock_console_class):
        """Test init_console with empty model string."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(model="")

        # With empty model string, model line should not be printed
        print_calls = str(mock_console.print.call_args_list)
        # Should only have banner and attribution, not model line
        assert mock_console.print.call_count == 2

    @patch("rich.console.Console")
    def test_multiple_console_creations(self, mock_console_class):
        """Test that each function creates its own console instance."""
        from flock.utils.cli_helper import display_banner_no_version, init_console

        mock_console1 = MagicMock()
        mock_console2 = MagicMock()
        mock_console_class.side_effect = [mock_console1, mock_console2]

        init_console(show_banner=False)
        display_banner_no_version()

        # Verify two separate console instances were created
        assert mock_console_class.call_count == 2
        # First console should have clear called
        mock_console1.clear.assert_called_once()
        # Second console should not have clear called
        mock_console2.clear.assert_not_called()


class TestImportBehavior:
    """Test module import behavior."""

    def test_module_imports_successfully(self):
        """Test that the module can be imported without errors."""
        import importlib

        import flock.utils.cli_helper

        # Force reload to ensure fresh import
        importlib.reload(flock.utils.cli_helper)

        # Check that all expected functions are available
        assert hasattr(flock.utils.cli_helper, "display_hummingbird")
        assert hasattr(flock.utils.cli_helper, "init_console")
        assert hasattr(flock.utils.cli_helper, "display_banner_no_version")
        assert hasattr(flock.utils.cli_helper, "__version__")

    def test_rich_imports_lazy(self):
        """Test that Rich modules are imported lazily within functions."""
        # This is important for performance - Rich shouldn't be imported
        # at module level, only when functions are called

        # Remove Rich from sys.modules to simulate fresh import
        rich_modules = [m for m in sys.modules.keys() if m.startswith("rich")]
        for module in rich_modules:
            del sys.modules[module]

        # Import our module
        import importlib

        import flock.utils.cli_helper

        importlib.reload(flock.utils.cli_helper)

        # Rich shouldn't be imported yet
        assert "rich.console" not in sys.modules
        assert "rich.syntax" not in sys.modules

        # Now call a function that uses Rich
        with patch("rich.console.Console"):
            flock.utils.cli_helper.init_console(show_banner=False)

        # Now Rich should be imported
        assert "rich.console" in sys.modules
