"""A Rich-based formatter for agent results with theme support."""

import pathlib
import random
import re
from typing import Any

from temporalio import workflow

from flock.core.logging.formatters.themes import OutputTheme

with workflow.unsafe.imports_passed_through():
    from pygments.style import Style
    from pygments.token import Token
    from rich import box
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.syntax import PygmentsSyntaxTheme, Syntax
    from rich.table import Table
    from rich.theme import Theme

import toml  # install with: pip install toml


def resolve_style_string(style_str: str, theme: dict) -> str:
    """Replace tokens in a style string of the form.

        color.<section>.<key>

    with the corresponding value from theme["colors"][<section>][<key>].
    If the token cannot be resolved, it is left unchanged.
    """
    pattern = r"color\.(\w+)\.(\w+)"

    def repl(match):
        section = match.group(1)
        key = match.group(2)
        try:
            return theme["colors"][section][key]
        except KeyError:
            return match.group(0)  # leave token unchanged if not found

    return re.sub(pattern, repl, style_str)


def generate_default_rich_block(theme: dict | None = None) -> dict[str, Any]:
    """Generate a default [rich] block with *all* styling properties.

    For the color mapping properties the defaults are computed from the
    theme's [colors] blocks (if available). This includes colors from the
    "bright", "normal", and "cursor" sections.

    Non color properties (layout and table specific properties) are randomly
    chosen from a set of sensible alternatives.
    """
    if theme is not None:
        # Retrieve colors from the theme.
        bright_black = theme["colors"]["bright"].get("black", "#000000")
        bright_blue = theme["colors"]["bright"].get("blue", "#96cbfe")
        bright_cyan = theme["colors"]["bright"].get("cyan", "#85befd")
        bright_green = theme["colors"]["bright"].get("green", "#94fa36")
        bright_magenta = theme["colors"]["bright"].get("magenta", "#b9b6fc")
        bright_red = theme["colors"]["bright"].get("red", "#fd5ff1")
        bright_white = theme["colors"]["bright"].get("white", "#e0e0e0")
        bright_yellow = theme["colors"]["bright"].get("yellow", "#f5ffa8")

        normal_black = theme["colors"]["normal"].get("black", "#000000")
        normal_blue = theme["colors"]["normal"].get("blue", "#85befd")
        normal_cyan = theme["colors"]["normal"].get("cyan", "#85befd")
        normal_green = theme["colors"]["normal"].get("green", "#87c38a")
        normal_magenta = theme["colors"]["normal"].get("magenta", "#b9b6fc")
        normal_red = theme["colors"]["normal"].get("red", "#fd5ff1")
        normal_white = theme["colors"]["normal"].get("white", "#e0e0e0")
        normal_yellow = theme["colors"]["normal"].get("yellow", "#ffd7b1")

        cursor_cursor = theme["colors"]["cursor"].get("cursor", "#d0d0d0")
        cursor_text = theme["colors"]["cursor"].get("text", "#151515")

        primary_background = theme["colors"]["primary"].get(
            "background", "#161719"
        )
        primary_foreground = theme["colors"]["primary"].get(
            "foreground", "#c5c8c6"
        )
        selection_background = theme["colors"]["selection"].get(
            "background", "#444444"
        )
        selection_text = theme["colors"]["selection"].get(
            "text", primary_foreground
        )
    else:
        bright_black = "black"
        bright_blue = "blue"
        bright_cyan = "cyan"
        bright_green = "green"
        bright_magenta = "magenta"
        bright_red = "red"
        bright_white = "white"
        bright_yellow = "yellow"

        normal_black = "black"
        normal_blue = "blue"
        normal_cyan = "cyan"
        normal_green = "green"
        normal_magenta = "magenta"
        normal_red = "red"
        normal_white = "white"
        normal_yellow = "yellow"

        cursor_cursor = "gray"
        cursor_text = "white"

        primary_background = "black"
        primary_foreground = "white"
        selection_background = "gray"
        selection_text = "white"

    # Color properties computed from the theme.
    default_color_props = {
        "panel_style": f"on {primary_background}",
        "table_header_style": f"bold {selection_text} on {selection_background}",
        "table_title_style": f"bold {primary_foreground}",
        "table_border_style": bright_blue,
        "panel_border_style": bright_blue,
        "column_output": f"bold {primary_foreground}",
        "column_value": primary_foreground,
    }
    # Extra color tokens so they can be used via tokens like color.bright.black, etc.
    extra_color_props = {
        "bright_black": bright_black,
        "bright_blue": bright_blue,
        "bright_cyan": bright_cyan,
        "bright_green": bright_green,
        "bright_magenta": bright_magenta,
        "bright_red": bright_red,
        "bright_white": bright_white,
        "bright_yellow": bright_yellow,
        "normal_black": normal_black,
        "normal_blue": normal_blue,
        "normal_cyan": normal_cyan,
        "normal_green": normal_green,
        "normal_magenta": normal_magenta,
        "normal_red": normal_red,
        "normal_white": normal_white,
        "normal_yellow": normal_yellow,
        "cursor_cursor": cursor_cursor,
        "cursor_text": cursor_text,
    }
    # Randomly choose non color properties.
    default_non_color_props = {
        "table_show_lines": random.choice([True, False]),
        "table_box": random.choice(
            ["ROUNDED", "SIMPLE", "SQUARE", "MINIMAL", "HEAVY", "DOUBLE_EDGE"]
        ),
        "panel_padding": random.choice([[1, 2], [1, 1], [2, 2], [0, 2]]),
        "panel_title_align": random.choice(["left", "center", "right"]),
        # Add table_row_styles property.
        "table_row_styles": random.choice(
            [["", "dim"], ["", "italic"], ["", "underline"]]
        ),
    }
    # Extra table layout properties (non content properties).
    default_extra_table_props = {
        "table_safe_box": True,
        "table_padding": [0, 1],
        "table_collapse_padding": False,
        "table_pad_edge": True,
        "table_expand": False,
        "table_show_footer": False,
        "table_show_edge": True,
        "table_leading": 0,
        "table_style": "none",
        "table_footer_style": "none",
        "table_caption": None,
        "table_caption_style": "none",
        "table_title_justify": "center",
        "table_caption_justify": "center",
        "table_highlight": False,
    }
    # Combine all defaults.
    defaults = {
        **default_color_props,
        **extra_color_props,
        **default_non_color_props,
        **default_extra_table_props,
    }
    return defaults


def load_theme_from_file(filepath: str) -> dict:
    """Load a theme from a TOML file.

    The theme is expected to contain color blocks like [colors.primary],
    [colors.selection], [colors.normal], [colors.cursor], etc.
    If the file does not contain a [rich] block for styling properties,
    one is generated (with all properties including color mappings) and
    written back into the file.
    """
    with open(filepath) as f:
        theme = toml.load(f)

    if "rich" not in theme:
        theme["rich"] = generate_default_rich_block(theme)
        # Write the updated theme back into the file.
        with open(filepath, "w") as f:
            toml.dump(theme, f)

    return theme


def get_default_styles(theme: dict | None) -> dict[str, Any]:
    """Build a style mapping from the theme.

    It first computes defaults from the [colors] block (via generate_default_rich_block)
    and then overrides any property found in the [rich] block.
    Finally, for every property that is a string, tokens of the form
    "color.<section>.<key>" are resolved.
    """
    if theme is None:
        final_styles = generate_default_rich_block(None)
    else:
        defaults = generate_default_rich_block(theme)
        rich_props = theme.get("rich", {})
        final_styles = {
            key: rich_props.get(key, defaults[key]) for key in defaults
        }

    # Ensure that panel_padding and table_padding are tuples.
    final_styles["panel_padding"] = tuple(final_styles["panel_padding"])
    if "table_padding" in final_styles:
        final_styles["table_padding"] = tuple(final_styles["table_padding"])

    # Resolve tokens in every string value.
    if theme is not None:
        for key, value in final_styles.items():
            if isinstance(value, str):
                final_styles[key] = resolve_style_string(value, theme)

    return final_styles


def create_rich_renderable(
    value: Any,
    level: int = 0,
    theme: dict | None = None,
    styles: dict[str, Any] | None = None,
    max_length: int = -1,
) -> Any:
    """Recursively creates a Rich renderable for a given value.

    - For dicts: creates a Table with headers styled via the computed properties.
    - For lists/tuples: if every item is a dict, returns a Group of subtables;
      otherwise, renders each item recursively.
    - Other types: returns a string (adding extra newlines for multi-line strings).
    """
    if styles is None:
        styles = get_default_styles(theme)

    # If the value is a dictionary, render it as a table.
    if isinstance(value, dict):
        # Convert table_box string into an actual box style.
        box_style = (
            getattr(box, styles["table_box"])
            if isinstance(styles["table_box"], str)
            else styles["table_box"]
        )
        # Gather all table-related keyword arguments.
        table_kwargs = {
            "show_header": True,
            "header_style": styles["table_header_style"],
            "title": f"Subtable (Level {level})" if level > 0 else None,
            "title_style": styles["table_title_style"],
            "border_style": styles["table_border_style"],
            "show_lines": styles["table_show_lines"],
            "box": box_style,
            "row_styles": styles["table_row_styles"],
            "safe_box": styles.get("table_safe_box"),
            "padding": styles.get("table_padding"),
            "collapse_padding": styles.get("table_collapse_padding"),
            "pad_edge": styles.get("table_pad_edge"),
            "expand": styles.get("table_expand"),
            "show_footer": styles.get("table_show_footer"),
            "show_edge": styles.get("table_show_edge"),
            "leading": styles.get("table_leading"),
            "style": styles.get("table_style"),
            "footer_style": styles.get("table_footer_style"),
            "caption": styles.get("table_caption"),
            "caption_style": styles.get("table_caption_style"),
            "title_justify": styles.get("table_title_justify"),
            "caption_justify": styles.get("table_caption_justify"),
            "highlight": styles.get("table_highlight"),
        }
        table = Table(**table_kwargs)
        table.add_column("Key", style=styles["column_output"])
        table.add_column("Value", style=styles["column_value"])
        for k, v in value.items():
            table.add_row(
                str(k),
                create_rich_renderable(v, level + 1, theme, styles, max_length),
            )
        return table

    # If the value is a list or tuple, render each item.
    elif isinstance(value, list | tuple):
        if all(isinstance(item, dict) for item in value):
            sub_tables = []
            for i, item in enumerate(value):
                sub_tables.append(f"[bold]Item {i + 1}[/bold]")
                sub_tables.append(
                    create_rich_renderable(
                        item, level + 1, theme, styles, max_length=max_length
                    )
                )
            return Group(*sub_tables)
        else:
            rendered_items = [
                create_rich_renderable(
                    item, level + 1, theme, styles, max_length=max_length
                )
                for item in value
            ]
            if all(isinstance(item, str) for item in rendered_items):
                return "\n".join(rendered_items)
            else:
                return Group(*rendered_items)

    # Otherwise, return a string representation.
    else:
        s = str(value).strip()
        if max_length > 0 and len(s) > max_length:
            omitted = len(s) - max_length
            s = (
                s[:max_length]
                + f"[bold bright_yellow]...(+{omitted}chars)[/bold bright_yellow]"
            )
        if isinstance(value, str) and "\n" in value:
            return f"\n{s}\n"
        return s


def load_syntax_theme_from_file(filepath: str) -> dict:
    """Load a syntax highlighting theme from a TOML file and map it to Rich styles."""
    with open(filepath) as f:
        theme = toml.load(f)

    if "colors" not in theme:
        raise ValueError(
            f"Theme file {filepath} does not contain a 'colors' section."
        )

    # Map theme colors to syntax categories
    syntax_theme = {
        "background": theme["colors"]["primary"].get("background", "#161719"),
        "text": theme["colors"]["primary"].get("foreground", "#c5c8c6"),
        "comment": theme["colors"]["normal"].get("black", "#666666"),
        "keyword": theme["colors"]["bright"].get("magenta", "#ff79c6"),
        "builtin": theme["colors"]["bright"].get("cyan", "#8be9fd"),
        "string": theme["colors"]["bright"].get("green", "#50fa7b"),
        "name": theme["colors"]["bright"].get("blue", "#6272a4"),
        "number": theme["colors"]["bright"].get("yellow", "#f1fa8c"),
        "operator": theme["colors"]["bright"].get("red", "#ff5555"),
        "punctuation": theme["colors"]["normal"].get("white", "#bbbbbb"),
        "error": theme["colors"]["bright"].get("red", "#ff5555"),
    }

    return syntax_theme


def create_rich_syntax_theme(syntax_theme: dict) -> Theme:
    """Convert a syntax theme dict to a Rich-compatible Theme."""
    return Theme(
        {
            "background": f"on {syntax_theme['background']}",
            "text": syntax_theme["text"],
            "keyword": f"bold {syntax_theme['keyword']}",
            "builtin": f"bold {syntax_theme['builtin']}",
            "string": syntax_theme["string"],
            "name": syntax_theme["name"],
            "number": syntax_theme["number"],
            "operator": syntax_theme["operator"],
            "punctuation": syntax_theme["punctuation"],
            "error": f"bold {syntax_theme['error']}",
        }
    )


def create_pygments_syntax_theme(syntax_theme: dict) -> PygmentsSyntaxTheme:
    """Convert a syntax theme dict to a Pygments-compatible Rich syntax theme."""

    class CustomSyntaxStyle(Style):
        """Dynamically generated Pygments style based on the loaded theme."""

        background_color = syntax_theme["background"]
        styles = {
            Token.Text: syntax_theme["text"],
            Token.Comment: f"italic {syntax_theme['comment']}",
            Token.Keyword: f"bold {syntax_theme['keyword']}",
            Token.Name.Builtin: f"bold {syntax_theme['builtin']}",
            Token.String: syntax_theme["string"],
            Token.Name: syntax_theme["name"],
            Token.Number: syntax_theme["number"],
            Token.Operator: syntax_theme["operator"],
            Token.Punctuation: syntax_theme["punctuation"],
            Token.Error: f"bold {syntax_theme['error']}",
        }

    return PygmentsSyntaxTheme(CustomSyntaxStyle)


class ThemedAgentResultFormatter:
    """Formats agent results in a Rich table with nested subtables and theme support."""

    def __init__(
        self,
        theme: OutputTheme = OutputTheme.afterglow,
        max_length: int = -1,
        render_table: bool = True,
    ):
        """Initialize the formatter with a theme and optional max length."""
        self.theme = theme
        self.styles = None
        self.max_length = max_length
        self.render_table = render_table

    def format_result(
        self,
        result: dict[str, Any],
        agent_name: str,
        theme,
        styles,
    ) -> Panel:
        from devtools import pformat

        """Format an agent's result as a Rich Panel containing a table."""
        box_style = (
            getattr(box, styles["table_box"])
            if isinstance(styles["table_box"], str)
            else styles["table_box"]
        )

        # Gather table properties for the main table.
        table_kwargs = {
            "show_header": True,
            "header_style": styles["table_header_style"],
            "title": f"Agent Results: {agent_name}",
            "title_style": styles["table_title_style"],
            "border_style": styles["table_border_style"],
            "show_lines": styles["table_show_lines"],
            "box": box_style,
            "row_styles": styles["table_row_styles"],
            "safe_box": styles.get("table_safe_box"),
            "padding": styles.get("table_padding"),
            "collapse_padding": styles.get("table_collapse_padding"),
            "pad_edge": styles.get("table_pad_edge"),
            "expand": styles.get("table_expand"),
            "show_footer": styles.get("table_show_footer"),
            "show_edge": styles.get("table_show_edge"),
            "leading": styles.get("table_leading"),
            "style": styles.get("table_style"),
            "footer_style": styles.get("table_footer_style"),
            "caption": styles.get("table_caption"),
            "caption_style": styles.get("table_caption_style"),
            "title_justify": styles.get("table_title_justify"),
            "caption_justify": styles.get("table_caption_justify"),
            "highlight": styles.get("table_highlight"),
        }

        table = Table(**table_kwargs)
        table.add_column("Output", style=styles["column_output"])
        table.add_column("Value", style=styles["column_value"])
        for key, value in result.items():
            rich_renderable = create_rich_renderable(
                value,
                level=0,
                theme=theme,
                styles=styles,
                max_length=self.max_length,
            )
            table.add_row(key, rich_renderable)

        s = pformat(result, highlight=False)

        if self.render_table:
            return Panel(
                table,
                title="🐤🐧🐓🦆",
                title_align=styles["panel_title_align"],
                border_style=styles["panel_border_style"],
                padding=styles["panel_padding"],
                style=styles["panel_style"],
            )
        else:
            syntax = Syntax(
                s,  # The formatted string
                "python",  # Highlight as Python (change this for other formats)
                theme=self.syntax_style,  # Choose a Rich theme (matches your color setup)
                line_numbers=False,
            )
            return Panel(
                syntax,
                title=agent_name,
                title_align=styles["panel_title_align"],
                border_style=styles["panel_border_style"],
                padding=styles["panel_padding"],
                style=styles["panel_style"],
            )

    def display_result(self, result: dict[str, Any], agent_name: str) -> None:
        """Print an agent's result using Rich formatting."""
        theme = self.theme
        themes_dir = (
            pathlib.Path(__file__).parent.parent.parent.parent / "themes"
        )
        all_themes = list(themes_dir.glob("*.toml"))
        theme = (
            theme.value + ".toml"
            if not theme.value.endswith(".toml")
            else theme.value
        )
        theme = (
            pathlib.Path(__file__).parent.parent.parent.parent
            / "themes"
            / theme
        )

        if pathlib.Path(theme) not in all_themes:
            raise ValueError(
                f"Invalid theme: {theme}\nAvailable themes: {all_themes}"
            )

        theme_dict = load_theme_from_file(theme)

        styles = get_default_styles(theme_dict)
        self.styles = styles
        self.syntax_style = create_pygments_syntax_theme(
            load_syntax_theme_from_file(theme)
        )

        console = Console()
        panel = self.format_result(
            result=result,
            agent_name=agent_name,
            theme=theme_dict,
            styles=styles,
        )
        console.print(panel)
