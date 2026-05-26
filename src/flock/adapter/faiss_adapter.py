from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .vector_base import VectorAdapter, VectorHit


class FAISSAdapter(VectorAdapter):
    """Simple on-disk FAISS vector store.

    Index is stored in `index_path` (flat L2).  Metadata & content are kept in a
    parallel JSONL file for quick prototyping; not optimised for massive scale.
    """

    def __init__(self, *, index_path: str = "./faiss.index") -> None:
        super().__init__()
        try:
            import faiss  # type: ignore
        except ImportError as e:
            raise RuntimeError("faiss library is required for FAISSAdapter") from e

        self._faiss = __import__("faiss")  # lazy alias
        self._index_path = Path(index_path)
        self._meta_path = self._index_path.with_suffix(".meta.jsonl")
        self._metadata: dict[int, dict[str, Any]] = {}

        if self._index_path.exists():
            self._index = self._faiss.read_index(str(self._index_path))
            # Load metadata
            if self._meta_path.exists():
                import json

                with open(self._meta_path) as f:
                    for line_no, line in enumerate(f):
                        self._metadata[line_no] = json.loads(line)
        else:
            self._index = None  # created on first add

    # -----------------------------
    def _ensure_index(self, dim: int):
        if self._index is None:
            self._index = self._faiss.IndexFlatL2(dim)

    def add(
        self,
        *,
        id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        import json

        vec = np.array([embedding], dtype="float32")
        self._ensure_index(vec.shape[1])
        self._index.add(vec)
        # Row id is current size - 1
        row_id = self._index.ntotal - 1
        self._metadata[row_id] = {
            "id": id,
            "content": content,
            "metadata": metadata or {},
        }
        # Append metadata to file for persistence
        self._meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._meta_path, "a") as f:
            f.write(json.dumps(self._metadata[row_id]) + "\n")
        # Persist index lazily every 100 inserts
        if row_id % 100 == 0:
            self._faiss.write_index(self._index, str(self._index_path))

    def query(self, *, embedding: list[float], k: int) -> list[VectorHit]:
        if self._index is None or self._index.ntotal == 0:
            return []
        vec = np.array([embedding], dtype="float32")
        distances, indices = self._index.search(vec, k)
        hits: list[VectorHit] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            meta = self._metadata.get(idx, {})
            hits.append(
                VectorHit(
                    id=meta.get("id", str(idx)),
                    content=meta.get("content"),
                    metadata=meta.get("metadata", {}),
                    score=1 - float(dist),  # approximate similarity
                )
            )
        return hits

    def close(self) -> None:
        if self._index is not None:
            self._faiss.write_index(self._index, str(self._index_path))
