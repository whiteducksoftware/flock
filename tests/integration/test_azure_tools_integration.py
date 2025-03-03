import os
import time
import uuid
import pytest
from typing import List, Dict, Any
import random

import pytest
from azure.search.documents.indexes.models import (
    SearchFieldDataType,
    SimpleField,
    SearchableField
)

from flock.core.tools.azure_tools import (
    azure_search_initialize_clients,
    azure_search_create_index,
    azure_search_upload_documents,
    azure_search_query,
    azure_search_get_document,
    azure_search_delete_documents,
    azure_search_list_indexes,
    azure_search_get_index_statistics,
    azure_search_create_vector_index
)


@pytest.fixture(scope="module")
def integration_enabled():
    """Check if integration tests are enabled and required env vars are set."""
    required_env_vars = [
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_API_KEY",
    ]
    
    # Check if environment variables are set
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        pytest.skip(f"Integration tests skipped. Missing env vars: {', '.join(missing_vars)}")
    return True


@pytest.fixture(scope="module")
def test_index_name():
    """Create a unique test index name."""
    # Create a unique name with timestamp and random uuid to avoid conflicts
    timestamp = int(time.time())
    random_id = str(uuid.uuid4())[:8]
    return f"test-index-{timestamp}-{random_id}"


@pytest.fixture(scope="module")
def setup_test_index(integration_enabled, test_index_name):
    """Create a test index for integration tests."""
    # Set up the test index
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String, sortable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="rating", type=SearchFieldDataType.Int32, filterable=True)
    ]
    
    # Create the index
    result = azure_search_create_index(
        index_name=test_index_name,
        fields=fields
    )
    
    # Wait a bit for index creation to complete
    time.sleep(2)
    
    # Return the index name
    yield test_index_name
    
    # Clean up after tests
    try:
        # Find a way to delete the index if possible
        # This might require using the azure SDK directly as our tools don't have this function
        clients = azure_search_initialize_clients()
        index_client = clients["index_client"]
        index_client.delete_index(test_index_name)
    except Exception as e:
        print(f"Warning: Failed to delete test index {test_index_name}: {e}")


@pytest.fixture(scope="module")
def sample_documents():
    """Create sample documents for testing."""
    return [
        {
            "id": "doc1",
            "title": "Azure Search Integration",
            "content": "This is a test document for Azure Search integration tests.",
            "rating": 5
        },
        {
            "id": "doc2",
            "title": "Python Testing",
            "content": "How to write effective integration tests in Python.",
            "rating": 4
        },
        {
            "id": "doc3",
            "title": "Azure AI Services",
            "content": "Azure AI Search is a cloud search service with built-in AI capabilities.",
            "rating": 5
        }
    ]


class TestAzureToolsIntegration:
    """Integration tests for Azure AI Search tools."""
    
    def test_initialize_clients(self, integration_enabled):
        """Test initializing clients with environment variables."""
        clients = azure_search_initialize_clients()
        assert "index_client" in clients
        # search_client requires an index name, which might not be set in the env vars
        
    def test_list_indexes(self, integration_enabled):
        """Test listing all indexes."""
        indexes = azure_search_list_indexes()
        assert isinstance(indexes, list)
        # The result should be a list (even if empty)
        
    def test_index_creation_upload_query(self, integration_enabled, setup_test_index, sample_documents):
        """Test the full workflow: create index, upload documents, and query."""
        index_name = setup_test_index
        
        # 1. Upload documents
        upload_result = azure_search_upload_documents(
            documents=sample_documents,
            index_name=index_name
        )
        assert upload_result["succeeded"] == len(sample_documents)
        
        # Wait a bit for indexing to complete
        time.sleep(3)
        
        # 2. Get index statistics
        stats = azure_search_get_index_statistics(index_name=index_name)
        assert "document_count" in stats
        assert stats["document_count"] == len(sample_documents)
        
        # 3. Retrieve a specific document
        doc = azure_search_get_document(key="doc1", index_name=index_name)
        assert doc["id"] == "doc1"
        assert "title" in doc
        assert "content" in doc
        
        # 4. Search documents
        results = azure_search_query(
            search_text="Azure",
            index_name=index_name
        )
        assert len(results) > 0
        assert any("Azure" in doc.get("title", "") or "Azure" in doc.get("content", "") 
                  for doc in results)
        
        # 5. Filter documents
        filtered_results = azure_search_query(
            filter="rating eq 5",
            index_name=index_name
        )
        assert all(doc.get("rating") == 5 for doc in filtered_results)
        
        # 6. Delete a document
        delete_result = azure_search_delete_documents(
            keys=["doc1"],
            index_name=index_name
        )
        assert delete_result["succeeded"] == 1
        
        # Wait for deletion to propagate
        time.sleep(2)
        
        # 7. Verify document was deleted
        try:
            azure_search_get_document(key="doc1", index_name=index_name)
            assert False, "Document should have been deleted"
        except Exception:
            # Expected exception because document was deleted
            pass
        
        # 8. Verify document count was reduced
        stats = azure_search_get_index_statistics(index_name=index_name)
        assert stats["document_count"] == len(sample_documents) - 1


@pytest.mark.skip(reason="Vector search requires additional setup that may not be available")
class TestVectorSearch:
    """Integration tests for vector search capabilities."""
    
    @pytest.fixture(scope="class")
    def vector_index_name(self):
        """Create a unique test vector index name."""
        timestamp = int(time.time())
        random_id = str(uuid.uuid4())[:8]
        return f"vector-index-{timestamp}-{random_id}"
    
    @pytest.fixture(scope="class")
    def setup_vector_index(self, integration_enabled, vector_index_name):
        """Create a test vector index for integration tests."""
        # Vector fields definition
        fields = [
            {"name": "id", "type": "string", "key": True},
            {"name": "title", "type": "string", "searchable": True},
            {"name": "content", "type": "string", "searchable": True},
            {"name": "embedding", "type": "collection", "vector": True}
        ]
        
        # Create vector index
        result = azure_search_create_vector_index(
            fields=fields,
            vector_dimensions=3,  # Small dimension for testing
            index_name=vector_index_name
        )
        
        # Wait for index creation
        time.sleep(2)
        
        # Return the index name
        yield vector_index_name
        
        # Clean up
        try:
            clients = azure_search_initialize_clients()
            index_client = clients["index_client"]
            index_client.delete_index(vector_index_name)
        except Exception as e:
            print(f"Warning: Failed to delete vector test index {vector_index_name}: {e}")
    
    @pytest.fixture(scope="class")
    def sample_vector_documents(self):
        """Create sample documents with vector embeddings."""
        return [
            {
                "id": "vec1",
                "title": "First Vector Document",
                "content": "This is the first test document with vector embedding.",
                "embedding": [0.1, 0.2, 0.3]
            },
            {
                "id": "vec2",
                "title": "Second Vector Document",
                "content": "This is the second test document with vector embedding.",
                "embedding": [0.2, 0.3, 0.4]
            },
            {
                "id": "vec3",
                "title": "Third Vector Document",
                "content": "This is the third test document with vector embedding.",
                "embedding": [0.3, 0.4, 0.5]
            }
        ]
    
    def test_vector_search(self, setup_vector_index, sample_vector_documents):
        """Test vector search functionality."""
        index_name = setup_vector_index
        
        # 1. Upload documents with vector embeddings
        upload_result = azure_search_upload_documents(
            documents=sample_vector_documents,
            index_name=index_name
        )
        assert upload_result["succeeded"] == len(sample_vector_documents)
        
        # Wait for indexing to complete
        time.sleep(3)
        
        # 2. Perform vector search
        query_vector = [0.1, 0.2, 0.3]  # Same as first document
        results = azure_search_query(
            vector=query_vector,
            vector_field="embedding",
            index_name=index_name
        )
        
        # First result should be the closest match (vec1)
        assert len(results) > 0
        assert results[0]["id"] == "vec1" 