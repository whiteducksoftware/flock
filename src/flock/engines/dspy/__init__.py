"""DSPy engine implementation modules.

Phase 6: Modularized DSPy engine implementation to improve maintainability.

This package contains extracted components from the main DSPy engine:
- SignatureBuilder: DSPy signature generation with semantic field naming
- StreamingExecutor: Streaming execution (CLI Rich display + WebSocket-only)
- ArtifactMaterializer: Output normalization and artifact creation
"""

from flock.engines.dspy.artifact_materializer import DSPyArtifactMaterializer
from flock.engines.dspy.signature_builder import DSPySignatureBuilder
from flock.engines.dspy.streaming_executor import DSPyStreamingExecutor


__all__ = [
    "DSPyArtifactMaterializer",
    "DSPySignatureBuilder",
    "DSPyStreamingExecutor",
]
