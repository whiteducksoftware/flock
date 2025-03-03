"""
Example script demonstrating how to use the Azure AI Search functions.

This script shows how to:
1. Create a search index
2. Upload documents to the index
3. Query the index using text search
4. Get individual documents by ID
5. Delete documents

Requirements:
- Set the following environment variables:
  - AZURE_SEARCH_ENDPOINT: Your Azure AI Search service endpoint URL
  - AZURE_SEARCH_API_KEY: Your Azure AI Search API key
  - AZURE_SEARCH_INDEX_NAME: (Optional) Default index name

Usage:
python azure_search_example.py

"""

import os
import time
import uuid
from dotenv import load_dotenv
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
    azure_search_get_index_statistics
)


def main():
    """Execute the Azure AI Search example workflow."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Create a unique index name for this example
    timestamp = int(time.time())
    random_id = str(uuid.uuid4())[:8]
    index_name = f"example-index-{timestamp}-{random_id}"
    
    print(f"Using index name: {index_name}")
    
    # Create the search index
    print("\n1. Creating search index...")
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String, sortable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="rating", type=SearchFieldDataType.Int32, filterable=True, sortable=True)
    ]
    
    create_result = azure_search_create_index(
        index_name=index_name,
        fields=fields
    )
    print(f"Index created: {create_result}")
    
    # Wait a bit for the index to be ready
    time.sleep(2)
    
    # Upload documents
    print("\n2. Uploading documents...")
    documents = [
        {
            "id": "doc1",
            "title": "Azure AI Search Overview",
            "content": "Azure AI Search is a cloud search service with built-in AI capabilities.",
            "category": "cloud",
            "rating": 5
        },
        {
            "id": "doc2",
            "title": "Python Development Best Practices",
            "content": "Write clean, maintainable Python code by following established best practices.",
            "category": "development",
            "rating": 4
        },
        {
            "id": "doc3",
            "title": "Azure and Python Integration",
            "content": "Learn how to use Azure services with Python applications.",
            "category": "cloud",
            "rating": 5
        }
    ]
    
    upload_result = azure_search_upload_documents(
        documents=documents,
        index_name=index_name
    )
    print(f"Documents uploaded: {upload_result}")
    
    # Wait for indexing to complete
    time.sleep(3)
    
    # Get document count
    print("\n3. Getting index statistics...")
    stats = azure_search_get_index_statistics(index_name=index_name)
    print(f"Document count: {stats['document_count']}")
    
    # Get a specific document
    print("\n4. Retrieving specific document...")
    doc = azure_search_get_document(key="doc1", index_name=index_name)
    print(f"Retrieved document: {doc}")
    
    # Search documents with text query
    print("\n5. Searching documents with text...")
    results = azure_search_query(
        search_text="Azure",
        index_name=index_name
    )
    print(f"Search results for 'Azure': {results}")
    
    # Filter documents
    print("\n6. Filtering documents...")
    filtered_results = azure_search_query(
        filter="category eq 'cloud'",
        index_name=index_name
    )
    print(f"Filtered results for cloud category: {filtered_results}")
    
    # Delete a document
    print("\n7. Deleting a document...")
    delete_result = azure_search_delete_documents(
        keys=["doc1"],
        index_name=index_name
    )
    print(f"Delete result: {delete_result}")
    
    # List all indexes
    print("\n8. Listing all indexes...")
    indexes = azure_search_list_indexes()
    print(f"All indexes: {indexes}")
    
    # Clean up: delete the test index
    print("\n9. Cleaning up...")
    try:
        # This requires direct SDK access
        clients = azure_search_initialize_clients()
        index_client = clients["index_client"]
        index_client.delete_index(index_name)
        print(f"Index {index_name} deleted successfully")
    except Exception as e:
        print(f"Warning: Failed to delete test index {index_name}: {e}")
    
    print("\nExample completed!")


if __name__ == "__main__":
    main() 