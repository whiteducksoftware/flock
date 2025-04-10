"""Tools for interacting with Zendesk."""

import os
from collections.abc import Generator

import httpx

ZENDESK_EMAIL = os.getenv("ZENDESK_EMAIL")
ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN")


AUTH = (f"{ZENDESK_EMAIL}/token", ZENDESK_API_TOKEN)
HEADERS = {"Accept": "application/json"}


def get_tickets() -> Generator[dict, None, None]:
    """Get all tickets."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets.json"

    with httpx.Client(auth=AUTH, headers=HEADERS, timeout=30.0) as client:
        while url:
            response = client.get(url)
            response.raise_for_status()

            data = response.json()
            tickets = data.get("tickets", [])
            yield from tickets

            url = data.get("next_page")


def get_ticket_by_id(ticket_id: str) -> dict:
    """Get a ticket by ID."""
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_TICKET")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = f"{BASE_URL}/api/v2/tickets/{ticket_id}"
    with httpx.Client(auth=AUTH, headers=HEADERS, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def get_article_by_id(article_id: str) -> dict:
    """Get an article by ID."""
    ZENDESK_LOCALE = os.getenv("ZENDESK_ARTICLE_LOCALE")
    ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN_ARTICLE")
    BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
    url = (
        f"{BASE_URL}/api/v2/help_center/{ZENDESK_LOCALE}/articles/{article_id}"
    )
    with httpx.Client(auth=AUTH, headers=HEADERS, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


# get_ticket_by_id("366354")
