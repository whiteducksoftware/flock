#!/usr/bin/env python3
import os
import re
import yaml  # pip install pyyaml if needed

def extract_docstring(file_path):
    """
    Extracts the initial triple-quoted docstring from the file.
    Returns a tuple: (title, description) or (None, None) if not found.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Look for a triple-quoted docstring at the very beginning.
    match = re.search(r'^\s*"""(.*?)"""', content, re.DOTALL)
    if match:
        docstring = match.group(1).strip()
        # Split the docstring by lines.
        lines = docstring.splitlines()
        title = ""
        description = ""
        if lines:
            # If the first line starts with "Title:", use that.
            if lines[0].startswith("Title:"):
                title = lines[0][len("Title:"):].strip()
                description = "\n".join(lines[1:]).strip()
            else:
                # Fallback: use the first line as title.
                title = lines[0].strip()
                description = "\n".join(lines[1:]).strip()
        return title, description
    return None, None

def build_nav_items(dir_path, base_dir):
    """
    Recursively builds a list of nav items based on the folder structure.
    Each Python file is read to extract its docstring title and then converted
    to a nav entry pointing to the corresponding markdown file (with .md extension).
    """
    nav_items = []
    
    # List the directory entries and sort them for predictable order.
    entries = sorted(os.listdir(dir_path))
    # Optionally, skip directories that you don't want in the nav.
    entries = [entry for entry in entries if entry not in ['__pycache__']]
    
    # Process subdirectories first.
    for entry in entries:
        full_path = os.path.join(dir_path, entry)
        if os.path.isdir(full_path):
            # Recursively build nav items for subdirectories.
            sub_nav = build_nav_items(full_path, base_dir)
            if sub_nav:
                # Use the directory name as the group title.
                nav_items.append({ entry: sub_nav })
    
    # Process .py files.
    for entry in entries:
        full_path = os.path.join(dir_path, entry)
        if os.path.isfile(full_path) and entry.endswith('.py'):
            title, _ = extract_docstring(full_path)
            if not title or title == None or title == "":
                print(f"Skipped because no matching docstring found! {full_path}")
                continue
            # Compute the markdown file path (preserve relative structure, change .py to .md).
            rel_path = os.path.relpath(full_path, base_dir)
            md_path = os.path.splitext(rel_path)[0] + ".md"
            # Ensure the path uses forward slashes.
            nav_items.append({ title: md_path.replace(os.sep, "/") })
    
    return nav_items

def update_mkdocs_nav(nav_items, mkdocs_path='mkdocs.yml'):
    """
    Loads the existing mkdocs.yaml file, updates (or adds) the top-level "examples"
    node in the nav section with the new nav_items, and writes it back.
    """
    # Load the current mkdocs.yaml content.
    with open(mkdocs_path, 'r', encoding='utf-8') as f:
        mkdocs_config = yaml.safe_load(f)
    if mkdocs_config is None:
        mkdocs_config = {}
    
    # Get the current nav list or create a new one if missing.
    nav = mkdocs_config.get('nav', [])
    if not isinstance(nav, list):
        nav = []
    
    # Search for an "examples" node in the nav list.
    examples_found = False
    for item in nav:
        if isinstance(item, dict) and 'examples' in item:
            # Update the "examples" node with our new navigation items.
            item['examples'] = nav_items
            examples_found = True
            break

    # If no "examples" node was found, append one.
    if not examples_found:
        nav.append({'examples': nav_items})
    
    # Update the nav key in the configuration.
    mkdocs_config['nav'] = nav
    
    # Write the updated configuration back to mkdocs.yaml.
    with open(mkdocs_path, 'w', encoding='utf-8') as f:
        yaml.dump(mkdocs_config, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    
    print(f"mkdocs.yaml updated with the new examples navigation.")

def main():
    base_dir = "examples"
    if not os.path.isdir(base_dir):
        print(f"Error: '{base_dir}' folder not found.")
        return
    
    # Build the navigation items from the examples folder.
    nav_items = build_nav_items(base_dir, ".")
    # Update the mkdocs.yaml file.
    update_mkdocs_nav(nav_items)

if __name__ == "__main__":
    main()
