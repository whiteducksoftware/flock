from __future__ import annotations

from typing import Any

from .vector_base import VectorAdapter, VectorHit


class PineconeAdapter(VectorAdapter):
    """Adapter for Pinecone vector DB."""

    def __init__(
        self,
        *,
        api_key: str,
        environment: str,
        index: str,
    ) -> None:
        super().__init__()
        try:
            import pinecone
        except ImportError as e:
            raise RuntimeError("pinecone-client is required for PineconeAdapter") from e

        pinecone.init(api_key=api_key, environment=environment)
        self._index = pinecone.Index(index)

    # -------------------------------
    def add(
        self,
        *,
        id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        meta = {"content": content, **(metadata or {})}
        self._index.upsert(vectors=[(id, embedding, meta)])

    def query(self, *, embedding: list[float], k: int) -> list[VectorHit]:
        res = self._index.query(vector=embedding, top_k=k, include_values=False, include_metadata=True)
        hits: list[VectorHit] = []
        for match in res.matches or []:
            hits.append(
                VectorHit(
                    id=match.id,
                    content=match.metadata.get("content") if match.metadata else None,
                    metadata={k: v for k, v in (match.metadata or {}).items() if k != "content"},
                    score=match.score,
                )
            )
        return hits
