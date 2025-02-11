"""This module contains basic agentic tools for performing various tasks."""

import importlib
import os

from flock.core.logging.trace_and_logged import traced_and_logged


@traced_and_logged
def web_search_tavily(query: str):
    """Performs a web search using the Tavily client.

    This function checks if the optional 'tavily' dependency is installed. If so,
    it creates a TavilyClient using the API key from the environment variable
    'TAVILY_API_KEY' and performs a search with the provided query. The search response
    is returned if successful.

    Parameters:
        query (str): The search query string.

    Returns:
        Any: The search response obtained from the Tavily client.

    Raises:
        ImportError: If the 'tavily' dependency is not installed.
        Exception: Re-raises any exceptions encountered during the search.
    """
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
def get_web_content_as_markdown(url: str):
    """Fetches web content from a URL and converts it to Markdown.

    This function uses the 'httpx' library to retrieve the content of the provided URL.
    It then converts the HTML content into Markdown using the 'markdownify' library.

    Parameters:
        url (str): The URL of the web page to fetch.

    Returns:
        str: The web page content converted into Markdown format.

    Raises:
        ImportError: If either 'httpx' or 'markdownify' dependencies are not installed.
        Exception: Re-raises any exceptions encountered during the HTTP request or conversion.
    """
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
    """Converts the content of a URL or file into Markdown format.

    This function leverages the 'docling' library to convert various document types
    (retrieved from a URL or a local file) into Markdown. It uses the DocumentConverter
    from the 'docling.document_converter' module.

    Parameters:
        url_or_file_path (str): The URL or local file path of the document to convert.

    Returns:
        str: The converted document in Markdown format.

    Raises:
        ImportError: If the 'docling' dependency is not installed.
        Exception: Re-raises any exceptions encountered during the document conversion.
    """
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
    """Evaluates a mathematical expression using the dspy interpreter.

    This function uses the 'dspy' library's PythonInterpreter to evaluate the provided
    mathematical expression.

    Parameters:
        expression (str): A string containing the mathematical expression to evaluate.

    Returns:
        float: The result of the evaluated expression.

    Raises:
        Exception: Re-raises any exceptions encountered during the evaluation.
    """
    import dspy

    try:
        result = dspy.PythonInterpreter({}).execute(expression)
        return result
    except Exception:
        raise


@traced_and_logged
def code_eval(python_code: str) -> float:
    """Executes Python code using the dspy interpreter.

    This function takes a string of Python code, executes it using the 'dspy' PythonInterpreter,
    and returns the result.

    Parameters:
        python_code (str): A string containing Python code to execute.

    Returns:
        float: The result of the executed code.

    Raises:
        Exception: Re-raises any exceptions encountered during code execution.
    """
    import dspy

    try:
        result = dspy.PythonInterpreter({}).execute(python_code)
        return result
    except Exception:
        raise


@traced_and_logged
def get_current_time() -> str:
    """Retrieves the current time in ISO 8601 format.

    Returns:
        str: The current date and time as an ISO 8601 formatted string.
    """
    import datetime

    time = datetime.datetime.now().isoformat()
    return time


@traced_and_logged
def count_words(text: str) -> int:
    """Counts the number of words in the provided text.

    This function splits the input text by whitespace and returns the count of resulting words.

    Parameters:
        text (str): The text in which to count words.

    Returns:
        int: The number of words in the text.
    """
    count = len(text.split())
    return count


@traced_and_logged
def extract_urls(text: str) -> list[str]:
    """Extracts all URLs from the given text.

    This function uses a regular expression to find all substrings that match the typical
    URL pattern (starting with http or https).

    Parameters:
        text (str): The text from which to extract URLs.

    Returns:
        list[str]: A list of URLs found in the text.
    """
    import re

    url_pattern = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"
    urls = re.findall(url_pattern, text)
    return urls


@traced_and_logged
def extract_numbers(text: str) -> list[float]:
    """Extracts all numerical values from the provided text.

    This function uses a regular expression to find substrings that represent integers or decimals,
    converts them to floats, and returns them as a list.

    Parameters:
        text (str): The text from which to extract numerical values.

    Returns:
        list[float]: A list of numbers (as floats) found in the text.
    """
    import re

    numbers = [float(x) for x in re.findall(r"-?\d*\.?\d+", text)]
    return numbers


@traced_and_logged
def json_parse_safe(text: str) -> dict:
    """Safely parses a JSON string into a dictionary.

    This function attempts to load a JSON object from the given text. If parsing fails,
    it returns an empty dictionary instead of raising an exception.

    Parameters:
        text (str): The JSON-formatted string to parse.

    Returns:
        dict: The parsed JSON object as a dictionary, or an empty dictionary if parsing fails.
    """
    import json

    try:
        result = json.loads(text)
        return result
    except Exception:
        return {}


@traced_and_logged
def save_to_file(content: str, filename: str):
    """Saves the given content to a file.

    This function writes the provided content to a file specified by the filename.
    If the file cannot be written, an exception is raised.

    Parameters:
        content (str): The content to be saved.
        filename (str): The path to the file where the content will be saved.

    Raises:
        Exception: Re-raises any exceptions encountered during the file write operation.
    """
    try:
        with open(filename, "w") as f:
            f.write(content)
    except Exception:
        raise


@traced_and_logged
def read_from_file(filename: str) -> str:
    """Reads and returns the content of a file.

    This function opens the specified file, reads its content, and returns it as a string.
    If the file cannot be read, an exception is raised.

    Parameters:
        filename (str): The path to the file to be read.

    Returns:
        str: The content of the file.

    Raises:
        Exception: Re-raises any exceptions encountered during the file read operation.
    """
    try:
        with open(filename) as f:
            content = f.read()
        return content
    except Exception:
        raise
