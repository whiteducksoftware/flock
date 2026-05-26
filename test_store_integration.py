#!/usr/bin/env python3
"""Test script to verify the Azure Table Storage integration with environment variables."""

import asyncio
import os


# Set environment variables to test the factory function
def test_sqlite_store():
    """Test SQLite store (default)."""
    os.environ["FLOCK_WEBAPP_STORE"] = "local"
    os.environ["FLOCK_WEBAPP_STORE_CONNECTION"] = "test_shared_links.db"

    from flock.webapp.app.services.sharing_models import SharedLinkConfig
    from flock.webapp.app.services.sharing_store import create_shared_link_store

    async def run_test():
        print("Testing SQLite store...")
        store = create_shared_link_store()
        print(f"Created store: {type(store).__name__}")

        # Initialize the store
        await store.initialize()
        print("Store initialized successfully")

        # Create a test config
        config = SharedLinkConfig(
            share_id="test123",
            agent_name="TestAgent",
            flock_definition="name: TestFlock\nagents:\n  TestAgent:\n    input: 'message: str'",
            share_type="agent_run"
        )

        # Test save
        saved_config = await store.save_config(config)
        print(f"Saved config: {saved_config.share_id}")

        # Test retrieve
        retrieved_config = await store.get_config("test123")
        if retrieved_config:
            print(f"Retrieved config: {retrieved_config.share_id}")
        else:
            print("Failed to retrieve config")

        # Test delete
        deleted = await store.delete_config("test123")
        print(f"Deleted config: {deleted}")

    asyncio.run(run_test())

def test_azure_store():
    """Test Azure Table Storage store."""
    os.environ["FLOCK_WEBAPP_STORE"] = "azure-storage"
    os.environ["FLOCK_WEBAPP_STORE_CONNECTION"] = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"

    from flock.webapp.app.services.sharing_store import (
        AZURE_AVAILABLE,
        create_shared_link_store,
    )

    if not AZURE_AVAILABLE:
        print("Azure dependencies not available - this is expected if azure-data-tables is not installed")
        return

    try:
        print("Testing Azure Table Storage store...")
        store = create_shared_link_store()
        print(f"Created store: {type(store).__name__}")
        print("Azure Table Storage store created successfully (connection will fail with fake credentials)")
    except Exception as e:
        print(f"Expected error with fake credentials: {e}")

def test_invalid_store_type():
    """Test invalid store type."""
    os.environ["FLOCK_WEBAPP_STORE"] = "invalid"

    from flock.webapp.app.services.sharing_store import create_shared_link_store

    try:
        store = create_shared_link_store()
        print("ERROR: Should have failed with invalid store type")
    except ValueError as e:
        print(f"Correctly caught error: {e}")

if __name__ == "__main__":
    print("=== Testing Store Integration ===\n")

    # Test SQLite store
    test_sqlite_store()
    print()

    # Test Azure store creation
    test_azure_store()
    print()

    # Test invalid store type
    test_invalid_store_type()
    print()

    print("=== Tests completed ===")

    # Clean up test database
    try:
        os.remove("test_shared_links.db")
        print("Cleaned up test database")
    except FileNotFoundError:
        pass
