import os
import re

def extract_docstring(file_path):
    """
    Extract the initial triple-quoted docstring from the file.
    Returns a tuple (title, description, docstring_end_index) where:
      - title: the page title (either from a "Title:" prefix or the first line)
      - description: the remaining lines of the docstring
      - docstring_end_index: the index in the file content where the docstring ends
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Look for a triple-quoted docstring at the very beginning.
    match = re.search(r'^\s*"""(.*?)"""', content, re.DOTALL)
    if match:
        docstring = match.group(1).strip()
        lines = docstring.splitlines()
        title = ""
        description = ""
        if lines:
            if lines[0].startswith("Title:"):
                title = lines[0][len("Title:"):].strip()
                description = "\n".join(lines[1:]).strip()
            else:
                title = lines[0].strip()
                description = "\n".join(lines[1:]).strip()
        return title, description, match.end()
    return None, None, None

def is_separator_line(line):
    """
    Returns True if the given line is a comment separator.
    A separator line is a comment line (starting with '#') whose content (after stripping '#')
    consists solely of three or more dashes or underscores.
    """
    stripped = line.lstrip()
    if not stripped.startswith("#"):
        return False
    content = stripped[1:].strip()  # Remove '#' and extra whitespace.
    return bool(re.fullmatch(r'[-_]{3,}', content))

def split_into_blocks(text):
    """
    Splits the given text (the code after the docstring) into alternating blocks.
    Each block is a tuple (block_type, content) where block_type is either 'comment' or 'code'.
    
    The function:
      - Ignores separator lines (e.g. lines with only dashes).
      - Groups consecutive comment lines together.
      - Groups consecutive non-comment (code) lines together.
      - Treats blank lines as part of the current block.
    """
    lines = text.splitlines()
    blocks = []
    current_type = None
    current_lines = []

    def flush_block():
        nonlocal current_lines, current_type, blocks
        if current_lines:
            blocks.append((current_type, "\n".join(current_lines).rstrip("\n")))
            current_lines = []

    for line in lines:
        if is_separator_line(line):
            # A separator line signals a new block; flush current block and skip the separator.
            flush_block()
            continue

        # Determine if the current line is a comment or code.
        stripped = line.lstrip()
        if stripped.startswith("#"):
            line_type = "comment"
        else:
            line_type = "code"

        # If the line is blank and we haven't started a block, default to code.
        if stripped == "":
            line_type = current_type if current_type is not None else "code"

        # If the type changes, flush the current block.
        if current_type is None:
            current_type = line_type
        elif line_type != current_type:
            flush_block()
            current_type = line_type
        current_lines.append(line)
    flush_block()
    return blocks

def process_comment_block(block):
    """
    Processes a comment block by stripping the leading '#' (and one optional space) from each line.
    Returns the cleaned-up text to be rendered as Markdown.
    """
    processed_lines = []
    for line in block.splitlines():
        if line.lstrip().startswith("#"):
            # Remove the first '#' and one following space if present.
            processed_line = re.sub(r'^\s*#\s?', '', line)
            processed_lines.append(processed_line)
        else:
            processed_lines.append(line)
    return "\n".join(processed_lines).strip()

def generate_markdown(file_path, output_path):
    """
    Reads a Python example file and creates a Markdown file that:
      - Uses the initial docstring for the page header (title and description).
      - Splits the remaining content into alternating comment and code blocks.
      - Renders comment blocks as plain Markdown text and code blocks as fenced code blocks.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    title, description, doc_end = extract_docstring(file_path)
    if not title:
        print(f"Skipped {file_path}: no docstring found")
        return

    # Remove the initial docstring from the content.
    remaining_content = content[doc_end:].lstrip("\n")
    
    # Split the remaining content into blocks.
    blocks = split_into_blocks(remaining_content)
    
    # Build the Markdown output.
    md_parts = []
    md_parts.append(f"# {title}\n")
    if description:
        md_parts.append(f"{description}\n")
    
    for block_type, block_content in blocks:
        if block_type == "comment":
            processed = process_comment_block(block_content)
            if processed:
                md_parts.append(processed + "\n")
        elif block_type == "code":
            if block_content.strip():
                md_parts.append("```python\n" + block_content + "\n```\n")
    
    md_content = "\n".join(md_parts)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"Generated {output_path}")

def main():
    examples_dir = "examples"         # Folder with your Python example files.
    docs_dir = "docs/examples"         # Output folder for the generated Markdown files.
    
    # Walk through the examples directory.
    for root, _, files in os.walk(examples_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                # Compute the file path relative to the examples directory.
                rel_path = os.path.relpath(file_path, examples_dir)
                # Change the extension to .md.
                md_rel_path = os.path.splitext(rel_path)[0] + ".md"
                output_md_path = os.path.join(docs_dir, md_rel_path)
                generate_markdown(file_path, output_md_path)

if __name__ == "__main__":
    main()
