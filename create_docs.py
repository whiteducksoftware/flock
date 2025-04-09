from pathlib import Path
from typing import Any

import yaml  # <--- Keep standard import

# --- Configuration ---
MKDOCS_YAML_PATH = "mkdocs.yml"
DOCS_DIR = Path("docs")
PLACEHOLDER_CONTENT = """---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# {title}

*Documentation in progress...*
"""
# --- End Configuration ---


def create_markdown_file(file_path: Path, title: str) -> None:
    """Creates a markdown file with a title and placeholder content."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = PLACEHOLDER_CONTENT.format(title=title)
    if not file_path.exists():
        try:
            file_path.write_text(content, encoding="utf-8")
            print(f"Created: {file_path}")
        except OSError as e:
            print(f"Error creating file {file_path}: {e}")
    else:
        print(f"Skipped (already exists): {file_path}")


def process_nav_item(item: Any, base_dir: Path) -> None:
    """Recursively processes items from the MkDocs nav structure."""
    if isinstance(item, str):
        if ":" in item:
            title, path_str = item.split(":", 1)
            title = title.strip()
            path_str = path_str.strip()
        else:
            path_str = item.strip()
            title = (
                Path(path_str).stem.replace("-", " ").replace("_", " ").title()
            )
            if Path(path_str).name == "index.md":
                parent_name = Path(path_str).parent.name
                if parent_name and parent_name != ".":
                    title = (
                        parent_name.replace("-", " ").replace("_", " ").title()
                        + " Overview"
                    )
                else:
                    title = "Home"

        if path_str.endswith(".md"):
            file_path = base_dir / path_str
            create_markdown_file(file_path, title)

    elif isinstance(item, dict):
        for key, value in item.items():
            if isinstance(value, str) and value.endswith(".md"):
                file_path = base_dir / value
                create_markdown_file(file_path, key)
            elif isinstance(value, list):
                for sub_item in value:
                    process_nav_item(sub_item, base_dir)
            else:
                print(
                    f"Warning: Unexpected value type in nav for key '{key}': {type(value)}"
                )

    elif isinstance(item, list):
        for sub_item in item:
            process_nav_item(sub_item, base_dir)

    else:
        print(f"Warning: Unexpected item type in nav: {type(item)}")


def main():
    """Loads mkdocs.yml, parses the nav structure, and creates placeholder files."""
    DOCS_DIR.mkdir(exist_ok=True)

    try:
        with open(MKDOCS_YAML_PATH, encoding="utf-8") as f:
            # --- CHANGE HERE: Use yaml.Loader instead of yaml.safe_load ---
            config = yaml.load(f, Loader=yaml.Loader)
            # --- END CHANGE ---
    except FileNotFoundError:
        print(f"Error: {MKDOCS_YAML_PATH} not found.")
        return
    except yaml.YAMLError as e:
        print(f"Error parsing {MKDOCS_YAML_PATH}: {e}")
        return

    nav_structure = config.get("nav")
    if not nav_structure or not isinstance(nav_structure, list):
        print("Error: 'nav' structure not found or invalid in mkdocs.yml.")
        return

    print(f"Processing navigation structure from {MKDOCS_YAML_PATH}...")
    for item in nav_structure:
        process_nav_item(item, DOCS_DIR)

    # --- Create essential assets directory and placeholder files ---
    assets_dir = DOCS_DIR / "assets" / "images"
    assets_dir.mkdir(parents=True, exist_ok=True)
    placeholder_logo = assets_dir / "flock_logo_small.png"
    placeholder_favicon = assets_dir / "favicon.png"
    if not placeholder_logo.exists():
        placeholder_logo.touch()
        print(f"Created placeholder: {placeholder_logo}")
    if not placeholder_favicon.exists():
        placeholder_favicon.touch()
        print(f"Created placeholder: {placeholder_favicon}")

    css_dir = DOCS_DIR / "stylesheets"
    css_dir.mkdir(exist_ok=True)
    placeholder_css = css_dir / "extra.css"
    if not placeholder_css.exists():
        placeholder_css.touch()
        print(f"Created placeholder: {placeholder_css}")
    # --- End assets creation ---

    print("\nBoilerplate documentation structure created.")
    print(
        f"You can now start filling in the content in the '{DOCS_DIR}' directory."
    )
    print("Run 'mkdocs serve' to view the documentation locally.")


if __name__ == "__main__":
    main()
