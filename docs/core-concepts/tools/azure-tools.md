# Azure Search Tools

Flock provides a set of tools for seamless integration with [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/), allowing you to leverage powerful vector search and document retrieval capabilities in your AI agents.

## Overview

Azure AI Search (formerly Azure Cognitive Search) is a cloud search service that gives developers APIs and tools for building rich search experiences over private, heterogeneous content in web, mobile, and enterprise applications. In Flock, we've provided tools to easily interact with Azure AI Search, allowing your agents to store, search, and retrieve information using both text and vector embeddings.

## Features

- Create and manage search indexes
- Upload and manage documents
- Perform text-based and vector-based searches
- Retrieve detailed index statistics
- Delete documents and manage content

## Environment Configuration

The Azure Search tools rely on environment variables for configuration:

```python
# Required environment variables
AZURE_SEARCH_ENDPOINT  # The endpoint URL for your Azure AI Search service
AZURE_SEARCH_API_KEY   # The API key for your Azure AI Search service
AZURE_SEARCH_INDEX_NAME  # Optional: A default index name to use
```

## Available Tools

### Initialization

```python
from flock.core.tools.azure_tools import azure_search_initialize_clients

# Initialize clients (uses environment variables by default)
clients = azure_search_initialize_clients()

# Or specify endpoints manually
clients = azure_search_initialize_clients(
    endpoint="https://your-service.search.windows.net",
    api_key="your-api-key",
    index_name="your-index-name"
)
```

### Index Management

```python
from flock.core.tools.azure_tools import (
    azure_search_create_index,
    azure_search_list_indexes,
    azure_search_get_index_statistics
)
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField
)

# Create fields for the index
fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SearchableField(name="title", type=SearchFieldDataType.String),
    SearchableField(name="content", type=SearchFieldDataType.String)
]

# Create index
result = azure_search_create_index(
    index_name="my-index",
    fields=fields
)

# List all indexes
indexes = azure_search_list_indexes()

# Get index statistics
stats = azure_search_get_index_statistics(index_name="my-index")
```

### Vector Search Index Creation

```python
from flock.core.tools.azure_tools import azure_search_create_vector_index

# Create a vector index
fields = [
    {"name": "id", "type": "string", "key": True},
    {"name": "title", "type": "string", "searchable": True},
    {"name": "content", "type": "string", "searchable": True},
    {"name": "embedding", "type": "collection", "vector": True}
]

result = azure_search_create_vector_index(
    fields=fields,
    vector_dimensions=1536,  # Dimensions for your vector embeddings
    index_name="vector-index",
    algorithm_kind="hnsw"  # Using HNSW algorithm for vector search
)
```

### Document Management

```python
from flock.core.tools.azure_tools import (
    azure_search_upload_documents,
    azure_search_get_document,
    azure_search_delete_documents
)

# Upload documents
documents = [
    {
        "id": "doc1",
        "title": "Sample Document",
        "content": "This is a sample document for Azure Search."
    },
    {
        "id": "doc2",
        "title": "Another Document",
        "content": "This is another sample document."
    }
]

upload_result = azure_search_upload_documents(
    documents=documents,
    index_name="my-index"
)

# Get a specific document
document = azure_search_get_document(
    key="doc1",
    index_name="my-index"
)

# Delete documents
delete_result = azure_search_delete_documents(
    keys=["doc1", "doc2"],
    index_name="my-index"
)
```

### Search and Query

```python
from flock.core.tools.azure_tools import azure_search_query

# Text-based search
results = azure_search_query(
    search_text="sample",
    index_name="my-index"
)

# Filter-based search
filtered_results = azure_search_query(
    filter="id eq 'doc1'",
    index_name="my-index"
)

# Vector search (for vector indexes)
vector = [0.1, 0.2, 0.3, ...]  # Your vector embedding
vector_results = azure_search_query(
    vector=vector,
    vector_field="embedding",
    vector_k=10,  # Return top 10 results
    index_name="vector-index"
)
```

## Integration with Agents

Azure Search tools can be easily integrated with your Flock agents to provide powerful retrieval capabilities:

```python
from flock import Flock, FlockFactory
from flock.core.tools.azure_tools import (
    azure_search_query,
    azure_search_upload_documents
)

# Create an agent with access to Azure Search tools
agent = FlockFactory.create_default_agent(
    name="search_agent",
    input="search_query",
    output="search_results",
    tools=[azure_search_query]
)

# Create a document management agent
upload_agent = FlockFactory.create_default_agent(
    name="upload_agent",
    input="documents_to_upload",
    output="upload_status",
    tools=[azure_search_upload_documents]
)

# Add to Flock
flock = Flock()
flock.add_agent(agent)
flock.add_agent(upload_agent)
```

## Best Practices

1. **Environment Variables**: Use environment variables for sensitive information like API keys.
2. **Error Handling**: Implement proper error handling when using these tools, as network requests can sometimes fail.
3. **Batching**: When uploading large numbers of documents, consider batching them in groups of 100-1000.
4. **Indexing Delay**: Allow a small delay (1-2 seconds) after uploading documents before searching them to ensure indexing is complete.
5. **Vector Dimensions**: Ensure your vector dimensions match between your embeddings and the index configuration.

## Limitations

- The maximum number of documents that can be uploaded in a single request is 1000.
- Vector search requires the appropriate SKU tier in Azure AI Search.
- Certain operations may have rate limits depending on your Azure service tier.

## Further Resources

- [Azure AI Search Documentation](https://docs.microsoft.com/en-us/azure/search/)
- [Vector Search in Azure AI Search](https://learn.microsoft.com/en-us/azure/search/vector-search-overview)
- [Azure Python SDK Documentation](https://docs.microsoft.com/en-us/python/api/overview/azure/search-documents-readme?view=azure-python) 