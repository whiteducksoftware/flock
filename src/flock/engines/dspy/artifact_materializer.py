"""Artifact materialization from DSPy outputs.

Phase 6: Extracted from dspy_engine.py to reduce file size and improve modularity.

This module handles conversion of DSPy Prediction outputs to Flock artifacts,
including JSON parsing, normalization, and fan-out support.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.logging.logging import get_logger


logger = get_logger(__name__)


class DSPyArtifactMaterializer:
    """Materializes Flock artifacts from DSPy program outputs.

    Responsibilities:
    - Normalize DSPy outputs (JSON parsing, BaseModel handling)
    - Select correct output payload from multi-output results
    - Create artifacts with fan-out support (count > 1)
    - Handle validation errors gracefully
    """

    def normalize_output_payload(self, raw: Any) -> dict[str, Any]:
        """Normalize raw DSPy output to dict format.

        Handles:
        - BaseModel instances → model_dump()
        - JSON strings → parsed dict
        - DSPy streaming markers like `[[ ## output ## ]]`
        - Markdown fenced code blocks
        - Extracting JSON from text

        Args:
            raw: Raw output from DSPy program

        Returns:
            Normalized dict payload
        """
        if isinstance(raw, BaseModel):
            return raw.model_dump()
        if isinstance(raw, str):
            text = raw.strip()
            candidates: list[str] = []

            # Primary attempt - full string
            if text:
                candidates.append(text)

            # Handle DSPy streaming markers like `[[ ## output ## ]]`
            if text.startswith("[[") and "]]" in text:
                _, remainder = text.split("]]", 1)
                remainder = remainder.strip()
                if remainder:
                    candidates.append(remainder)

            # Handle Markdown-style fenced blocks
            if text.startswith("```") and text.endswith("```"):
                fenced = text.strip("`").strip()
                if fenced:
                    candidates.append(fenced)

            # Extract first JSON-looking segment if present
            for opener, closer in (("{", "}"), ("[", "]")):
                start = text.find(opener)
                end = text.rfind(closer)
                if start != -1 and end != -1 and end > start:
                    segment = text[start : end + 1].strip()
                    if segment:
                        candidates.append(segment)

            seen: set[str] = set()
            for candidate in candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

            return {"text": text}
        if isinstance(raw, Mapping):
            return dict(raw)
        return {"value": raw}

    def materialize_artifacts(
        self,
        payload: dict[str, Any],
        outputs: Iterable[Any],
        produced_by: str,
        pre_generated_id: Any = None,
    ):
        """Materialize artifacts from payload, handling fan-out (count > 1).

        For fan-out outputs (count > 1), splits the list into individual artifacts.
        For single outputs (count = 1), creates one artifact from dict.

        Args:
            payload: Normalized output dict from DSPy
            outputs: AgentOutput declarations defining what to create
            produced_by: Agent name
            pre_generated_id: Pre-generated ID for streaming (only used for single outputs)

        Returns:
            Tuple of (artifacts list, errors list)
        """
        artifacts: list[Artifact] = []
        errors: list[str] = []
        for output in outputs or []:
            model_cls = output.spec.model
            data = self.select_output_payload(payload, model_cls, output.spec.type_name)

            # FAN-OUT: If count > 1, data should be a list and we create multiple artifacts
            if output.count > 1:
                if not isinstance(data, list):
                    errors.append(
                        f"Fan-out expected list for {output.spec.type_name} (count={output.count}), "
                        f"got {type(data).__name__}"
                    )
                    continue

                # Create one artifact for each item in the list
                for item_data in data:
                    try:
                        instance = model_cls(**item_data)
                    except Exception as exc:  # noqa: BLE001 - collect validation errors for logs
                        errors.append(f"{output.spec.type_name}: {exc!s}")
                        continue

                    # Fan-out artifacts auto-generate their IDs (can't reuse pre_generated_id)
                    artifact_kwargs = {
                        "type": output.spec.type_name,
                        "payload": instance.model_dump(),
                        "produced_by": produced_by,
                    }
                    artifacts.append(Artifact(**artifact_kwargs))
            else:
                # SINGLE OUTPUT: Create one artifact from dict
                try:
                    instance = model_cls(**data)
                except Exception as exc:  # noqa: BLE001 - collect validation errors for logs
                    errors.append(str(exc))
                    continue

                # Use the pre-generated ID if provided (for streaming), otherwise let Artifact auto-generate
                artifact_kwargs = {
                    "type": output.spec.type_name,
                    "payload": instance.model_dump(),
                    "produced_by": produced_by,
                }
                if pre_generated_id is not None:
                    artifact_kwargs["id"] = pre_generated_id

                artifacts.append(Artifact(**artifact_kwargs))
        return artifacts, errors

    def select_output_payload(
        self,
        payload: Mapping[str, Any],
        model_cls: type[BaseModel],
        type_name: str,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Select the correct output payload from the normalized output dict.

        Handles both simple type names and fully qualified names (with module prefix).
        Returns either a dict (single output) or list[dict] (fan-out/batch).

        Args:
            payload: Normalized output dict
            model_cls: Pydantic model class
            type_name: Type name from OutputSpec

        Returns:
            Either dict (single) or list[dict] (fan-out/batch)
        """
        candidates = [
            payload.get(type_name),  # Try exact type_name (may be "__main__.Movie")
            payload.get(model_cls.__name__),  # Try simple class name ("Movie")
            payload.get(model_cls.__name__.lower()),  # Try lowercase ("movie")
        ]

        # Extract value based on type
        for candidate in candidates:
            if candidate is not None:
                # Handle lists (fan-out and batching)
                if isinstance(candidate, list):
                    # Convert Pydantic instances to dicts
                    return [
                        item.model_dump() if isinstance(item, BaseModel) else item
                        for item in candidate
                    ]
                # Handle single Pydantic instance
                if isinstance(candidate, BaseModel):
                    return candidate.model_dump()
                # Handle dict
                if isinstance(candidate, Mapping):
                    return dict(candidate)

        # Fallback: return entire payload (will likely fail validation)
        if isinstance(payload, Mapping):
            return dict(payload)
        return {}


__all__ = ["DSPyArtifactMaterializer"]
