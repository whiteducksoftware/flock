"""Tools for interacting with Zendesk."""

import os

import httpx

ZENDESK_BEARER_TOKEN = os.getenv("ZENDESK_BEARER_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {ZENDESK_BEARER_TOKEN}",
    "Accept": "application/json",
}


def get_tickets(number_of_tickets: int = 10) -> list[dict]:
    """Get all tickets."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets.json"
    all_tickets = []
    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        while url and len(all_tickets) < number_of_tickets:
            response = client.get(url)
            response.raise_for_status()

            data = response.json()
            tickets = data.get("tickets", [])
            all_tickets.extend(tickets)

            url = data.get("next_page")
    return all_tickets


def get_ticket_by_id(ticket_id: str) -> dict:
    """Get a ticket by ID."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}"
    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()["ticket"]


def get_comments_by_ticket_id(ticket_id: str) -> list[dict]:
    """Get all comments for a ticket."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}/comments"
    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()["comments"]


def get_article_by_id(article_id: str) -> dict:
    """Get an article by ID."""
    ZENDESK_LOCALE = os.getenv("ZENDESK_ARTICLE_LOCALE")
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = (
        f"{BASE_URL}/api/v2/help_center/{ZENDESK_LOCALE}/articles/{article_id}"
    )
    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()["article"]


def get_articles() -> list[dict]:
    """Get all articles."""
    ZENDESK_LOCALE = os.getenv("ZENDESK_ARTICLE_LOCALE")
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/help_center/{ZENDESK_LOCALE}/articles.json"
    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()["articles"]


def search_articles(query: str) -> list[dict]:
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

    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json().get("results", [])
