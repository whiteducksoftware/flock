#!/usr/bin/env python
"""A simple interactive theme builder.

Steps:
1. Load theme files from a folder (or pick N random ones).
2. Display each theme’s color palette (colors only).
3. Let the user choose a palette.
4. Generate a number of sample tables using that palette (with randomized non-color settings).
5. Let the user select one sample table and save its configuration to a TOML file.
"""

import pathlib
import random
import re
from typing import Any

import toml
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def resolve_style_string(style_str: str, theme: dict) -> str:
    """Replace tokens of the form "color.<section>.<key>" in style_str with
    the value from theme["colors"][<section>][<key>].
    """
    pattern = r"color\.(\w+)\.(\w+)"

    def repl(match):
        section = match.group(1)
        key = match.group(2)
        try:
            return theme["colors"][section][key]
        except KeyError:
            return match.group(0)

    return re.sub(pattern, repl, style_str)


def generate_default_rich_block(theme: dict | None = None) -> dict[str, Any]:
    """Generate a default [rich] block that includes:
    - Color properties computed from the theme's [colors] blocks.
    - Extra color tokens (so tokens like "color.bright.green" can be used).
    - Non-color table layout properties, randomly chosen.
    """

    def random_background():
        return random.choice(
            [
                f"{normal_black}",
                f"{normal_blue}",
                f"{primary_background}",
                f"{selection_background}",
                f"{cursor_cursor}",
            ]
        )

    if theme is not None:
        bright = theme["colors"].get("bright", {})
        normal = theme["colors"].get("normal", {})
        cursor = theme["colors"].get("cursor", {})
        primary = theme["colors"].get("primary", {})
        selection = theme["colors"].get("selection", {})

        bright_black = bright.get("black", "#000000")
        bright_blue = bright.get("blue", "#96cbfe")
        bright_cyan = bright.get("cyan", "#85befd")
        bright_green = bright.get("green", "#94fa36")
        bright_magenta = bright.get("magenta", "#b9b6fc")
        bright_red = bright.get("red", "#fd5ff1")
        bright_white = bright.get("white", "#e0e0e0")
        bright_yellow = bright.get("yellow", "#f5ffa8")

        normal_black = normal.get("black", "#000000")
        normal_blue = normal.get("blue", "#85befd")
        normal_cyan = normal.get("cyan", "#85befd")
        normal_green = normal.get("green", "#87c38a")
        normal_magenta = normal.get("magenta", "#b9b6fc")
        normal_red = normal.get("red", "#fd5ff1")
        normal_white = normal.get("white", "#e0e0e0")
        normal_yellow = normal.get("yellow", "#ffd7b1")

        cursor_cursor = cursor.get("cursor", "#d0d0d0")
        cursor_text = cursor.get("text", "#151515")

        primary_background = primary.get("background", "#161719")
        primary_foreground = primary.get("foreground", "#c5c8c6")
        selection_background = selection.get("background", "#444444")
        selection_text = selection.get("text", primary_foreground)
    else:
        # Fallback default values.
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

    # Color properties.
    default_color_props = {
        "panel_style": f"on {random_background()}",
        "table_header_style": f"bold {selection_text} on {selection_background}",
        "table_title_style": f"bold {primary_foreground}",
        "table_border_style": bright_blue,
        "panel_border_style": bright_blue,
        "column_output": f"bold {primary_foreground}",
        "column_value": primary_foreground,
    }
    # Extra color tokens.
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
    # Non-color layout properties, randomly chosen.
    default_non_color_props = {
        "table_show_lines": random.choice([True, False]),
        "table_box": random.choice(
            ["ROUNDED", "SIMPLE", "SQUARE", "MINIMAL", "HEAVY", "DOUBLE_EDGE"]
        ),
        "panel_padding": random.choice([[1, 2], [1, 1], [2, 2], [0, 2]]),
        "panel_title_align": random.choice(["left", "center", "right"]),
        "table_row_styles": random.choice(
            [["", "dim"], ["", "italic"], ["", "underline"]]
        ),
    }
    # Extra table layout properties (non-content).
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
        "table_caption": "",
        "table_caption_style": "none",
        "table_title_justify": "center",
        "table_caption_justify": "center",
        "table_highlight": False,
    }
    defaults = {
        **default_color_props,
        **extra_color_props,
        **default_non_color_props,
        **default_extra_table_props,
    }
    return defaults


def load_theme_from_file(filepath: str) -> dict:
    """Load a theme from a TOML file.

    If the file does not contain a [rich] block, one is generated and saved.
    """
    with open(filepath) as f:
        theme = toml.load(f)
    if "rich" not in theme:
        theme["rich"] = generate_default_rich_block(theme)
        with open(filepath, "w") as f:
            toml.dump(theme, f)
    return theme


def get_default_styles(theme: dict | None) -> dict[str, Any]:
    """Build a style mapping from the theme by merging defaults with any overrides
    in the [rich] block. Also resolves any color tokens.
    """
    if theme is None:
        final_styles = generate_default_rich_block(None)
    else:
        defaults = generate_default_rich_block(theme)
        rich_props = theme.get("rich", {})
        final_styles = {
            key: rich_props.get(key, defaults[key]) for key in defaults
        }
    # Ensure tuple for padding properties.
    final_styles["panel_padding"] = tuple(final_styles["panel_padding"])
    if "table_padding" in final_styles:
        final_styles["table_padding"] = tuple(final_styles["table_padding"])
    # Resolve tokens.
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
) -> Any:
    """Recursively creates a Rich renderable.

    - If value is a dict, renders it as a Table.
    - If a list/tuple, renders each item.
    - Otherwise, returns the string representation.
    """
    if styles is None:
        styles = get_default_styles(theme)

    if isinstance(value, dict):
        box_style = (
            getattr(box, styles["table_box"])
            if isinstance(styles["table_box"], str)
            else styles["table_box"]
        )
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
                str(k), create_rich_renderable(v, level + 1, theme, styles)
            )
        return table

    elif isinstance(value, (list, tuple)):
        if all(isinstance(item, dict) for item in value):
            sub_tables = []
            for i, item in enumerate(value):
                sub_tables.append(f"[bold]Item {i + 1}[/bold]")
                sub_tables.append(
                    create_rich_renderable(item, level + 1, theme, styles)
                )
            return Group(*sub_tables)
        else:
            rendered_items = [
                create_rich_renderable(item, level + 1, theme, styles)
                for item in value
            ]
            if all(isinstance(item, str) for item in rendered_items):
                return "\n".join(rendered_items)
            else:
                return Group(*rendered_items)
    else:
        if isinstance(value, str) and "\n" in value:
            return f"\n{value}\n"
        return str(value)


# --- Theme Builder Functions --- #


def load_theme_files(theme_dir: pathlib.Path) -> list[pathlib.Path]:
    """Return a list of .toml theme files in the given directory."""
    return list(theme_dir.glob("*.toml"))


def display_color_palette(theme: dict) -> None:
    """Display the color palette from a theme's [colors] sections with a color preview."""
    console = Console()
    palette_table = Table(
        title="Color Palette", show_header=True, header_style="bold"
    )
    palette_table.add_column("Section", style="bold")
    palette_table.add_column("Key", style="italic")
    palette_table.add_column("Value", style="bold")
    palette_table.add_column("Preview", justify="center")

    # Iterate over the colors in each section.
    for section, colors in theme.get("colors", {}).items():
        for key, value in colors.items():
            # Create a Text object with a fixed-width string (here, six spaces)
            # styled with a background color of the actual color value.
            preview = Text("      ", style=f"on {value}")
            palette_table.add_row(section, key, value, preview)

    console.print(palette_table)


def generate_sample_rich_blocks(
    chosen_theme: dict, count: int
) -> list[dict[str, Any]]:
    """Generate a list of sample rich blocks (randomized layout) using the chosen theme's colors."""
    samples = []
    for _ in range(count):
        samples.append(generate_default_rich_block(chosen_theme))
    return samples


def generate_sample_table(sample_theme: dict, dummy_data: dict) -> Panel:
    """Generate a sample table using the given theme dictionary (which includes a [rich] block)
    and some dummy data.
    """
    # Here we use our create_rich_renderable to build a table for dummy_data.
    # For simplicity, we create our own panel.
    styles = get_default_styles(sample_theme)
    # Build a basic table (using our earlier functions)
    table = create_rich_renderable(
        dummy_data, theme=sample_theme, styles=styles
    )
    return Panel(
        table,
        title="Sample Table",
        title_align=styles["panel_title_align"],
        border_style=styles["panel_border_style"],
        padding=styles["panel_padding"],
        style=styles["panel_style"],
    )


def save_theme(theme: dict, filename: pathlib.Path) -> None:
    """Save the given theme dictionary to the specified TOML file."""
    with open(filename, "w") as f:
        toml.dump(theme, f)


# --- Main Interactive Loop --- #


def theme_builder():
    console = Console(force_terminal=True, color_system="truecolor")
    themes_dir = pathlib.Path(__file__).parent.parent.parent.parent / "themes"
    theme_files = load_theme_files(themes_dir)

    if not theme_files:
        console.print("[red]No theme files found in the themes folder.[/red]")
        return

    # Ask the user: load all themes or N random themes?
    console.print("[bold]Theme Builder[/bold]")
    choice = console.input(
        "Load [bold](a)ll[/bold] themes or [bold](n)[/bold] random ones? (a/n): "
    )
    if choice.lower() == "n":
        n = console.input("How many random themes? ")
        try:
            n = int(n)
        except ValueError:
            n = len(theme_files)
        theme_files = random.sample(theme_files, min(n, len(theme_files)))

    # Display palettes for each theme file.
    console.print("\n[underline]Available Color Palettes:[/underline]")
    palettes = []
    for idx, tf in enumerate(theme_files):
        theme_dict = load_theme_from_file(str(tf))
        palettes.append((tf, theme_dict))
        console.print(f"\n[bold]Theme #{idx} - {tf.name}[/bold]")
        display_color_palette(theme_dict)

    # Let the user choose a palette by index.
    sel = console.input("\nEnter the number of the palette to use: ")
    try:
        sel = int(sel)
        chosen_theme = palettes[sel][1]
    except (ValueError, IndexError):
        console.print("[red]Invalid selection. Exiting.[/red]")
        return

    console.print("\n[underline]Selected Palette:[/underline]")
    display_color_palette(chosen_theme)

    # Ask the user how many sample tables to generate.
    count = console.input("\nHow many sample tables to generate? (default 3): ")
    try:
        count = int(count)
    except ValueError:
        count = 3

    # Generate sample rich blocks from the chosen theme.
    sample_rich_blocks = generate_sample_rich_blocks(chosen_theme, count)

    # For each sample, create a new theme dict that uses the chosen palette and the sample rich block.
    dummy_data = {
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

    samples = []
    for i, rich_block in enumerate(sample_rich_blocks):
        # Build a sample theme: copy the chosen theme and override its [rich] block.
        sample_theme = dict(
            chosen_theme
        )  # shallow copy (good enough if colors remain unchanged)
        sample_theme["rich"] = rich_block
        sample_table = generate_sample_table(sample_theme, dummy_data)
        samples.append((sample_theme, sample_table))
        console.print(f"\n[bold]Sample Table #{i}[/bold]")
        console.print(sample_table)

    # Let the user choose one sample or regenerate.
    sel2 = console.input(
        "\nEnter the number of the sample table you like, or type [bold]r[/bold] to regenerate: "
    )
    if sel2.lower() == "r":
        console.print("Regenerating samples...")
        theme_builder()  # restart the builder
        return
    try:
        sel2 = int(sel2)
        chosen_sample_theme = samples[sel2][0]
    except (ValueError, IndexError):
        console.print("[red]Invalid selection. Exiting.[/red]")
        return

    # Ask for file name to save the chosen theme.
    filename = console.input(
        "\nEnter a filename to save the chosen theme (e.g. mytheme.toml): "
    )
    save_path = themes_dir / filename
    save_theme(chosen_sample_theme, save_path)
    console.print(f"\n[green]Theme saved as {save_path}.[/green]")
