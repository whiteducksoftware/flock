import re
from typing import Any

from flock.core.logging.trace_and_logged import traced_and_logged


@traced_and_logged
def split_markdown_by_headers(
    markdown_text: str, min_header_level: int = 1, max_header_level: int = 2
) -> list[dict[str, Any]]:
    if not markdown_text:
        return []

    # Pattern to match headers from level min_header_level to max_header_level
    header_pattern = re.compile(
        f"^({'#' * min_header_level}){{'1,{max_header_level - min_header_level + 1}'}}\\s+(.+)$",
        re.MULTILINE,
    )

    # Find all headers
    headers = list(header_pattern.finditer(markdown_text))

    if not headers:
        return [{"title": "Text", "content": markdown_text, "level": 0}]

    chunks = []

    # Process each section
    for i in range(len(headers)):
        current_header = headers[i]
        header_text = current_header.group(2).strip()
        header_level = len(current_header.group(1))

        # Determine section content
        if i < len(headers) - 1:
            next_header_start = headers[i + 1].start()
            content = markdown_text[current_header.end() : next_header_start]
        else:
            content = markdown_text[current_header.end() :]

        chunks.append(
            {
                "title": header_text,
                "content": content.strip(),
                "level": header_level,
            }
        )

    # Check if there's content before the first header
    if headers[0].start() > 0:
        preamble = markdown_text[: headers[0].start()].strip()
        if preamble:
            chunks.insert(
                0, {"title": "Preamble", "content": preamble, "level": 0}
            )

    return chunks


@traced_and_logged
def extract_code_blocks(
    markdown_text: str, language: str = None
) -> list[dict[str, str]]:
    if not markdown_text:
        return []

    # Pattern to match markdown code blocks
    if language:
        # Match only code blocks with the specified language
        pattern = rf"```{language}\s*([\s\S]*?)\s*```"
    else:
        # Match all code blocks, capturing the language specifier if present
        pattern = r"```(\w*)\s*([\s\S]*?)\s*```"

    blocks = []

    if language:
        # If language is specified, we only capture the code content
        matches = re.finditer(pattern, markdown_text)
        for match in matches:
            blocks.append(
                {"language": language, "code": match.group(1).strip()}
            )
    else:
        # If no language is specified, we capture both language and code content
        matches = re.finditer(pattern, markdown_text)
        for match in matches:
            lang = match.group(1).strip() if match.group(1) else "text"
            blocks.append({"language": lang, "code": match.group(2).strip()})

    return blocks


@traced_and_logged
def extract_links(markdown_text: str) -> list[dict[str, str]]:
    if not markdown_text:
        return []

    # Pattern to match markdown links [text](url)
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    matches = link_pattern.findall(markdown_text)

    return [{"text": text, "url": url} for text, url in matches]


@traced_and_logged
def extract_tables(markdown_text: str) -> list[dict[str, Any]]:
    if not markdown_text:
        return []

    # Split the text by lines
    lines = markdown_text.split("\n")

    tables = []
    current_table = None
    header_row = None

    for line in lines:
        line = line.strip()

        # Table rows are indicated by starting with |
        if line.startswith("|") and line.endswith("|"):
            if current_table is None:
                current_table = []
                # This is the header row
                header_row = [
                    cell.strip() for cell in line.strip("|").split("|")
                ]
            elif "|--" in line or "|:-" in line:
                # This is the separator row, ignore it
                pass
            else:
                # This is a data row
                row_data = [cell.strip() for cell in line.strip("|").split("|")]

                # Create a dictionary mapping headers to values
                row_dict = {}
                for i, header in enumerate(header_row):
                    if i < len(row_data):
                        row_dict[header] = row_data[i]
                    else:
                        row_dict[header] = ""

                current_table.append(row_dict)
        else:
            # End of table
            if current_table is not None:
                tables.append({"headers": header_row, "rows": current_table})
                current_table = None
                header_row = None

    # Don't forget to add the last table if we're at the end of the document
    if current_table is not None:
        tables.append({"headers": header_row, "rows": current_table})

    return tables


@traced_and_logged
def markdown_to_plain_text(markdown_text: str) -> str:
    if not markdown_text:
        return ""

    # Replace headers
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", markdown_text, flags=re.MULTILINE)

    # Replace bold and italic
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)

    # Replace links
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", text)

    # Replace code blocks
    text = re.sub(r"```(?:\w+)?\s*([\s\S]*?)\s*```", r"\1", text)
    text = re.sub(r"`([^`]*?)`", r"\1", text)

    # Replace bullet points
    text = re.sub(r"^[\*\-\+]\s+(.+)$", r"• \1", text, flags=re.MULTILINE)

    # Replace numbered lists (keeping the numbers)
    text = re.sub(r"^\d+\.\s+(.+)$", r"\1", text, flags=re.MULTILINE)

    # Replace blockquotes
    text = re.sub(r"^>\s+(.+)$", r"\1", text, flags=re.MULTILINE)

    # Remove HTML tags
    text = re.sub(r"<.*?>", "", text)

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
