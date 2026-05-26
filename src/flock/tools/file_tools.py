import importlib
import json
from typing import Any

from flock.core.logging.trace_and_logged import traced_and_logged


@traced_and_logged
def file_get_anything_as_markdown(url_or_file_path: str):
    if importlib.util.find_spec("docling") is not None:
        from docling.document_converter import DocumentConverter

        try:
            converter = DocumentConverter()
            result = converter.convert(url_or_file_path)
            markdown = result.document.export_to_markdown()
            return markdown
        except Exception:
            raise
    else:
        raise ImportError(
            "Optional tool dependencies not installed. Install with 'pip install flock-core[file-tools]'."
        )


@traced_and_logged
def file_append_to_file(content: str, filename: str):
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        raise


@traced_and_logged
def file_save_to_file(content: str, filename: str):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        raise


@traced_and_logged
def file_read_from_file(filename: str) -> str:
    with open(filename, encoding="utf-8") as file:
        return file.read()


@traced_and_logged
def file_json_parse_safe(text: str) -> dict:
    try:
        result = json.loads(text)
        return result
    except Exception:
        return {}


@traced_and_logged
def file_json_search(
    json_file_path: str, search_query: str, case_sensitive: bool = False
) -> list:
    """Search a JSON file for objects containing the specified search query.

    Args:
        json_file_path (str): Path to the JSON file to search
        search_query (str): Text to search for within the JSON objects
        case_sensitive (bool, optional): Whether to perform a case-sensitive search. Defaults to False.

    Returns:
        list: List of JSON objects (as dicts) that contain the search query

    Example:
        >>> matching_tickets = file_json_search("tickets.json", "error 404")
        >>> print(
        ...     f"Found {len(matching_tickets)} tickets mentioning '404 error'"
        ... )
    """
    try:
        # Read the JSON file
        file_content = file_read_from_file(json_file_path)

        # Parse the JSON content
        json_data = file_json_parse_safe(file_content)

        # Convert search query to lowercase if case-insensitive search
        if not case_sensitive:
            search_query = search_query.lower()

        results = []

        # Determine if the JSON root is an object or array
        if isinstance(json_data, dict):
            # Handle case where root is a dictionary object
            for key, value in json_data.items():
                if isinstance(value, list):
                    # If this key contains a list of objects, search within them
                    matching_items = _search_in_list(
                        value, search_query, case_sensitive
                    )
                    results.extend(matching_items)
                elif _contains_text(value, search_query, case_sensitive):
                    # The entire object matches
                    results.append(json_data)
                    break
        elif isinstance(json_data, list):
            # Handle case where root is an array
            matching_items = _search_in_list(
                json_data, search_query, case_sensitive
            )
            results.extend(matching_items)

        return results

    except Exception as e:
        return [{"error": f"Error searching JSON file: {e!s}"}]


def _search_in_list(
    items: list, search_query: str, case_sensitive: bool
) -> list:
    """Helper function to search for text in a list of items."""
    matching_items = []
    for item in items:
        if _contains_text(item, search_query, case_sensitive):
            matching_items.append(item)
    return matching_items


def _contains_text(obj: Any, search_query: str, case_sensitive: bool) -> bool:
    """Recursively check if an object contains the search query in any of its string values."""
    if isinstance(obj, str):
        # For string values, check if they contain the search query
        if case_sensitive:
            return search_query in obj
        else:
            return search_query in obj.lower()
    elif isinstance(obj, dict):
        # For dictionaries, check each value
        for value in obj.values():
            if _contains_text(value, search_query, case_sensitive):
                return True
    elif isinstance(obj, list):
        # For lists, check each item
        for item in obj:
            if _contains_text(item, search_query, case_sensitive):
                return True
    # For other types (numbers, booleans, None), return False
    return False
