"""DSPy signature building from output specifications.

Phase 6: Extracted from dspy_engine.py to reduce file size and improve modularity.

This module handles all signature-related logic for DSPy program execution,
including semantic field naming, pluralization, batching, and fan-out support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flock.core.artifacts import Artifact
from flock.logging.logging import get_logger
from flock.registry import type_registry
from flock.utils.runtime import EvalInputs


if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import BaseModel


logger = get_logger(__name__)


class DSPySignatureBuilder:
    """Builds DSPy signatures from output group specifications.

    Responsibilities:
    - Convert Pydantic models to snake_case field names
    - Pluralize field names for batching and fan-out
    - Generate DSPy signatures with semantic naming
    - Build execution payloads matching signatures
    - Extract outputs from predictions
    """

    def _type_to_field_name(self, type_class: type) -> str:
        """Convert Pydantic model class name to snake_case field name.

        Examples:
            Movie → "movie"
            ResearchQuestion → "research_question"
            APIResponse → "api_response"
            UserAuthToken → "user_auth_token"

        Args:
            type_class: The Pydantic model class

        Returns:
            snake_case field name
        """
        import re

        name = type_class.__name__
        # Convert CamelCase to snake_case
        snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        return snake_case

    def _pluralize(self, field_name: str) -> str:
        """Convert singular field name to plural for lists.

        Examples:
            "idea" → "ideas"
            "movie" → "movies"
            "story" → "stories" (y → ies)
            "analysis" → "analyses" (is → es)
            "research_question" → "research_questions"

        Args:
            field_name: Singular field name in snake_case

        Returns:
            Pluralized field name
        """
        # Simple English pluralization rules
        if (
            field_name.endswith("y")
            and len(field_name) > 1
            and field_name[-2] not in "aeiou"
        ):
            # story → stories (consonant + y)
            return field_name[:-1] + "ies"
        if field_name.endswith(("s", "x", "z", "ch", "sh")):
            # analysis → analyses, box → boxes
            return field_name + "es"
        # idea → ideas, movie → movies
        return field_name + "s"

    def _needs_multioutput_signature(self, output_group) -> bool:
        """Determine if OutputGroup requires multi-output signature generation.

        Args:
            output_group: OutputGroup to analyze

        Returns:
            True if multi-output signature needed, False for single output
        """
        if (
            not output_group
            or not hasattr(output_group, "outputs")
            or not output_group.outputs
        ):
            return False

        # Multiple different types → multi-output
        if len(output_group.outputs) > 1:
            return True

        # Fan-out (single type, count > 1) → multi-output
        if output_group.outputs[0].count > 1:
            return True

        return False

    def _prepare_signature_with_context(
        self,
        dspy_mod,
        *,
        description: str | None,
        input_schema: type[BaseModel] | None,
        output_schema: type[BaseModel] | None,
        has_context: bool = False,
        batched: bool = False,
    ) -> Any:
        """Prepare DSPy signature, optionally including context field."""
        fields = {
            "description": (str, dspy_mod.InputField()),
        }

        # Add context field if we have conversation history
        if has_context:
            fields["context"] = (
                list,
                dspy_mod.InputField(
                    desc="Previous conversation artifacts providing context for this request"
                ),
            )

        if batched:
            if input_schema is not None:
                input_type = list[input_schema]
            else:
                input_type = list[dict[str, Any]]
        else:
            input_type = input_schema or dict

        fields["input"] = (input_type, dspy_mod.InputField())
        fields["output"] = (output_schema or dict, dspy_mod.OutputField())

        signature = dspy_mod.Signature(fields)

        instruction = (
            description or "Produce a valid output that matches the 'output' schema."
        )
        if has_context:
            instruction += (
                " Consider the conversation context provided to inform your response."
            )
        if batched:
            instruction += (
                " The 'input' field will contain a list of items representing the batch; "
                "process the entire collection coherently."
            )

        return signature.with_instructions(instruction)

    def prepare_signature_for_output_group(
        self,
        dspy_mod,
        *,
        agent,
        inputs: EvalInputs,
        output_group,
        has_context: bool = False,
        batched: bool = False,
        engine_instructions: str | None = None,
    ) -> Any:
        """Prepare DSPy signature dynamically based on OutputGroup with semantic field names.

        This method generates signatures using semantic field naming:
        - Type names → snake_case field names (Task → "task", ResearchQuestion → "research_question")
        - Pluralization for fan-out (Idea → "ideas" for lists)
        - Pluralization for batching (Task → "tasks" for list[Task])
        - Multi-input support for joins (multiple input artifacts with semantic names)
        - Collision handling (same input/output type → prefix with "input_" or "output_")

        Examples:
            Single output: .consumes(Task).publishes(Report)
            → {"task": (Task, InputField()), "report": (Report, OutputField())}

            Multiple inputs (joins): .consumes(Document, Guidelines).publishes(Report)
            → {"document": (Document, InputField()), "guidelines": (Guidelines, InputField()),
               "report": (Report, OutputField())}

            Multiple outputs: .consumes(Task).publishes(Summary, Analysis)
            → {"task": (Task, InputField()), "summary": (Summary, OutputField()),
               "analysis": (Analysis, OutputField())}

            Fan-out: .publishes(Idea, fan_out=5)
            → {"topic": (Topic, InputField()), "ideas": (list[Idea], OutputField(...))}

            Batching: evaluate_batch([task1, task2, task3])
            → {"tasks": (list[Task], InputField()), "reports": (list[Report], OutputField())}

        Args:
            dspy_mod: DSPy module
            agent: Agent instance
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what to generate
            has_context: Whether conversation context should be included
            batched: Whether this is a batch evaluation (pluralizes input fields)
            engine_instructions: Optional override for engine instructions

        Returns:
            DSPy Signature with semantic field names
        """
        fields = {
            "description": (str, dspy_mod.InputField()),
        }

        # Add context field if we have conversation history
        if has_context:
            fields["context"] = (
                list,
                dspy_mod.InputField(
                    desc="Previous conversation artifacts providing context for this request"
                ),
            )

        # Track used field names for collision detection
        used_field_names: set[str] = {"description", "context"}

        # 1. Generate INPUT fields with semantic names
        #    Multi-input support: handle all input artifacts for joins
        #    Batching support: pluralize field names and use list[Type] when batched=True
        if inputs.artifacts:
            # Collect unique input types (avoid duplicates if multiple artifacts of same type)
            input_types_seen: dict[type, list[Artifact]] = {}
            for artifact in inputs.artifacts:
                input_model = self._resolve_input_model(artifact)
                if input_model is not None:
                    if input_model not in input_types_seen:
                        input_types_seen[input_model] = []
                    input_types_seen[input_model].append(artifact)

            # Generate fields for each unique input type
            for input_model, artifacts_of_type in input_types_seen.items():
                field_name = self._type_to_field_name(input_model)

                # Handle batching: pluralize field name and use list[Type]
                if batched:
                    field_name = self._pluralize(field_name)
                    input_type = list[input_model]
                    desc = f"Batch of {input_model.__name__} instances to process"
                    fields[field_name] = (input_type, dspy_mod.InputField(desc=desc))
                else:
                    # Single input: use singular field name
                    input_type = input_model
                    fields[field_name] = (input_type, dspy_mod.InputField())

                used_field_names.add(field_name)

            # Fallback: if we couldn't resolve any types, use generic "input"
            if not input_types_seen:
                fields["input"] = (dict, dspy_mod.InputField())
                used_field_names.add("input")

        # 2. Generate OUTPUT fields with semantic names
        for output_decl in output_group.outputs:
            output_schema = output_decl.spec.model
            type_name = output_decl.spec.type_name

            # Generate semantic field name
            field_name = self._type_to_field_name(output_schema)

            # Handle fan-out: pluralize field name and use list[Type]
            if output_decl.count > 1:
                field_name = self._pluralize(field_name)
                output_type = list[output_schema]

                # Create description with count hint
                desc = f"Generate exactly {output_decl.count} {type_name} instances"
                if output_decl.group_description:
                    desc = f"{desc}. {output_decl.group_description}"

                fields[field_name] = (output_type, dspy_mod.OutputField(desc=desc))
            else:
                # Single output
                output_type = output_schema

                # Handle collision: if field name already used, prefix with "output_"
                if field_name in used_field_names:
                    field_name = f"output_{field_name}"

                desc = f"{type_name} output"
                if output_decl.group_description:
                    desc = output_decl.group_description

                fields[field_name] = (output_type, dspy_mod.OutputField(desc=desc))

            used_field_names.add(field_name)

        # 3. Create signature
        signature = dspy_mod.Signature(fields)

        # 4. Build instruction
        description = engine_instructions or agent.description
        instruction = (
            description
            or f"Process input and generate {len(output_group.outputs)} outputs."
        )

        if has_context:
            instruction += (
                " Consider the conversation context provided to inform your response."
            )

        # Add batching hint
        if batched:
            instruction += " Process the batch of inputs coherently, generating outputs for each item."

        # Add semantic field names to instruction for clarity
        output_field_names = [
            name for name in fields.keys() if name not in {"description", "context"}
        ]
        if len(output_field_names) > 2:  # Multiple outputs
            instruction += f" Generate ALL output fields as specified: {', '.join(output_field_names[1:])}."

        return signature.with_instructions(instruction)

    def prepare_execution_payload_for_output_group(
        self,
        inputs: EvalInputs,
        output_group,
        *,
        batched: bool,
        has_context: bool,
        context_history: list | None,
        sys_desc: str,
    ) -> dict[str, Any]:
        """Prepare execution payload with semantic field names matching signature.

        This method builds a payload dict with semantic field names that match the signature
        generated by `prepare_signature_for_output_group()`.

        Args:
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup (not used here but kept for symmetry)
            batched: Whether this is a batch evaluation
            has_context: Whether conversation context should be included
            context_history: Optional conversation history
            sys_desc: System description for the "description" field

        Returns:
            Dict with semantic field names ready for DSPy program execution

        Examples:
            Single input: {"description": desc, "task": {...}}
            Multi-input: {"description": desc, "task": {...}, "topic": {...}}
            Batched: {"description": desc, "tasks": [{...}, {...}, {...}]}
        """
        payload = {"description": sys_desc}

        # Add context if present
        if has_context and context_history:
            payload["context"] = context_history

        # Build semantic input fields
        if inputs.artifacts:
            # Collect unique input types (same logic as signature generation)
            input_types_seen: dict[type, list[Artifact]] = {}
            for artifact in inputs.artifacts:
                input_model = self._resolve_input_model(artifact)
                if input_model is not None:
                    if input_model not in input_types_seen:
                        input_types_seen[input_model] = []
                    input_types_seen[input_model].append(artifact)

            # Generate payload fields for each unique input type
            for input_model, artifacts_of_type in input_types_seen.items():
                field_name = self._type_to_field_name(input_model)

                # Validate and prepare payloads
                validated_payloads = [
                    self._validate_input_payload(input_model, art.payload)
                    for art in artifacts_of_type
                ]

                if batched:
                    # Batch mode: pluralize field name and use list
                    field_name = self._pluralize(field_name)
                    payload[field_name] = validated_payloads
                else:
                    # Single mode: use first (or only) artifact
                    # For multi-input joins, we have one artifact per type
                    payload[field_name] = (
                        validated_payloads[0] if validated_payloads else {}
                    )

        return payload

    def extract_multi_output_payload(self, prediction, output_group) -> dict[str, Any]:
        """Extract semantic fields from DSPy Prediction for multi-output scenarios.

        Maps semantic field names (e.g., "movie", "ideas") back to type names (e.g., "Movie", "Idea")
        for artifact materialization compatibility.

        Args:
            prediction: DSPy Prediction object with semantic field names
            output_group: OutputGroup defining expected outputs

        Returns:
            Dict mapping type names to extracted values

        Examples:
            Prediction(movie={...}, summary={...})
            → {"Movie": {...}, "Summary": {...}}

            Prediction(ideas=[{...}, {...}, {...}])
            → {"Idea": [{...}, {...}, {...}]}
        """
        payload = {}

        for output_decl in output_group.outputs:
            output_schema = output_decl.spec.model
            type_name = output_decl.spec.type_name

            # Generate the same semantic field name used in signature
            field_name = self._type_to_field_name(output_schema)

            # Handle fan-out: field name is pluralized
            if output_decl.count > 1:
                field_name = self._pluralize(field_name)

            # Extract value from Prediction
            if hasattr(prediction, field_name):
                value = getattr(prediction, field_name)

                # Store using type_name as key (for _select_output_payload compatibility)
                payload[type_name] = value
            else:
                # Fallback: try with "output_" prefix (collision handling)
                prefixed_name = f"output_{field_name}"
                if hasattr(prediction, prefixed_name):
                    value = getattr(prediction, prefixed_name)
                    payload[type_name] = value

        return payload

    def _resolve_input_model(self, artifact: Artifact) -> type[BaseModel] | None:
        """Resolve artifact type to Pydantic model."""
        try:
            return type_registry.resolve(artifact.type)
        except KeyError:
            return None

    def _validate_input_payload(
        self,
        schema: type[BaseModel] | None,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Validate and normalize input payload against schema."""
        data = dict(payload or {})
        if schema is None:
            return data
        try:
            return schema(**data).model_dump()
        except Exception:
            return data


__all__ = ["DSPySignatureBuilder"]
