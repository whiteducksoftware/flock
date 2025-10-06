"""Contract tests for artifact storage and retrieval with type normalization.

This test file validates that artifacts stored with fully qualified names
can be retrieved using simple names after type normalization.
"""

import pytest
from pydantic import BaseModel

from flock.artifacts import Artifact
from flock.registry import flock_type, type_registry
from flock.store import InMemoryBlackboardStore
from flock.visibility import PublicVisibility


@pytest.mark.asyncio
class TestArtifactStorageContract:
    """Contract tests for artifact storage with type normalization."""

    def setup_method(self):
        """Create fresh store and save registry state."""
        self.store = InMemoryBlackboardStore()
        self._saved_by_name = type_registry._by_name.copy()
        self._saved_by_cls = type_registry._by_cls.copy()

    def teardown_method(self):
        """Restore registry state."""
        type_registry._by_name.clear()
        type_registry._by_cls.clear()
        type_registry._by_name.update(self._saved_by_name)
        type_registry._by_cls.update(self._saved_by_cls)

    async def test_publish_stores_with_canonical_name(self):
        """S1: Artifacts are stored with their canonical type names."""

        @flock_type
        class Document(BaseModel):
            content: str

        canonical_name = type_registry.name_for(Document)

        artifact = Artifact(
            type=canonical_name,
            payload={"content": "test"},
            produced_by="test_agent",
            visibility=PublicVisibility(),
        )

        await self.store.publish(artifact)

        # Should be able to list by canonical name
        results = await self.store.list_by_type(canonical_name)
        assert len(results) == 1
        assert results[0].payload["content"] == "test"

    async def test_list_by_simple_name_finds_qualified_artifacts(self):
        """S2: list_by_type(simple) finds artifacts stored with qualified names."""

        @flock_type
        class Document(BaseModel):
            content: str

        canonical_name = type_registry.name_for(Document)

        artifact = Artifact(
            type=canonical_name,  # Fully qualified, e.g., "test_artifact_storage_contract.Document"
            payload={"content": "test"},
            produced_by="test_agent",
            visibility=PublicVisibility(),
        )

        await self.store.publish(artifact)

        # This will FAIL initially - store doesn't normalize yet
        results = await self.store.list_by_type("Document")
        assert len(results) == 1
        assert results[0].payload["content"] == "test"

    async def test_cross_context_type_resolution(self):
        """S3: Artifacts from __main__ can be queried from test context."""

        # Simulate artifact registered in __main__ context
        # Create a class actually named "Document" to match the lookup
        class Document(BaseModel):
            title: str

        # Register it with __main__ prefix as if from main script
        type_registry.register(Document, name="__main__.Document")

        artifact = Artifact(
            type="__main__.Document",
            payload={"title": "Test"},
            produced_by="main_script",
            visibility=PublicVisibility(),
        )

        await self.store.publish(artifact)

        # Should find it by simple name
        results = await self.store.list_by_type("Document")
        assert len(results) == 1
        assert results[0].payload["title"] == "Test"

    async def test_multiple_artifacts_same_type(self):
        """S4: Multiple artifacts of same type are all retrievable."""

        @flock_type
        class Document(BaseModel):
            content: str

        canonical_name = type_registry.name_for(Document)

        artifacts = [
            Artifact(
                type=canonical_name,
                payload={"content": f"doc{i}"},
                produced_by="test_agent",
                visibility=PublicVisibility(),
            )
            for i in range(3)
        ]

        for artifact in artifacts:
            await self.store.publish(artifact)

        # This will FAIL initially
        results = await self.store.list_by_type("Document")
        assert len(results) == 3
        contents = {r.payload["content"] for r in results}
        assert contents == {"doc0", "doc1", "doc2"}
