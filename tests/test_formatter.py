# tests/test_themes.py

import pathlib
import pytest
from rich.panel import Panel
from rich.console import Console

from flock.core.logging.formatters.themed_formatter import ThemedAgentResultFormatter, load_theme_from_file

def get_theme_files() -> list[pathlib.Path]:
    """
    Returns a list of all TOML theme files in src/flock/themes.
    """
    themes_dir = pathlib.Path(__file__).parent.parent / "src" / "flock" / "themes"
    return list(themes_dir.glob("*.toml"))

@pytest.mark.parametrize("theme_file", get_theme_files())
def test_generate_table_with_theme(theme_file: pathlib.Path, capsys):

    theme = load_theme_from_file(str(theme_file))
    
    test_result = {
        "Agent": "Test Agent",
        "Status": "Running",
        "Metrics": {
            "CPU": "20%",
            "Memory": "512MB",
            "Nested": {"value1": 1, "value2": 2},
        },
        "Logs": [
            "Initialization complete",
            "Running process...",
            {"Step": "Completed", "Time": "2025-02-07T12:00:00Z"},
        ],
    }
    
    panel = ThemedAgentResultFormatter.format_result(test_result, "Test Agent", theme=theme)
    
    # Assert that the formatter returns a Panel instance.
    assert isinstance(panel, Panel)
    console = Console(force_terminal=True, color_system="truecolor")
    with capsys.disabled():
        console.print(panel)
