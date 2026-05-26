"""Enum Builder."""

import os
import pathlib
import re

theme_folder = pathlib.Path(__file__).parent.parent.parent.parent / "themes"

if not theme_folder.exists():
    raise FileNotFoundError(f"Theme folder not found: {theme_folder}")

theme_files = [
    pathlib.Path(f.path).stem for f in os.scandir(theme_folder) if f.is_file()
]

theme_enum_entries = {}
for theme in theme_files:
    safe_name = (
        theme.replace("-", "_")
        .replace(" ", "_")
        .replace("(", "_")
        .replace(")", "_")
        .replace("+", "_")
        .replace(".", "_")
    )

    if re.match(r"^\d", safe_name):
        safe_name = f"_{safe_name}"

    theme_enum_entries[safe_name] = theme

with open("theme_enum.py", "w") as f:
    f.write("from enum import Enum\n\n")
    f.write("class OutputOptionsTheme(Enum):\n")
    for safe_name, original_name in theme_enum_entries.items():
        f.write(f'    {safe_name} = "{original_name}"\n')

print("Generated theme_enum.py ✅")
