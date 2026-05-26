from __future__ import annotations

from pathlib import Path
from typing import Any

from .vector_base import VectorAdapter, VectorHit


class ChromaAdapter(VectorAdapter):
    """Adapter for Chroma vector DB (local or HTTP)."""

    def __init__(
        self,
        *,
        collection: str = "flock_memories",
        host: str | None = None,
        port: int = 8000,
        path: str | None = "./vector_store",
    ) -> None:
        super().__init__()
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as e:
            raise RuntimeError("chromadb is required for ChromaAdapter") from e

        if host:
            client = chromadb.HttpClient(host=host, port=port)
        else:
            p = Path(path or "./vector_store")
            p.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(settings=Settings(path=str(p)))

        self._collection = client.get_or_create_collection(collection)

    # -------------------------------
    # VectorAdapter implementation
    # -------------------------------
    def add(
        self,
        *,
        id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._collection.add(
            ids=[id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata or {}],
        )

    def query(self, *, embedding: list[float], k: int) -> list[VectorHit]:
        res = self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            include=["documents", "metadatas", "distances", "ids"],
        )
        hits: list[VectorHit] = []
        if res and res["ids"]:
            for idx in range(len(res["ids"][0])):
                dist = res["distances"][0][idx]
                score = 1 - dist  # Convert L2 → similarity
                hits.append(
                    VectorHit(
                        id=res["ids"][0][idx],
                        content=res["documents"][0][idx],
                        metadata=res["metadatas"][0][idx],
                        score=score,
                    )
                )
        return hits
