"""Tests for the CLI helper module."""

import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


@contextmanager
def _fresh_rich_imports():
    """Drop rich from sys.modules for the block, then restore the originals.

    Without the restore, rich modules imported during the block replace the
    originals for the rest of the run, and two copies of rich's classes coexist.
    """
    saved = {
        name: module for name, module in sys.modules.items() if name.startswith("rich")
    }
    for name in saved:
        del sys.modules[name]
    try:
        yield
    finally:
        for name in [name for name in sys.modules if name.startswith("rich")]:
            del sys.modules[name]
        sys.modules.update(saved)


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


def _printed(mock_console: MagicMock) -> str:
    """Everything a mocked console printed, as plain text."""
    from rich.text import Text

    return "".join(
        call.args[0].plain if isinstance(call.args[0], Text) else str(call.args[0])
        for call in mock_console.print.call_args_list
    )


class TestInitConsole:
    """Test the init_console function."""

    @patch("rich.console.Console")
    def test_init_console_default_params(self, mock_console_class):
        """The screen is cleared and the banner printed in one go."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console()

        mock_console_class.assert_called_once()
        mock_console.clear.assert_called_once()
        assert mock_console.print.call_count == 1

    @patch("rich.console.Console")
    def test_init_console_no_clear_screen(self, mock_console_class):
        """Test init_console with clear_screen=False."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(clear_screen=False)

        mock_console.clear.assert_not_called()
        assert mock_console.print.call_count == 1

    @patch("rich.console.Console")
    def test_init_console_no_banner(self, mock_console_class):
        """Test init_console with show_banner=False."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(show_banner=False)

        mock_console.clear.assert_called_once()
        mock_console.print.assert_not_called()

    @patch("rich.console.Console")
    def test_init_console_with_model(self, mock_console_class):
        """The banner names the model."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(model="gpt-4")

        assert "model: gpt-4" in _printed(mock_console)

    @patch("rich.console.Console")
    def test_init_console_all_false_with_model(self, mock_console_class):
        """Without the banner, only the model is printed."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(clear_screen=False, show_banner=False, model="claude-3")

        mock_console.clear.assert_not_called()
        assert mock_console.print.call_count == 1
        assert "claude-3" in _printed(mock_console)

    @patch("rich.console.Console")
    @patch("flock.utils.cli_helper.__version__", "test-version")
    def test_init_console_version_in_banner(self, mock_console_class):
        """The banner names the version and the milestone."""
        from flock.utils.cli_helper import MILESTONE, init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console()

        assert f"vtest-version · {MILESTONE}" in _printed(mock_console)

    @patch("rich.console.Console")
    def test_init_console_banner_content(self, mock_console_class):
        """A formation shaped like a prompt (>) in front of the wordmark."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console()

        lines = _printed(mock_console).splitlines()
        assert [line.index("⌄") for line in lines[:7]] == [2, 4, 6, 8, 6, 4, 2]
        assert lines[3].endswith("█▀▀ █   █▀█ █▀▀ █▄▀")
        assert "blackboard-first agent orchestration" in lines[5]
        assert "🦆 white duck GmbH · https://whiteduck.de" in lines[6]


class TestDisplayBannerNoVersion:
    """Test the display_banner_no_version function."""

    @patch("rich.console.Console")
    @patch("flock.utils.cli_helper.__version__", "test-version")
    def test_display_banner_no_version_content(self, mock_console_class):
        """The same banner, with the milestone and without the version."""
        from flock.utils.cli_helper import MILESTONE, display_banner_no_version

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        display_banner_no_version()

        printed = _printed(mock_console)
        assert mock_console.print.call_count == 1
        assert "█▀  █▄▄ █▄█ █▄▄ █ █" in printed
        assert MILESTONE in printed
        assert "test-version" not in printed
        assert "🦆 white duck GmbH" in printed

    @patch("rich.console.Console")
    def test_display_banner_no_version_no_clear(self, mock_console_class):
        """Test that display_banner_no_version doesn't clear screen."""
        from flock.utils.cli_helper import display_banner_no_version

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        display_banner_no_version()

        mock_console.clear.assert_not_called()


class TestDisplayAbout:
    """The milestone's bird (flock-flow --about)."""

    def test_about_shows_the_kingfisher_and_what_it_stands_for(self, capsys):
        from flock.utils.cli_helper import MILESTONE, __version__, display_about

        display_about()

        out = capsys.readouterr().out
        assert MILESTONE == "Kingfisher"
        assert f"flock-core {__version__}" in out
        assert '"Kingfisher" milestone' in out
        assert "UNSURE" in out
        assert "▀" in out  # the sprite
        assert "white duck GmbH" in out

    def test_the_kingfisher_is_drawn_in_half_blocks(self):
        from flock.utils.cli_helper import _KINGFISHER, kingfisher

        drawn = kingfisher().plain.splitlines()

        assert len(drawn) == (len(_KINGFISHER) + 1) // 2  # two pixels a line
        assert {len(line) for line in drawn} == {max(map(len, _KINGFISHER))}


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("rich.console.Console")
    def test_init_console_empty_model_string(self, mock_console_class):
        """Test init_console with empty model string."""
        from flock.utils.cli_helper import init_console

        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        init_console(model="")

        # With an empty model string, the banner names no model
        assert mock_console.print.call_count == 1
        assert "model:" not in _printed(mock_console)

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
        import importlib

        import flock.utils.cli_helper

        with _fresh_rich_imports():  # simulate a fresh import, restore afterwards
            importlib.reload(flock.utils.cli_helper)

            # Rich shouldn't be imported yet
            assert "rich.console" not in sys.modules
            assert "rich.syntax" not in sys.modules

            # Now call a function that uses Rich
            with patch("rich.console.Console"):
                flock.utils.cli_helper.init_console(show_banner=False)

            # Now Rich should be imported
            assert "rich.console" in sys.modules


def test_lazy_import_check_leaves_rich_intact():
    """test_rich_imports_lazy drops rich from sys.modules; it must restore the
    original modules, or two copies of rich's classes coexist and rich's own
    isinstance checks fail in later tests (Text.assemble then crashes panels)."""
    import rich.text  # noqa: F401 - make sure it is loaded

    before = sys.modules["rich.text"]

    TestImportBehavior().test_rich_imports_lazy()

    assert sys.modules["rich.text"] is before
