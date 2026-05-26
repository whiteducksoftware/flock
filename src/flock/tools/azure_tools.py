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
from azure.storage.blob import (
    BlobServiceClient,
    ContentSettings,
)

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
    # filter out the text_vector field
    result_list = [{**dict(result), "text_vector": ""} for result in results]

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


# --- Azure Blob Storage Tools ---

def _get_blob_service_client(conn_string_env_var: str) -> BlobServiceClient:
    """Helper function to get BlobServiceClient using a connection string from an environment variable."""
    actual_connection_string = os.environ.get(conn_string_env_var)
    if not actual_connection_string:
        raise ValueError(f"Environment variable '{conn_string_env_var}' for Azure Storage connection string is not set or is empty.")
    return BlobServiceClient.from_connection_string(actual_connection_string)


@traced_and_logged
def azure_storage_list_containers(conn_string_env_var: str) -> list[str]:
    """Lists all containers in the Azure Storage account.

    Args:
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.

    Returns:
        A list of container names.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    containers = blob_service_client.list_containers()
    return [container.name for container in containers]


@traced_and_logged
def azure_storage_create_container(container_name: str, conn_string_env_var: str) -> dict[str, Any]:
    """Creates a new container in the Azure Storage account.

    Args:
        container_name: The name of the container to create.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.

    Returns:
        A dictionary with creation status.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    try:
        blob_service_client.create_container(container_name)
        return {"container_name": container_name, "created": True, "message": f"Container '{container_name}' created successfully."}
    except Exception as e:
        return {"container_name": container_name, "created": False, "error": str(e)}


@traced_and_logged
def azure_storage_delete_container(container_name: str, conn_string_env_var: str) -> dict[str, Any]:
    """Deletes an existing container from the Azure Storage account.

    Args:
        container_name: The name of the container to delete.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.

    Returns:
        A dictionary with deletion status.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    try:
        blob_service_client.delete_container(container_name)
        return {"container_name": container_name, "deleted": True, "message": f"Container '{container_name}' deleted successfully."}
    except Exception as e:
        return {"container_name": container_name, "deleted": False, "error": str(e)}


@traced_and_logged
def azure_storage_list_blobs(container_name: str, conn_string_env_var: str) -> list[str]:
    """Lists all blobs in a specified container.

    Args:
        container_name: The name of the container.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.

    Returns:
        A list of blob names.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    container_client = blob_service_client.get_container_client(container_name)
    blob_list = container_client.list_blobs()
    return [blob.name for blob in blob_list]


@traced_and_logged
def azure_storage_upload_blob_text(container_name: str, blob_name: str, text_content: str, conn_string_env_var: str, overwrite: bool = True) -> dict[str, Any]:
    """Uploads text content as a blob to the specified container.

    Args:
        container_name: The name of the container.
        blob_name: The name of the blob to create.
        text_content: The string content to upload.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.
        overwrite: Whether to overwrite the blob if it already exists. Defaults to True.

    Returns:
        A dictionary with upload status.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    try:
        content_settings = ContentSettings(content_type='text/plain')
        blob_client.upload_blob(text_content.encode('utf-8'), overwrite=overwrite, content_settings=content_settings)
        return {"container_name": container_name, "blob_name": blob_name, "uploaded": True, "message": "Text content uploaded successfully."}
    except Exception as e:
        return {"container_name": container_name, "blob_name": blob_name, "uploaded": False, "error": str(e)}


@traced_and_logged
def azure_storage_upload_blob_bytes(container_name: str, blob_name: str, bytes_content: bytes, conn_string_env_var: str, overwrite: bool = True) -> dict[str, Any]:
    """Uploads bytes content as a blob to the specified container.

    Args:
        container_name: The name of the container.
        blob_name: The name of the blob to create.
        bytes_content: The bytes content to upload.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.
        overwrite: Whether to overwrite the blob if it already exists. Defaults to True.

    Returns:
        A dictionary with upload status.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    try:
        content_settings = ContentSettings(content_type='application/octet-stream')
        blob_client.upload_blob(bytes_content, overwrite=overwrite, content_settings=content_settings)
        return {"container_name": container_name, "blob_name": blob_name, "uploaded": True, "message": "Bytes content uploaded successfully."}
    except Exception as e:
        return {"container_name": container_name, "blob_name": blob_name, "uploaded": False, "error": str(e)}


@traced_and_logged
def azure_storage_upload_blob_from_file(container_name: str, blob_name: str, file_path: str, conn_string_env_var: str, overwrite: bool = True) -> dict[str, Any]:
    """Uploads a local file to a blob in the specified container.

    Args:
        container_name: The name of the container.
        blob_name: The name of the blob to create.
        file_path: The local path to the file to upload.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.
        overwrite: Whether to overwrite the blob if it already exists. Defaults to True.

    Returns:
        A dictionary with upload status.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    try:
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=overwrite)
        return {"container_name": container_name, "blob_name": blob_name, "file_path": file_path, "uploaded": True, "message": "File uploaded successfully."}
    except FileNotFoundError:
        return {"container_name": container_name, "blob_name": blob_name, "file_path": file_path, "uploaded": False, "error": "File not found."}
    except Exception as e:
        return {"container_name": container_name, "blob_name": blob_name, "file_path": file_path, "uploaded": False, "error": str(e)}


@traced_and_logged
def azure_storage_download_blob_to_text(container_name: str, blob_name: str, conn_string_env_var: str) -> str:
    """Downloads a blob's content as text.

    Args:
        container_name: The name of the container.
        blob_name: The name of the blob to download.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.

    Returns:
        The blob content as a string.

    Raises:
        Exception: If download fails or blob is not text.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    try:
        download_stream = blob_client.download_blob()
        return download_stream.readall().decode('utf-8')
    except Exception as e:
        raise Exception(f"Failed to download or decode blob '{blob_name}' from container '{container_name}': {e!s}")


@traced_and_logged
def azure_storage_download_blob_to_bytes(container_name: str, blob_name: str, conn_string_env_var: str) -> bytes:
    """Downloads a blob's content as bytes.

    Args:
        container_name: The name of the container.
        blob_name: The name of the blob to download.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.

    Returns:
        The blob content as bytes.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    download_stream = blob_client.download_blob()
    return download_stream.readall()


@traced_and_logged
def azure_storage_download_blob_to_file(container_name: str, blob_name: str, file_path: str, conn_string_env_var: str, overwrite: bool = True) -> dict[str, Any]:
    """Downloads a blob to a local file.

    Args:
        container_name: The name of the container.
        blob_name: The name of the blob to download.
        file_path: The local path to save the downloaded file.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.
        overwrite: Whether to overwrite the local file if it exists. Defaults to True.

    Returns:
        A dictionary with download status.
    """
    if not overwrite and os.path.exists(file_path):
        return {"container_name": container_name, "blob_name": blob_name, "file_path": file_path, "downloaded": False, "error": "File exists and overwrite is False."}

    blob_service_client = _get_blob_service_client(conn_string_env_var)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    try:
        with open(file_path, "wb") as download_file:
            download_stream = blob_client.download_blob()
            download_file.write(download_stream.readall())
        return {"container_name": container_name, "blob_name": blob_name, "file_path": file_path, "downloaded": True, "message": "File downloaded successfully."}
    except Exception as e:
        return {"container_name": container_name, "blob_name": blob_name, "file_path": file_path, "downloaded": False, "error": str(e)}


@traced_and_logged
def azure_storage_delete_blob(container_name: str, blob_name: str, conn_string_env_var: str) -> dict[str, Any]:
    """Deletes a specified blob from a container.

    Args:
        container_name: The name of the container.
        blob_name: The name of the blob to delete.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.

    Returns:
        A dictionary with deletion status.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    try:
        blob_client.delete_blob()
        return {"container_name": container_name, "blob_name": blob_name, "deleted": True, "message": "Blob deleted successfully."}
    except Exception as e:
        return {"container_name": container_name, "blob_name": blob_name, "deleted": False, "error": str(e)}


@traced_and_logged
def azure_storage_get_blob_properties(container_name: str, blob_name: str, conn_string_env_var: str) -> dict[str, Any]:
    """Retrieves properties of a specified blob.

    Args:
        container_name: The name of the container.
        blob_name: The name of the blob.
        conn_string_env_var: The name of the environment variable holding the Azure Storage connection string.

    Returns:
        A dictionary containing blob properties.
    """
    blob_service_client = _get_blob_service_client(conn_string_env_var)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    try:
        properties = blob_client.get_blob_properties()
        return {
            "name": properties.name,
            "container": properties.container,
            "size": properties.size,
            "content_type": properties.content_settings.content_type,
            "last_modified": properties.last_modified.isoformat() if properties.last_modified else None,
            "etag": properties.etag,
            # Add more properties as needed
        }
    except Exception as e:
        return {"container_name": container_name, "blob_name": blob_name, "error": str(e)}

# Potential future tools:
# - azure_storage_set_blob_metadata
# - azure_storage_get_blob_metadata
# - azure_storage_generate_sas_token_blob
# - azure_storage_copy_blob
