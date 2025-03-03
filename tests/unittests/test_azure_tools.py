import os
import unittest
from unittest.mock import patch, MagicMock

import pytest
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField, 
    SearchIndex, 
    SearchableField,
    SimpleField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile
)
from azure.search.documents.models import VectorizedQuery

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


class TestAzureTools(unittest.TestCase):
    """Unit tests for Azure AI Search utility functions."""

    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'AZURE_SEARCH_ENDPOINT': 'https://test-search.search.windows.net',
            'AZURE_SEARCH_API_KEY': 'test-api-key',
            'AZURE_SEARCH_INDEX_NAME': 'test-index'
        })
        self.env_patcher.start()

        # Common test data
        self.endpoint = 'https://test-search.search.windows.net'
        self.api_key = 'test-api-key'
        self.index_name = 'test-index'
        self.test_document = {"id": "1", "content": "test content"}

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()

    @patch('flock.core.tools.azure_tools.SearchIndexClient')
    @patch('flock.core.tools.azure_tools.SearchClient')
    def test_initialize_clients(self, mock_search_client, mock_index_client):
        """Test the client initialization function."""
        # Set up mocks
        mock_index_client_instance = MagicMock()
        mock_search_client_instance = MagicMock()
        mock_index_client.return_value = mock_index_client_instance
        mock_search_client.return_value = mock_search_client_instance

        # Test with explicit parameters
        clients = azure_search_initialize_clients(self.endpoint, self.api_key, self.index_name)
        
        # Verify calls
        mock_index_client.assert_called_once()
        mock_search_client.assert_called_once()
        self.assertIn('index_client', clients)
        self.assertIn('search_client', clients)

        # Test with environment variables
        clients = azure_search_initialize_clients()
        self.assertIn('index_client', clients)
        self.assertIn('search_client', clients)

    @patch('flock.core.tools.azure_tools.azure_search_initialize_clients')
    def test_create_index(self, mock_initialize_clients):
        """Test index creation function."""
        # Set up mocks
        mock_index_client = MagicMock()
        mock_index_result = MagicMock()
        mock_index_result.name = self.index_name
        
        # Create mock fields with name attributes that return strings, not more mocks
        field1 = MagicMock()
        field1.name = "field1"
        field2 = MagicMock()
        field2.name = "field2"
        mock_index_result.fields = [field1, field2]
        
        mock_index_client.create_or_update_index.return_value = mock_index_result
        mock_initialize_clients.return_value = {'index_client': mock_index_client}

        # Create test fields
        fields = [
            SearchableField(name="field1", type=SearchFieldDataType.String),
            SimpleField(name="field2", type=SearchFieldDataType.Int32)
        ]

        # Test create index
        result = azure_search_create_index(fields=fields)
        
        # Verify calls
        mock_initialize_clients.assert_called_once()
        mock_index_client.create_or_update_index.assert_called_once()
        self.assertEqual(result['index_name'], self.index_name)
        self.assertListEqual(result['fields'], ['field1', 'field2'])
        self.assertTrue(result['created'])
    
    @patch('flock.core.tools.azure_tools.azure_search_initialize_clients')
    def test_upload_documents(self, mock_initialize_clients):
        """Test document upload function."""
        # Set up mocks
        mock_search_client = MagicMock()
        mock_upload_result = [MagicMock(succeeded=True), MagicMock(succeeded=True)]
        mock_search_client.upload_documents.return_value = mock_upload_result
        mock_initialize_clients.return_value = {'search_client': mock_search_client}

        # Test documents
        documents = [
            {"id": "doc1", "content": "content 1"},
            {"id": "doc2", "content": "content 2"}
        ]

        # Test upload documents
        result = azure_search_upload_documents(documents)
        
        # Verify calls
        mock_initialize_clients.assert_called_once()
        mock_search_client.upload_documents.assert_called_once_with(documents=documents)
        self.assertEqual(result['succeeded'], 2)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['total'], 2)

    @patch('flock.core.tools.azure_tools.azure_search_initialize_clients')
    def test_query(self, mock_initialize_clients):
        """Test search query function."""
        # Set up mocks
        mock_search_client = MagicMock()
        mock_search_result = [
            {"id": "doc1", "content": "content 1"},
            {"id": "doc2", "content": "content 2"}
        ]
        mock_search_client.search.return_value = mock_search_result
        mock_initialize_clients.return_value = {'search_client': mock_search_client}

        # Test query
        results = azure_search_query(search_text="test query")
        
        # Verify calls
        mock_initialize_clients.assert_called_once()
        mock_search_client.search.assert_called_once()
        self.assertEqual(len(results), 2)
        
        # Test vector query
        vector_embedding = [0.1, 0.2, 0.3]
        results = azure_search_query(vector=vector_embedding, vector_field="embedding")
        mock_search_client.search.assert_called()

    @patch('flock.core.tools.azure_tools.azure_search_initialize_clients')
    def test_get_document(self, mock_initialize_clients):
        """Test get document function."""
        # Set up mocks
        mock_search_client = MagicMock()
        mock_document = {"id": "doc1", "content": "content 1"}
        mock_search_client.get_document.return_value = mock_document
        mock_initialize_clients.return_value = {'search_client': mock_search_client}

        # Test get document
        result = azure_search_get_document(key="doc1")
        
        # Verify calls
        mock_initialize_clients.assert_called_once()
        mock_search_client.get_document.assert_called_once_with(key="doc1", selected_fields=None)
        self.assertEqual(result, mock_document)

    @patch('flock.core.tools.azure_tools.azure_search_initialize_clients')
    def test_delete_documents(self, mock_initialize_clients):
        """Test delete documents function."""
        # Set up mocks
        mock_search_client = MagicMock()
        mock_delete_result = [MagicMock(succeeded=True), MagicMock(succeeded=True)]
        mock_search_client.delete_documents.return_value = mock_delete_result
        mock_initialize_clients.return_value = {'search_client': mock_search_client}

        # Test delete documents
        keys = ["doc1", "doc2"]
        result = azure_search_delete_documents(keys=keys)
        
        # Verify calls
        mock_initialize_clients.assert_called_once()
        mock_search_client.delete_documents.assert_called_once()
        self.assertEqual(result['succeeded'], 2)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['total'], 2)

    @patch('flock.core.tools.azure_tools.azure_search_initialize_clients')
    def test_list_indexes(self, mock_initialize_clients):
        """Test list indexes function."""
        # Set up mocks
        mock_index_client = MagicMock()
        mock_index1 = MagicMock()
        mock_index1.name = "index1"
        mock_index1.fields = [MagicMock(name="field1"), MagicMock(name="field2")]
        mock_index2 = MagicMock()
        mock_index2.name = "index2"
        mock_index2.fields = [MagicMock(name="field1")]
        mock_index_client.list_indexes.return_value = [mock_index1, mock_index2]
        mock_initialize_clients.return_value = {'index_client': mock_index_client}

        # Test list indexes
        results = azure_search_list_indexes()
        
        # Verify calls
        mock_initialize_clients.assert_called_once()
        mock_index_client.list_indexes.assert_called_once()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], "index1")
        self.assertEqual(results[0]['field_count'], 2)
        self.assertEqual(results[1]['name'], "index2")
        self.assertEqual(results[1]['field_count'], 1)

    @patch('flock.core.tools.azure_tools.azure_search_initialize_clients')
    def test_get_index_statistics(self, mock_initialize_clients):
        """Test get index statistics function."""
        # Set up mocks
        mock_search_client = MagicMock()
        mock_search_client.get_document_count.return_value = 42
        mock_initialize_clients.return_value = {'search_client': mock_search_client}

        # Test get index statistics
        result = azure_search_get_index_statistics()
        
        # Verify calls
        mock_initialize_clients.assert_called_once()
        mock_search_client.get_document_count.assert_called_once()
        self.assertEqual(result['document_count'], 42)

    @patch('flock.core.tools.azure_tools.azure_search_initialize_clients')
    def test_create_vector_index(self, mock_initialize_clients):
        """Test create vector index function."""
        # Set up mocks
        mock_index_client = MagicMock()
        mock_index_result = MagicMock()
        mock_index_result.name = self.index_name
        mock_index_client.create_or_update_index.return_value = mock_index_result
        mock_initialize_clients.return_value = {'index_client': mock_index_client}

        # Test fields
        fields = [
            {"name": "id", "type": "string", "key": True},
            {"name": "content", "type": "string", "searchable": True},
            {"name": "embedding", "type": "collection", "vector": True}
        ]

        # Test create vector index
        result = azure_search_create_vector_index(
            fields=fields,
            vector_dimensions=384
        )
        
        # Verify calls
        mock_initialize_clients.assert_called_once()
        mock_index_client.create_or_update_index.assert_called_once()
        self.assertEqual(result['index_name'], self.index_name)
        self.assertEqual(result['vector_dimensions'], 384)
        self.assertEqual(result['algorithm'], "hnsw")
        self.assertTrue(result['created'])


if __name__ == '__main__':
    unittest.main() 