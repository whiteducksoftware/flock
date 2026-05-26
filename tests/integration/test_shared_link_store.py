"""
Integration tests for the shared link store implementations.

Tests both SQLite and Azure Table Storage backends.
"""

import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from flock.webapp.app.services.sharing_models import FeedbackRecord, SharedLinkConfig
from flock.webapp.app.services.sharing_store import create_shared_link_store


class TestSharedLinkStoreIntegration:
    """Integration tests for shared link store implementations."""

    def test_sqlite_store_integration(self):
        """Test SQLite store with environment variables."""
        asyncio.run(self._test_sqlite_store())

    async def _test_sqlite_store(self):
        """Test SQLite store functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_shared_links.db"
            
            # Set environment variables for SQLite
            original_store = os.environ.get("FLOCK_WEBAPP_STORE")
            original_conn = os.environ.get("FLOCK_WEBAPP_STORE_CONNECTION")
            
            try:
                os.environ["FLOCK_WEBAPP_STORE"] = "local"
                os.environ["FLOCK_WEBAPP_STORE_CONNECTION"] = str(db_path)
                
                # Create store using factory
                store = create_shared_link_store()
                await store.initialize()
                
                # Test shared link config
                config = SharedLinkConfig(
                    share_id="test-123",
                    agent_name="TestAgent",
                    flock_definition="name: TestFlock\nagents:\n  TestAgent:\n    input: 'message: str'",
                    share_type="agent_run"
                )
                
                # Test save and retrieve
                saved_config = await store.save_config(config)
                assert saved_config.share_id == "test-123"
                
                retrieved_config = await store.get_config("test-123")
                assert retrieved_config is not None
                assert retrieved_config.share_id == "test-123"
                assert retrieved_config.agent_name == "TestAgent"
                assert retrieved_config.share_type == "agent_run"
                
                # Test feedback
                feedback = FeedbackRecord(
                    feedback_id="feedback-123",
                    share_id="test-123",
                    context_type="agent_run",
                    reason="Test feedback",
                    expected_response="Expected output",
                    actual_response="Actual output",
                    flock_name="TestFlock",
                    agent_name="TestAgent",
                    flock_definition=config.flock_definition
                )
                
                saved_feedback = await store.save_feedback(feedback)
                assert saved_feedback.feedback_id == "feedback-123"
                
                # Test delete
                deleted = await store.delete_config("test-123")
                assert deleted is True
                
                # Verify deletion
                retrieved_after_delete = await store.get_config("test-123")
                assert retrieved_after_delete is None
                
                print("✅ SQLite store integration test passed!")
                
            finally:
                # Restore environment variables
                if original_store is not None:
                    os.environ["FLOCK_WEBAPP_STORE"] = original_store
                elif "FLOCK_WEBAPP_STORE" in os.environ:
                    del os.environ["FLOCK_WEBAPP_STORE"]
                    
                if original_conn is not None:
                    os.environ["FLOCK_WEBAPP_STORE_CONNECTION"] = original_conn
                elif "FLOCK_WEBAPP_STORE_CONNECTION" in os.environ:
                    del os.environ["FLOCK_WEBAPP_STORE_CONNECTION"]

    @pytest.mark.skipif(
        not os.environ.get("AZURE_STORAGE_CONNECTION_STRING"),
        reason="Azure Storage connection string not provided"
    )
    def test_azure_table_store_integration(self):
        """Test Azure Table Storage store with environment variables."""
        asyncio.run(self._test_azure_table_store())

    async def _test_azure_table_store(self):
        """Test Azure Table Storage functionality."""
        azure_conn_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not azure_conn_string:
            print("⚠️ Skipping Azure Table Storage test - no connection string provided")
            return
            
        # Set environment variables for Azure Table Storage
        original_store = os.environ.get("FLOCK_WEBAPP_STORE")
        original_conn = os.environ.get("FLOCK_WEBAPP_STORE_CONNECTION")
        
        try:
            os.environ["FLOCK_WEBAPP_STORE"] = "azure-storage"
            os.environ["FLOCK_WEBAPP_STORE_CONNECTION"] = azure_conn_string
            
            # Create store using factory
            store = create_shared_link_store()
            await store.initialize()
            
            # Test shared link config
            test_id = f"test-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            config = SharedLinkConfig(
                share_id=test_id,
                agent_name="TestAgent",
                flock_definition="name: TestFlock\nagents:\n  TestAgent:\n    input: 'message: str'",
                share_type="chat",
                chat_message_key="user_input",
                chat_history_key="history",
                chat_response_key="response"
            )
            
            # Test save and retrieve
            saved_config = await store.save_config(config)
            assert saved_config.share_id == test_id
            
            retrieved_config = await store.get_config(test_id)
            assert retrieved_config is not None
            assert retrieved_config.share_id == test_id
            assert retrieved_config.agent_name == "TestAgent"
            assert retrieved_config.share_type == "chat"
            assert retrieved_config.chat_message_key == "user_input"
            
            # Test feedback
            feedback_id = f"feedback-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            feedback = FeedbackRecord(
                feedback_id=feedback_id,
                share_id=test_id,
                context_type="chat",
                reason="Test feedback from Azure",
                expected_response="Expected chat response",
                actual_response="Actual chat response",
                flock_name="TestFlock",
                agent_name="TestAgent",
                flock_definition=config.flock_definition
            )
            
            saved_feedback = await store.save_feedback(feedback)
            assert saved_feedback.feedback_id == feedback_id
            
            # Test delete
            deleted = await store.delete_config(test_id)
            assert deleted is True
            
            # Verify deletion
            retrieved_after_delete = await store.get_config(test_id)
            assert retrieved_after_delete is None
            
            print("✅ Azure Table Storage integration test passed!")
            
        except ImportError as e:
            print(f"⚠️ Skipping Azure Table Storage test - missing dependencies: {e}")
        finally:
            # Restore environment variables
            if original_store is not None:
                os.environ["FLOCK_WEBAPP_STORE"] = original_store
            elif "FLOCK_WEBAPP_STORE" in os.environ:
                del os.environ["FLOCK_WEBAPP_STORE"]
                
            if original_conn is not None:
                os.environ["FLOCK_WEBAPP_STORE_CONNECTION"] = original_conn
            elif "FLOCK_WEBAPP_STORE_CONNECTION" in os.environ:
                del os.environ["FLOCK_WEBAPP_STORE_CONNECTION"]

    def test_factory_with_invalid_store_type(self):
        """Test factory function with invalid store type."""
        original_store = os.environ.get("FLOCK_WEBAPP_STORE")
        
        try:
            os.environ["FLOCK_WEBAPP_STORE"] = "invalid-store-type"
            
            with pytest.raises(ValueError, match="Unsupported store type"):
                create_shared_link_store()
                
        finally:
            if original_store is not None:
                os.environ["FLOCK_WEBAPP_STORE"] = original_store
            elif "FLOCK_WEBAPP_STORE" in os.environ:
                del os.environ["FLOCK_WEBAPP_STORE"]

    def test_factory_defaults(self):
        """Test factory function with default values."""
        # Clear environment variables
        original_store = os.environ.get("FLOCK_WEBAPP_STORE")
        original_conn = os.environ.get("FLOCK_WEBAPP_STORE_CONNECTION")
        
        try:
            if "FLOCK_WEBAPP_STORE" in os.environ:
                del os.environ["FLOCK_WEBAPP_STORE"]
            if "FLOCK_WEBAPP_STORE_CONNECTION" in os.environ:
                del os.environ["FLOCK_WEBAPP_STORE_CONNECTION"]
            
            # Should default to SQLite with default path
            store = create_shared_link_store()
            assert store.__class__.__name__ == "SQLiteSharedLinkStore"
            
        finally:
            # Restore environment variables
            if original_store is not None:
                os.environ["FLOCK_WEBAPP_STORE"] = original_store
            if original_conn is not None:
                os.environ["FLOCK_WEBAPP_STORE_CONNECTION"] = original_conn


if __name__ == "__main__":
    # Run basic tests
    test_suite = TestSharedLinkStoreIntegration()
    
    print("🧪 Running Shared Link Store Integration Tests...")
    print()
    
    # Test SQLite
    print("📁 Testing SQLite store...")
    test_suite.test_sqlite_store_integration()
    print()
    
    # Test Azure (if connection string available)
    if os.environ.get("AZURE_STORAGE_CONNECTION_STRING"):
        print("☁️ Testing Azure Table Storage...")
        test_suite.test_azure_table_store_integration()
    else:
        print("⚠️ Skipping Azure Table Storage test - set AZURE_STORAGE_CONNECTION_STRING to test")
    print()
    
    # Test factory
    print("🏭 Testing factory function...")
    test_suite.test_factory_defaults()
    test_suite.test_factory_with_invalid_store_type()
    print("✅ Factory tests passed!")
    print()
    
    print("🎉 All integration tests completed!")
