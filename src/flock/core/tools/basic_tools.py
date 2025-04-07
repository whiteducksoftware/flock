"""This module contains basic agentic tools for performing various tasks."""

import importlib
import json
import os
import re
from typing import Any, Literal

from flock.core.interpreter.python_interpreter import PythonInterpreter
from flock.core.logging.trace_and_logged import traced_and_logged


@traced_and_logged
def web_search_tavily(query: str):
    if importlib.util.find_spec("tavily") is not None:
        from tavily import TavilyClient

        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        try:
            response = client.search(query, include_answer=True)  # type: ignore
            return response
        except Exception:
            raise
    else:
        raise ImportError(
            "Optional tool dependencies not installed. Install with 'pip install flock-core[tools]'."
        )


@traced_and_logged
def web_search_duckduckgo(
    keywords: str, search_type: Literal["news", "web"] = "web"
):
    try:
        from duckduckgo_search import DDGS

        if search_type == "news":
            response = DDGS().news(keywords)
        else:
            response = DDGS().text(keywords)

        return response
    except Exception:
        raise


@traced_and_logged
def web_search_bing(keywords: str):
    try:
        import httpx

        subscription_key = os.environ["BING_SEARCH_V7_SUBSCRIPTION_KEY"]
        endpoint = "https://api.bing.microsoft.com/v7.0/search"

        # Query term(s) to search for.
        query = keywords

        # Construct a request
        mkt = "en-US"
        params = {"q": query, "mkt": mkt}
        headers = {"Ocp-Apim-Subscription-Key": subscription_key}

        response = httpx.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        search_results = response.json()
        return search_results["webPages"]
    except Exception:
        raise


def extract_links_from_markdown(markdown: str, url: str) -> list:
    # Regular expression to find all markdown links
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    links = link_pattern.findall(markdown)
    return [url + link[1] for link in links]


@traced_and_logged
def get_web_content_as_markdown(url: str) -> str:
    if (
        importlib.util.find_spec("httpx") is not None
        and importlib.util.find_spec("markdownify") is not None
    ):
        import httpx
        from markdownify import markdownify as md

        try:
            response = httpx.get(url)
            response.raise_for_status()
            markdown = md(response.text)
            return markdown
        except Exception:
            raise
    else:
        raise ImportError(
            "Optional tool dependencies not installed. Install with 'pip install flock-core[tools]'."
        )


@traced_and_logged
def get_anything_as_markdown(url_or_file_path: str):
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
            "Optional tool dependencies not installed. Install with 'pip install flock-core[all-tools]'."
        )


@traced_and_logged
def evaluate_math(expression: str) -> float:
    try:
        result = PythonInterpreter(
            {},
            [
                "os",
                "math",
                "random",
                "datetime",
                "time",
                "string",
                "collections",
                "itertools",
                "functools",
                "typing",
                "enum",
                "json",
                "ast",
            ],
            verbose=True,
        ).execute(expression)
        return result
    except Exception:
        raise


@traced_and_logged
def code_eval(python_code: str) -> str:
    try:
        result = PythonInterpreter(
            {},
            [
                "os",
                "math",
                "random",
                "datetime",
                "time",
                "string",
                "collections",
                "itertools",
                "functools",
                "typing",
                "enum",
                "json",
                "ast",
            ],
            verbose=True,
        ).execute(python_code)
        return result
    except Exception:
        raise


@traced_and_logged
def get_current_time() -> str:
    import datetime

    time = datetime.datetime.now().isoformat()
    return time


@traced_and_logged
def count_words(text: str) -> int:
    count = len(text.split())
    return count


@traced_and_logged
def extract_urls(text: str) -> list[str]:
    import re

    url_pattern = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"
    urls = re.findall(url_pattern, text)
    return urls


@traced_and_logged
def extract_numbers(text: str) -> list[float]:
    import re

    numbers = [float(x) for x in re.findall(r"-?\d*\.?\d+", text)]
    return numbers


@traced_and_logged
def json_parse_safe(text: str) -> dict:
    try:
        result = json.loads(text)
        return result
    except Exception:
        return {}


@traced_and_logged
def save_to_file(content: str, filename: str):
    try:
        with open(filename, "w") as f:
            f.write(content)
    except Exception:
        raise


@traced_and_logged
def read_from_file(filename: str) -> str:
    with open(filename, encoding="utf-8") as file:
        return file.read()


@traced_and_logged
def json_search(
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
        >>> matching_tickets = json_search("tickets.json", "error 404")
        >>> print(
        ...     f"Found {len(matching_tickets)} tickets mentioning '404 error'"
        ... )
    """
    try:
        # Read the JSON file
        file_content = read_from_file(json_file_path)

        # Parse the JSON content
        json_data = json_parse_safe(file_content)

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
