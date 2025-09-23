"""Tools for interacting with Zendesk."""

import os

import httpx
from mcp.server.fastmcp import FastMCP

from flock.core.logging.logging import get_logger

mcp = FastMCP("ZendeskTools")
logger = get_logger(__name__)

def _get_headers() -> dict:
    logger.debug("Preparing headers for Zendesk API request")

    token = os.getenv("ZENDESK_BEARER_TOKEN")
    if not token:
        logger.error("ZENDESK_BEARER_TOKEN environment variable is not set")
        raise ValueError(
            "ZENDESK_BEARER_TOKEN environment variable is not set"
        )

    logger.debug("Successfully retrieved bearer token from environment")
    # Log a masked version of the token for debugging
    masked_token = f"{token[:10]}...{token[-4:] if len(token) > 14 else 'short'}"
    logger.debug(f"Using bearer token: {masked_token}")
    logger.debug("Headers prepared successfully")

    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


@mcp.tool()
def zendesk_get_tickets(number_of_tickets: int = 10) -> list[dict]:
    """Get all tickets."""
    logger.info(f"Starting zendesk_get_tickets with number_of_tickets: {number_of_tickets}")

    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    logger.debug(f"Using Zendesk subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets.json"
    logger.debug(f"Initial URL: {url}")

    all_tickets = []
    page_count = 0

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        while url and len(all_tickets) < number_of_tickets:
            page_count += 1
            logger.debug(f"Fetching page {page_count} from URL: {url}")

            try:
                response = client.get(url)
                response.raise_for_status()
                logger.debug(f"Successfully received response with status: {response.status_code}")

                data = response.json()
                tickets = data.get("tickets", [])
                logger.debug(f"Retrieved {len(tickets)} tickets from page {page_count}")

                all_tickets.extend(tickets)
                logger.debug(f"Total tickets collected so far: {len(all_tickets)}")

                url = data.get("next_page")
                if url:
                    logger.debug(f"Next page URL: {url}")
                else:
                    logger.debug("No more pages available")

            except Exception as e:
                logger.error(f"Error fetching tickets on page {page_count}: {e}")
                raise

    logger.info(f"Successfully retrieved {len(all_tickets)} tickets across {page_count} pages")
    return all_tickets

@mcp.tool()
def zendesk_get_ticket_by_id(ticket_id: str) -> dict:
    """Get a ticket by ID."""
    logger.info(f"Starting zendesk_get_ticket_by_id for ticket_id: {ticket_id}")

    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    logger.debug(f"Using Zendesk subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}"
    logger.debug(f"Request URL: {url}")

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug(f"Making GET request for ticket {ticket_id}")
            response = client.get(url)
            response.raise_for_status()
            logger.debug(f"Successfully received response with status: {response.status_code}")

            ticket_data = response.json()["ticket"]
            logger.info(f"Successfully retrieved ticket {ticket_id} with subject: {ticket_data.get('subject', 'N/A')}")
            return ticket_data

        except Exception as e:
            logger.error(f"Error fetching ticket {ticket_id}: {e}")
            raise

@mcp.tool()
def zendesk_get_comments_by_ticket_id(ticket_id: str) -> list[dict]:
    """Get all comments for a ticket."""
    logger.info(f"Starting zendesk_get_comments_by_ticket_id for ticket_id: {ticket_id}")

    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    logger.debug(f"Using Zendesk subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}/comments"
    logger.debug(f"Request URL: {url}")

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug(f"Making GET request for comments of ticket {ticket_id}")
            response = client.get(url)
            response.raise_for_status()
            logger.debug(f"Successfully received response with status: {response.status_code}")

            comments = response.json()["comments"]
            logger.info(f"Successfully retrieved {len(comments)} comments for ticket {ticket_id}")
            return comments

        except Exception as e:
            logger.error(f"Error fetching comments for ticket {ticket_id}: {e}")
            raise

@mcp.tool()
def zendesk_get_article_by_id(article_id: str) -> dict:
    """Get an article by ID."""
    logger.info(f"Starting zendesk_get_article_by_id for article_id: {article_id}")

    ZENDESK_LOCALE = os.getenv("ZENDESK_ARTICLE_LOCALE")
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    logger.debug(f"Using locale: {ZENDESK_LOCALE}, subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = (
        f"{BASE_URL}/api/v2/help_center/{ZENDESK_LOCALE}/articles/{article_id}"
    )
    logger.debug(f"Request URL: {url}")

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug(f"Making GET request for article {article_id}")
            response = client.get(url)
            response.raise_for_status()
            logger.debug(f"Successfully received response with status: {response.status_code}")

            article = response.json()["article"]
            logger.info(f"Successfully retrieved article {article_id} with title: {article.get('title', 'N/A')}")
            return article

        except Exception as e:
            logger.error(f"Error fetching article {article_id}: {e}")
            raise

@mcp.tool()
def zendesk_get_articles() -> list[dict]:
    """Get all articles."""
    logger.info("Starting zendesk_get_articles")

    ZENDESK_LOCALE = os.getenv("ZENDESK_ARTICLE_LOCALE")
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    logger.debug(f"Using locale: {ZENDESK_LOCALE}, subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/help_center/{ZENDESK_LOCALE}/articles.json"
    logger.debug(f"Request URL: {url}")

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug("Making GET request for articles")
            response = client.get(url)
            response.raise_for_status()
            logger.debug(f"Successfully received response with status: {response.status_code}")

            articles = response.json()["articles"]
            logger.info(f"Successfully retrieved {len(articles)} articles")
            return articles

        except Exception as e:
            logger.error(f"Error fetching articles: {e}")
            raise

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
    logger.info(f"Starting zendesk_search_articles with query: '{query}'")

    ZENDESK_LOCALE = os.getenv("ZENDESK_ARTICLE_LOCALE")  # e.g., "en-us"
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    logger.debug(f"Using locale: {ZENDESK_LOCALE}, subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/help_center/articles/search.json"
    logger.debug(f"Search URL: {url}")

    params = {
        "query": query,
        "locale": ZENDESK_LOCALE,
        "sort_by": "updated_at",
        "sort_order": "desc",
    }
    logger.debug(f"Search parameters: {params}")

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug(f"Making GET request to search articles with query: '{query}'")
            response = client.get(url, params=params)
            response.raise_for_status()
            logger.debug(f"Successfully received response with status: {response.status_code}")

            results = response.json().get("results", [])
            logger.info(f"Search completed successfully, found {len(results)} articles matching query: '{query}'")
            return results

        except Exception as e:
            logger.error(f"Error searching articles with query '{query}': {e}")
            raise

@mcp.tool()
def zendesk_add_comment_to_ticket(ticket_id: str, comment_body: str, public: bool = False) -> dict:
    """Add a comment to a Zendesk ticket.

    Updates the ticket with a new comment via Zendesk Ticketing API:
    PUT /api/v2/tickets/{ticket_id}.json
    """
    logger.info(f"Starting zendesk_add_comment_to_ticket for ticket_id: {ticket_id}, public: {public}")
    logger.debug(f"Comment body length: {len(comment_body)} characters")

    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    logger.debug(f"Using Zendesk subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}.json"
    logger.debug(f"Request URL: {url}")

    payload = {
        "ticket": {
            "comment": {
                "body": comment_body,
                "public": public,
            }
        }
    }
    logger.debug(f"Payload prepared for ticket {ticket_id}")

    import httpx
    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug(f"Making PUT request to add comment to ticket {ticket_id}")
            response = client.put(url, json=payload)
            response.raise_for_status()
            logger.debug(f"Successfully received response with status: {response.status_code}")

            ticket_data = response.json()["ticket"]
            logger.info(f"Successfully added comment to ticket {ticket_id}")
            return ticket_data

        except Exception as e:
            logger.error(f"Error adding comment to ticket {ticket_id}: {e}")
            raise

@mcp.tool()
def zendesk_set_ticket_custom_field(
    ticket_id: str, custom_field_id: int, custom_field_value: str, is_multi_option: bool = False
) -> dict:
    """Set the custom field value of a Zendesk ticket.

    Uses Zendesk's Update Ticket API to set a custom field value:
    PUT /api/v2/tickets/{ticket_id}.json
    """#
    logger.info(f"Starting zendesk_set_ticket_custom_field for ticket_id: {ticket_id}, field_id: {custom_field_id}")
    logger.debug(f"Custom field value: {custom_field_value}, is_multi_option: {is_multi_option}")

    if is_multi_option:
        custom_field_value = [custom_field_value]
        logger.debug("Converted custom field value to list for multi-option field")

    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    logger.debug(f"Using Zendesk subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}.json"
    logger.debug(f"Request URL: {url}")

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
    logger.debug(f"Payload prepared for ticket {ticket_id} with custom field {custom_field_id}")

    import httpx

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug(f"Making PUT request to set custom field {custom_field_id} on ticket {ticket_id}")
            response = client.put(url, json=payload)
            response.raise_for_status()
            logger.debug(f"Successfully received response with status: {response.status_code}")

            ticket_data = response.json()["ticket"]
            logger.info(f"Successfully set custom field {custom_field_id} on ticket {ticket_id}")
            return ticket_data

        except Exception as e:
            logger.error(f"Error setting custom field {custom_field_id} on ticket {ticket_id}: {e}")
            raise



@mcp.tool()
def zendesk_set_ticket_tags(ticket_id: str, tags: list[str]) -> list[str]:
    """Set the complete tag list for a ticket (overwrites existing tags)."""
    logger.info(f"Starting zendesk_set_ticket_tags for ticket_id: {ticket_id}")
    logger.debug(f"Setting tags: {tags} (total: {len(tags)} tags)")

    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    logger.debug(f"Using Zendesk subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}/tags.json"
    logger.debug(f"Request URL: {url}")

    payload = {"tags": tags}
    logger.debug(f"Payload prepared for ticket {ticket_id}")

    import httpx

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug(f"Making PUT request to set tags on ticket {ticket_id}")
            resp = client.put(url, json=payload)
            resp.raise_for_status()
            logger.debug(f"Successfully received response with status: {resp.status_code}")

            result_tags = resp.json().get("tags", [])
            logger.info(f"Successfully set {len(result_tags)} tags on ticket {ticket_id}")
            return result_tags

        except Exception as e:
            logger.error(f"Error setting tags on ticket {ticket_id}: {e}")
            raise


@mcp.tool()
def zendesk_add_ticket_tags(ticket_id: str, tags: list[str]) -> list[str]:
    """Add tags to a ticket (preserves existing tags)."""
    logger.info(f"Starting zendesk_add_ticket_tags for ticket_id: {ticket_id}")
    logger.debug(f"Adding tags: {tags} (total: {len(tags)} tags)")

    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    logger.debug(f"Using Zendesk subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}/tags.json"
    logger.debug(f"Request URL: {url}")

    payload = {"tags": tags}
    logger.debug(f"Payload prepared for ticket {ticket_id}")

    import httpx

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug(f"Making POST request to add tags to ticket {ticket_id}")
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            logger.debug(f"Successfully received response with status: {resp.status_code}")

            result_tags = resp.json().get("tags", [])
            logger.info(f"Successfully added tags to ticket {ticket_id}, total tags now: {len(result_tags)}")
            return result_tags

        except Exception as e:
            logger.error(f"Error adding tags to ticket {ticket_id}: {e}")
            raise


@mcp.tool()
def zendesk_get_ticket_field_type(field_id: int) -> dict:
    """Return the Zendesk custom field type and options for a field id.

    Uses GET /api/v2/ticket_fields/{field_id}.json.

    Returns a dict containing at least:
    { "type": str, "custom_field_options": list }
    """
    logger.info(f"Starting zendesk_get_ticket_field_type for field_id: {field_id}")

    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    logger.debug(f"Using Zendesk subdomain: {ZENDESK_SUBDOMAIN}")

    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/ticket_fields/{field_id}.json"
    logger.debug(f"Request URL: {url}")

    import httpx

    with httpx.Client(headers=_get_headers(), timeout=30.0) as client:
        logger.debug("Created HTTP client for Zendesk API")

        try:
            logger.debug(f"Making GET request for ticket field {field_id}")
            resp = client.get(url)
            resp.raise_for_status()
            logger.debug(f"Successfully received response with status: {resp.status_code}")

            field = resp.json().get("ticket_field", {})
            result = {
                "id": field.get("id"),
                "type": field.get("type"),
                "title": field.get("title"),
                "required": field.get("required"),
                "custom_field_options": field.get("custom_field_options", []),
            }

            logger.info(f"Successfully retrieved field info for {field_id}: type={result['type']}, title='{result['title']}'")
            logger.debug(f"Field has {len(result['custom_field_options'])} custom options")
            return result

        except Exception as e:
            logger.error(f"Error fetching ticket field {field_id}: {e}")
            raise




if __name__ == "__main__":
    transport = os.getenv("ZENDESK_MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
