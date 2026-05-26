
import importlib
import os
from typing import Literal

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
            "Optional tool dependencies not installed. Install with 'pip install flock-mcp[all]'."
        )


@traced_and_logged
def web_search_duckduckgo(
    keywords: str, search_type: Literal["news", "web"] = "web"
):
    try:
        if importlib.util.find_spec("ddgs") is not None:
            from ddgs import DDGS

            if search_type == "news":
                response = DDGS().news(keywords)
            else:
                response = DDGS().text(keywords)

                return response
        else:
            raise ImportError(
                "Optional tool dependencies not installed. Install with 'pip install flock-mcp[all]'."
            )
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

@traced_and_logged
def web_content_as_markdown(url: str) -> str:
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
            "Optional tool dependencies not installed. Install with 'pip install flock-mcp[all]'."
        )


