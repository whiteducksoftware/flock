"""Contract tests for Agent._select_payload() with type normalization.

This test file validates that engine-produced artifacts with simple type names
are correctly matched with agent output declarations (qualified type names).
"""

from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.core import AgentOutput, Flock
from flock.core.artifacts import Artifact, ArtifactSpec
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@pytest.mark.asyncio
class TestAgentPayloadSelectionContract:
    """Contract tests for Agent._select_payload() type normalization."""

    def setup_method(self):
        """Save registry state."""
        self._saved_by_name = type_registry._by_name.copy()
        self._saved_by_cls = type_registry._by_cls.copy()

    def teardown_method(self):
        """Restore registry state."""
        type_registry._by_name.clear()
        type_registry._by_cls.clear()
        type_registry._by_name.update(self._saved_by_name)
        type_registry._by_cls.update(self._saved_by_cls)

    async def test_simple_name_matches_qualified_declaration(self):
        """P1: Engine artifact with simple name matches agent's qualified output."""

        @flock_type
        class Output(BaseModel):
            result: str

        canonical = type_registry.name_for(
            Output
        )  # e.g., "test_agent_payload_selection_contract.Output"

        orchestrator = Flock()
        agent_builder = orchestrator.agent("test").publishes(Output)
        agent = agent_builder._agent  # Get underlying Agent instance

        # Create output declaration (agent expects canonical name)
        output_decl = AgentOutput(
            spec=ArtifactSpec(type_name=canonical, model=Output),
            default_visibility=PublicVisibility(),
        )

        # Simulate engine producing artifact with simple name
        engine_artifact = Artifact(
            id=uuid4(),
            type="Output",  # Simple name from engine
            payload={"result": "success"},
            produced_by=agent.name,
            visibility=PublicVisibility(),
        )

        result = EvalResult(artifacts=[engine_artifact], state={})

        # This will FAIL initially - _select_payload doesn't normalize
        payload = agent._select_payload(output_decl, result)
        assert payload is not None
        assert payload["result"] == "success"

    async def test_qualified_name_matches_qualified_declaration(self):
        """P2: Engine artifact with qualified name matches (baseline behavior)."""

        @flock_type
        class Output(BaseModel):
            result: str

        canonical = type_registry.name_for(Output)

        orchestrator = Flock()
        agent_builder = orchestrator.agent("test").publishes(Output)
        agent = agent_builder._agent

        output_decl = AgentOutput(
            spec=ArtifactSpec(type_name=canonical, model=Output),
            default_visibility=PublicVisibility(),
        )

        # Engine produces artifact with canonical name
        engine_artifact = Artifact(
            id=uuid4(),
            type=canonical,  # Qualified name
            payload={"result": "success"},
            produced_by=agent.name,
            visibility=PublicVisibility(),
        )

        result = EvalResult(artifacts=[engine_artifact], state={})

        # This should work (baseline)
        payload = agent._select_payload(output_decl, result)
        assert payload is not None
        assert payload["result"] == "success"

    async def test_non_matching_type_returns_none(self):
        """P3: Non-matching types return None."""

        @flock_type
        class Output(BaseModel):
            result: str

        @flock_type
        class WrongOutput(BaseModel):
            data: str

        orchestrator = Flock()
        agent_builder = orchestrator.agent("test").publishes(Output)
        agent = agent_builder._agent

        canonical = type_registry.name_for(Output)
        output_decl = AgentOutput(
            spec=ArtifactSpec(type_name=canonical, model=Output),
            default_visibility=PublicVisibility(),
        )

        engine_artifact = Artifact(
            id=uuid4(),
            type="WrongOutput",
            payload={"data": "test"},
            produced_by=agent.name,
            visibility=PublicVisibility(),
        )

        result = EvalResult(artifacts=[engine_artifact], state={})

        payload = agent._select_payload(output_decl, result)
        assert payload is None

    async def test_cross_context_matching(self):
        """P4: Artifacts from __main__ match test context declarations."""

        # Simulate class from __main__
        class Document(BaseModel):
            content: str

        type_registry.register(Document, name="__main__.Document")

        orchestrator = Flock()
        agent_builder = orchestrator.agent("test")
        agent = agent_builder._agent

        # Agent declares it publishes __main__.Document (as registered)
        output_decl = AgentOutput(
            spec=ArtifactSpec(type_name="__main__.Document", model=Document),
            default_visibility=PublicVisibility(),
        )

        # Engine produces artifact with simple name
        engine_artifact = Artifact(
            id=uuid4(),
            type="Document",  # Simple name
            payload={"content": "test"},
            produced_by=agent.name,
            visibility=PublicVisibility(),
        )

        result = EvalResult(artifacts=[engine_artifact], state={})

        # This will FAIL initially
        payload = agent._select_payload(output_decl, result)
        assert payload is not None
        assert payload["content"] == "test"
