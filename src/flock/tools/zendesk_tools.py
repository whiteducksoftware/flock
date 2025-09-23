"""Tools for interacting with Zendesk."""

import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ZendeskTools")




def _get_headers() -> dict:
    token = os.getenv("ZENDESK_BEARER_TOKEN")
    if not token:
        raise ValueError(
            "ZENDESK_BEARER_TOKEN environment variable is not set"
        )
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


@mcp.tool()
def zendesk_get_tickets(number_of_tickets: int = 10) -> list[dict]:
    """Get all tickets."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets.json"
    all_tickets = []
    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        while url and len(all_tickets) < number_of_tickets:
            response = client.get(url)
            response.raise_for_status()

            data = response.json()
            tickets = data.get("tickets", [])
            all_tickets.extend(tickets)

            url = data.get("next_page")
    return all_tickets

@mcp.tool()
def zendesk_get_ticket_by_id(ticket_id: str) -> dict:
    """Get a ticket by ID."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}"
    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()["ticket"]

@mcp.tool()
def zendesk_get_comments_by_ticket_id(ticket_id: str) -> list[dict]:
    """Get all comments for a ticket."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}/comments"
    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()["comments"]

@mcp.tool()
def zendesk_get_article_by_id(article_id: str) -> dict:
    """Get an article by ID."""
    ZENDESK_LOCALE = os.getenv("ZENDESK_ARTICLE_LOCALE")
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = (
        f"{BASE_URL}/api/v2/help_center/{ZENDESK_LOCALE}/articles/{article_id}"
    )
    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()["article"]

@mcp.tool()
def zendesk_get_articles() -> list[dict]:
    """Get all articles."""
    ZENDESK_LOCALE = os.getenv("ZENDESK_ARTICLE_LOCALE")
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/help_center/{ZENDESK_LOCALE}/articles.json"
    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()["articles"]

@mcp.tool()
def zendesk_get_articles_count() -> int:
    """Count every Help-Center article in the configured locale.

    Uses cursor pagination (page[size]=100) because it’s faster and
    has no 10 000-record ceiling. Falls back to offset pagination
    if the account hasn’t been migrated yet.
    """
    ZENDESK_LOCALE     = os.getenv("ZENDESK_ARTICLE_LOCALE")  # e.g. "en-us"
    ZENDESK_SUBDOMAIN  = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    BASE_URL           = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url                = (
        f"{BASE_URL}/api/v2/help_center/{ZENDESK_LOCALE}/articles.json"
        "?page[size]=100"            # max page size for HC APIs
    )

    total = 0
    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        while url:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

            total += len(data.get("articles", []))
            print(f"Locale: {ZENDESK_LOCALE}")
            print(f"Number of articles: {total}")

            # Cursor pagination (preferred)
            if data.get("meta", {}).get("has_more"):
                url = data.get("links", {}).get("next")
                continue

            # Offset pagination fallback
            url = data.get("next_page")

    return total

@mcp.tool()
def zendesk_search_articles(query: str) -> list[dict]:
    """Search Zendesk Help Center articles using a query string."""
    ZENDESK_LOCALE = os.getenv("ZENDESK_ARTICLE_LOCALE")  # e.g., "en-us"
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/help_center/articles/search.json"

    params = {
        "query": query,
        "locale": ZENDESK_LOCALE,
        "sort_by": "updated_at",
        "sort_order": "desc",
    }

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json().get("results", [])

@mcp.tool()
def zendesk_add_comment_to_ticket(ticket_id: str, comment_body: str, public: bool = False) -> dict:
    """Add a comment to a Zendesk ticket.

    Updates the ticket with a new comment via Zendesk Ticketing API:
    PUT /api/v2/tickets/{ticket_id}.json
    """
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}.json"

    payload = {
        "ticket": {
            "comment": {
                "body": comment_body,
                "public": public,
            }
        }
    }

    import httpx
    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        response = client.put(url, json=payload)
        response.raise_for_status()
        return response.json()["ticket"]

@mcp.tool()
def zendesk_set_ticket_custom_field(
    ticket_id: str, custom_field_id: int, custom_field_value: str
) -> dict:
    """Set the custom field value of a Zendesk ticket.

    Uses Zendesk's Update Ticket API to set a custom field value:
    PUT /api/v2/tickets/{ticket_id}.json
    """
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}.json"

    payload = {
        "ticket": {
            "custom_fields": [
                {
                    "id": custom_field_id,
                    "value": custom_field_value,
                }
            ]
        }
    }

    import httpx

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        response = client.put(url, json=payload)
        response.raise_for_status()
        return response.json()["ticket"]



@mcp.tool()
def zendesk_set_ticket_tags(ticket_id: str, tags: list[str]) -> list[str]:
    """Set the complete tag list for a ticket (overwrites existing tags)."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}/tags.json"

    payload = {"tags": tags}

    import httpx

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        resp = client.put(url, json=payload)
        resp.raise_for_status()
        return resp.json().get("tags", [])


@mcp.tool()
def zendesk_add_ticket_tags(ticket_id: str, tags: list[str]) -> list[str]:
    """Add tags to a ticket (preserves existing tags)."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}/tags.json"

    payload = {"tags": tags}

    import httpx

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json().get("tags", [])


@mcp.tool()
def zendesk_get_ticket_field_type(field_id: int) -> dict:
    """Return the Zendesk custom field type and options for a field id.

    Uses GET /api/v2/ticket_fields/{field_id}.json.

    Returns a dict containing at least:
    { "type": str, "custom_field_options": list }
    """
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/ticket_fields/{field_id}.json"

    import httpx

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        field = resp.json().get("ticket_field", {})
        return {
            "id": field.get("id"),
            "type": field.get("type"),
            "title": field.get("title"),
            "required": field.get("required"),
            "custom_field_options": field.get("custom_field_options", []),
        }




if __name__ == "__main__":
    transport = os.getenv("ZENDESK_MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
