from __future__ import annotations

from typing import Any

from .vector_base import VectorAdapter, VectorHit


class AzureSearchAdapter(VectorAdapter):
    """Adapter for Azure Cognitive Search vector capabilities."""

    def __init__(
        self,
        *,
        endpoint: str,
        key: str,
        index_name: str,
        embedding_field: str = "embedding",
    ) -> None:
        super().__init__()
        try:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient
        except ImportError as e:
            raise RuntimeError("azure-search-documents package is required for AzureSearchAdapter") from e

        self._client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(key),
        )
        self._embedding_field = embedding_field

    # -----------------------------
    def add(
        self,
        *,
        id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        document = {
            "id": id,
            "content": content,
            self._embedding_field: embedding,
            **(metadata or {}),
        }
        # Upload is sync but returns iterator; consume to check errors
        list(self._client.upload_documents(documents=[document]))

    def query(self, *, embedding: list[float], k: int) -> list[VectorHit]:
        results = self._client.search(
            search_text=None,
            vector=embedding,
            k=k,
            vector_fields=self._embedding_field,
        )
        hits: list[VectorHit] = []
        for doc in results:
            hits.append(
                VectorHit(
                    id=doc["id"],
                    content=doc.get("content"),
                    metadata={k: v for k, v in doc.items() if k not in ("id", "content", self._embedding_field, "@search.score")},
                    score=doc["@search.score"],
                )
            )
        return hits
