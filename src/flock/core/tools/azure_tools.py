import os
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    ExhaustiveKnnAlgorithmConfiguration,
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery

from flock.core.logging.trace_and_logged import traced_and_logged


def _get_default_endpoint() -> str:
    """Get the default Azure Search endpoint from environment variables."""
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        raise ValueError(
            "AZURE_SEARCH_ENDPOINT environment variable is not set"
        )
    return endpoint


def _get_default_api_key() -> str:
    """Get the default Azure Search API key from environment variables."""
    api_key = os.environ.get("AZURE_SEARCH_API_KEY")
    if not api_key:
        raise ValueError("AZURE_SEARCH_API_KEY environment variable is not set")
    return api_key


def _get_default_index_name() -> str:
    """Get the default Azure Search index name from environment variables."""
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME")
    if not index_name:
        raise ValueError(
            "AZURE_SEARCH_INDEX_NAME environment variable is not set"
        )
    return index_name


@traced_and_logged
def azure_search_initialize_clients(
    endpoint: str | None = None,
    api_key: str | None = None,
    index_name: str | None = None,
) -> dict[str, Any]:
    """Initialize Azure AI Search clients.

    Args:
        endpoint: The Azure AI Search service endpoint URL (defaults to AZURE_SEARCH_ENDPOINT env var)
        api_key: The Azure AI Search API key (defaults to AZURE_SEARCH_API_KEY env var)
        index_name: Optional index name for SearchClient initialization (defaults to AZURE_SEARCH_INDEX_NAME env var if not None)

    Returns:
        Dictionary containing the initialized clients
    """
    # Use environment variables as defaults if not provided
    endpoint = endpoint or _get_default_endpoint()
    api_key = api_key or _get_default_api_key()

    credential = AzureKeyCredential(api_key)

    # Create the search index client
    search_index_client = SearchIndexClient(
        endpoint=endpoint, credential=credential
    )

    # Create clients dictionary
    clients = {
        "index_client": search_index_client,
    }

    # Add search client if index_name was provided or available in env
    if index_name is None and os.environ.get("AZURE_SEARCH_INDEX_NAME"):
        index_name = _get_default_index_name()

    if index_name:
        search_client = SearchClient(
            endpoint=endpoint, index_name=index_name, credential=credential
        )
        clients["search_client"] = search_client

    return clients


@traced_and_logged
def azure_search_create_index(
    index_name: str | None = None,
    fields: list[SearchField] = None,
    vector_search: VectorSearch | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create a new search index in Azure AI Search.

    Args:
        index_name: Name of the search index to create (defaults to AZURE_SEARCH_INDEX_NAME env var)
        fields: List of field definitions for the index
        vector_search: Optional vector search configuration
        endpoint: The Azure AI Search service endpoint URL (defaults to AZURE_SEARCH_ENDPOINT env var)
        api_key: The Azure AI Search API key (defaults to AZURE_SEARCH_API_KEY env var)

    Returns:
        Dictionary containing information about the created index
    """
    # Use environment variables as defaults if not provided
    endpoint = endpoint or _get_default_endpoint()
    api_key = api_key or _get_default_api_key()
    index_name = index_name or _get_default_index_name()

    if fields is None:
        raise ValueError("Fields must be provided for index creation")

    clients = azure_search_initialize_clients(endpoint, api_key)
    index_client = clients["index_client"]

    # Create the index
    index = SearchIndex(
        name=index_name, fields=fields, vector_search=vector_search
    )

    result = index_client.create_or_update_index(index)

    return {
        "index_name": result.name,
        "fields": [field.name for field in result.fields],
        "created": True,
    }


@traced_and_logged
def azure_search_upload_documents(
    documents: list[dict[str, Any]],
    index_name: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Upload documents to an Azure AI Search index.

    Args:
        documents: List of documents to upload (as dictionaries)
        index_name: Name of the search index (defaults to AZURE_SEARCH_INDEX_NAME env var)
        endpoint: The Azure AI Search service endpoint URL (defaults to AZURE_SEARCH_ENDPOINT env var)
        api_key: The Azure AI Search API key (defaults to AZURE_SEARCH_API_KEY env var)

    Returns:
        Dictionary containing the upload results
    """
    # Use environment variables as defaults if not provided
    endpoint = endpoint or _get_default_endpoint()
    api_key = api_key or _get_default_api_key()
    index_name = index_name or _get_default_index_name()

    clients = azure_search_initialize_clients(endpoint, api_key, index_name)
    search_client = clients["search_client"]

    result = search_client.upload_documents(documents=documents)

    # Process results
    succeeded = sum(1 for r in result if r.succeeded)

    return {
        "succeeded": succeeded,
        "failed": len(result) - succeeded,
        "total": len(result),
    }


@traced_and_logged
def azure_search_query(
    search_text: str | None = None,
    filter: str | None = None,
    select: list[str] | None = None,
    top: int | None = 50,
    vector: list[float] | None = None,
    vector_field: str | None = None,
    vector_k: int | None = 10,
    index_name: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Search documents in an Azure AI Search index.

    Args:
        search_text: Optional text to search for (keyword search)
        filter: Optional OData filter expression
        select: Optional list of fields to return
        top: Maximum number of results to return
        vector: Optional vector for vector search
        vector_field: Name of the field containing vectors for vector search
        vector_k: Number of nearest neighbors to retrieve in vector search
        index_name: Name of the search index (defaults to AZURE_SEARCH_INDEX_NAME env var)
        endpoint: The Azure AI Search service endpoint URL (defaults to AZURE_SEARCH_ENDPOINT env var)
        api_key: The Azure AI Search API key (defaults to AZURE_SEARCH_API_KEY env var)

    Returns:
        List of search results as dictionaries
    """
    # Use environment variables as defaults if not provided
    endpoint = endpoint or _get_default_endpoint()
    api_key = api_key or _get_default_api_key()
    index_name = index_name or _get_default_index_name()

    clients = azure_search_initialize_clients(endpoint, api_key, index_name)
    search_client = clients["search_client"]

    # Set up vector query if vector is provided
    vectorized_query = None
    if vector and vector_field:
        vectorized_query = VectorizedQuery(
            vector=vector, k=vector_k, fields=[vector_field]
        )

    # Execute the search
    results = search_client.search(
        search_text=search_text,
        filter=filter,
        select=select,
        top=top,
        vector_queries=[vectorized_query] if vectorized_query else None,
    )

    # Convert results to list of dictionaries
    result_list = [dict(result) for result in results]

    return result_list


@traced_and_logged
def azure_search_get_document(
    key: str,
    select: list[str] | None = None,
    index_name: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Retrieve a specific document from an Azure AI Search index by key.

    Args:
        key: The unique key of the document to retrieve
        select: Optional list of fields to return
        index_name: Name of the search index (defaults to AZURE_SEARCH_INDEX_NAME env var)
        endpoint: The Azure AI Search service endpoint URL (defaults to AZURE_SEARCH_ENDPOINT env var)
        api_key: The Azure AI Search API key (defaults to AZURE_SEARCH_API_KEY env var)

    Returns:
        The retrieved document as a dictionary
    """
    # Use environment variables as defaults if not provided
    endpoint = endpoint or _get_default_endpoint()
    api_key = api_key or _get_default_api_key()
    index_name = index_name or _get_default_index_name()

    clients = azure_search_initialize_clients(endpoint, api_key, index_name)
    search_client = clients["search_client"]

    result = search_client.get_document(key=key, selected_fields=select)

    return dict(result)


@traced_and_logged
def azure_search_delete_documents(
    keys: list[str],
    key_field_name: str = "id",
    index_name: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Delete documents from an Azure AI Search index.

    Args:
        keys: List of document keys to delete
        key_field_name: Name of the key field (defaults to "id")
        index_name: Name of the search index (defaults to AZURE_SEARCH_INDEX_NAME env var)
        endpoint: The Azure AI Search service endpoint URL (defaults to AZURE_SEARCH_ENDPOINT env var)
        api_key: The Azure AI Search API key (defaults to AZURE_SEARCH_API_KEY env var)

    Returns:
        Dictionary containing the deletion results
    """
    # Use environment variables as defaults if not provided
    endpoint = endpoint or _get_default_endpoint()
    api_key = api_key or _get_default_api_key()
    index_name = index_name or _get_default_index_name()

    clients = azure_search_initialize_clients(endpoint, api_key, index_name)
    search_client = clients["search_client"]

    # Format documents for deletion (only need the key field)
    documents_to_delete = [{key_field_name: key} for key in keys]

    result = search_client.delete_documents(documents=documents_to_delete)

    # Process results
    succeeded = sum(1 for r in result if r.succeeded)

    return {
        "succeeded": succeeded,
        "failed": len(result) - succeeded,
        "total": len(result),
    }


@traced_and_logged
def azure_search_list_indexes(
    endpoint: str | None = None, api_key: str | None = None
) -> list[dict[str, Any]]:
    """List all indexes in the Azure AI Search service.

    Args:
        endpoint: The Azure AI Search service endpoint URL (defaults to AZURE_SEARCH_ENDPOINT env var)
        api_key: The Azure AI Search API key (defaults to AZURE_SEARCH_API_KEY env var)

    Returns:
        List of indexes as dictionaries
    """
    # Use environment variables as defaults if not provided
    endpoint = endpoint or _get_default_endpoint()
    api_key = api_key or _get_default_api_key()

    clients = azure_search_initialize_clients(endpoint, api_key)
    index_client = clients["index_client"]

    result = index_client.list_indexes()

    # Convert index objects to dictionaries with basic information
    indexes = [
        {
            "name": index.name,
            "fields": [field.name for field in index.fields],
            "field_count": len(index.fields),
        }
        for index in result
    ]

    return indexes


@traced_and_logged
def azure_search_get_index_statistics(
    index_name: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Get statistics for a specific Azure AI Search index.

    Args:
        index_name: Name of the search index (defaults to AZURE_SEARCH_INDEX_NAME env var)
        endpoint: The Azure AI Search service endpoint URL (defaults to AZURE_SEARCH_ENDPOINT env var)
        api_key: The Azure AI Search API key (defaults to AZURE_SEARCH_API_KEY env var)

    Returns:
        Dictionary containing index statistics
    """
    # Use environment variables as defaults if not provided
    endpoint = endpoint or _get_default_endpoint()
    api_key = api_key or _get_default_api_key()
    index_name = index_name or _get_default_index_name()

    clients = azure_search_initialize_clients(endpoint, api_key, index_name)
    search_client = clients["search_client"]

    stats = search_client.get_document_count()

    return {"document_count": stats}


@traced_and_logged
def azure_search_create_vector_index(
    fields: list[dict[str, Any]],
    vector_dimensions: int,
    index_name: str | None = None,
    algorithm_kind: str = "hnsw",
    endpoint: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create a vector search index in Azure AI Search.

    Args:
        fields: List of field configurations (dicts with name, type, etc.)
        vector_dimensions: Dimensions of the vector field
        index_name: Name of the search index (defaults to AZURE_SEARCH_INDEX_NAME env var)
        algorithm_kind: Vector search algorithm ("hnsw" or "exhaustive")
        endpoint: The Azure AI Search service endpoint URL (defaults to AZURE_SEARCH_ENDPOINT env var)
        api_key: The Azure AI Search API key (defaults to AZURE_SEARCH_API_KEY env var)

    Returns:
        Dictionary with index creation result
    """
    # Use environment variables as defaults if not provided
    endpoint = endpoint or _get_default_endpoint()
    api_key = api_key or _get_default_api_key()
    index_name = index_name or _get_default_index_name()

    clients = azure_search_initialize_clients(endpoint, api_key)
    index_client = clients["index_client"]

    # Convert field configurations to SearchField objects
    index_fields = []
    vector_fields = []

    for field_config in fields:
        field_name = field_config["name"]
        field_type = field_config["type"]
        field_searchable = field_config.get("searchable", False)
        field_filterable = field_config.get("filterable", False)
        field_sortable = field_config.get("sortable", False)
        field_key = field_config.get("key", False)
        field_vector = field_config.get("vector", False)

        if field_searchable and field_type == "string":
            field = SearchableField(
                name=field_name,
                type=SearchFieldDataType.String,
                key=field_key,
                filterable=field_filterable,
                sortable=field_sortable,
            )
        else:
            data_type = None
            if field_type == "string":
                data_type = SearchFieldDataType.String
            elif field_type == "int":
                data_type = SearchFieldDataType.Int32
            elif field_type == "double":
                data_type = SearchFieldDataType.Double
            elif field_type == "boolean":
                data_type = SearchFieldDataType.Boolean
            elif field_type == "collection":
                data_type = SearchFieldDataType.Collection(
                    SearchFieldDataType.String
                )

            field = SimpleField(
                name=field_name,
                type=data_type,
                key=field_key,
                filterable=field_filterable,
                sortable=field_sortable,
            )

        index_fields.append(field)

        if field_vector:
            vector_fields.append(field_name)

    # Set up vector search configuration
    algorithm_config = None
    if algorithm_kind.lower() == "hnsw":
        algorithm_config = HnswAlgorithmConfiguration(
            name="hnsw-config",
            parameters={"m": 4, "efConstruction": 400, "efSearch": 500},
        )
    else:
        algorithm_config = ExhaustiveKnnAlgorithmConfiguration(
            name="exhaustive-config"
        )

    # Create vector search configuration
    vector_search = VectorSearch(
        algorithms=[algorithm_config],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name=algorithm_config.name,
            )
        ],
    )

    # Create the search index
    index = SearchIndex(
        name=index_name, fields=index_fields, vector_search=vector_search
    )

    try:
        result = index_client.create_or_update_index(index)
        return {
            "index_name": result.name,
            "vector_fields": vector_fields,
            "vector_dimensions": vector_dimensions,
            "algorithm": algorithm_kind,
            "created": True,
        }
    except Exception as e:
        return {"error": str(e), "created": False}
