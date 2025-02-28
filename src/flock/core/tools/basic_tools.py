"""This module contains basic agentic tools for performing various tasks."""

import importlib
import os
import re
from typing import Literal

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
def get_web_content_as_markdown(url: str):
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
    import json

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
    try:
        with open(filename) as f:
            content = f.read()
        return content
    except Exception:
        raise
