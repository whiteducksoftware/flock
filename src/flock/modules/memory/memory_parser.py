"""Parser for memory mapping declarations into executable operations."""

import re
from typing import Any

from flock.modules.memory.memory_storage import (
    CombineOperation,
    EnrichOperation,
    ExactOperation,
    FilterOperation,
    MemoryOperation,
    MemoryScope,
    SemanticOperation,
    SortOperation,
)


class MemoryMappingParser:
    """Parses memory mapping declarations into executable operations."""

    def parse(self, mapping: str) -> list[MemoryOperation]:
        """Parse a memory mapping string into operations.

        Example mappings:
        "topic -> memory.semantic(threshold=0.9) | memory.exact -> output"
        "query -> memory.semantic(scope='global') | memory.filter(recency='7d') | memory.sort(by='relevance')"
        """
        operations = []
        stages = [s.strip() for s in mapping.split("|")]

        for stage in stages:
            if "->" not in stage:
                continue

            inputs, op_spec = stage.split("->")
            inputs = [i.strip() for i in inputs.split(",")]

            if "memory." in op_spec:
                # Extract operation name and parameters
                match = re.match(r"memory\.(\w+)(?:\((.*)\))?", op_spec.strip())
                if not match:
                    continue

                op_name, params_str = match.groups()
                params = self._parse_params(params_str or "")

                # Create appropriate operation object
                if op_name == "semantic":
                    operation = SemanticOperation(
                        threshold=params.get("threshold", 0.8),
                        scope=params.get("scope", MemoryScope.BOTH),
                        max_results=params.get("max_results", 10),
                    )
                elif op_name == "exact":
                    operation = ExactOperation(
                        keys=inputs, scope=params.get("scope", MemoryScope.BOTH)
                    )
                elif op_name == "enrich":
                    operation = EnrichOperation(
                        tools=params.get("tools", []),
                        strategy=params.get("strategy", "comprehensive"),
                        scope=params.get("scope", MemoryScope.BOTH),
                    )
                elif op_name == "filter":
                    operation = FilterOperation(
                        recency=params.get("recency"),
                        relevance=params.get("relevance"),
                        metadata=params.get("metadata", {}),
                    )
                elif op_name == "sort":
                    operation = SortOperation(
                        by=params.get("by", "relevance"),
                        ascending=params.get("ascending", False),
                    )
                elif op_name == "combine":
                    operation = CombineOperation(
                        weights=params.get(
                            "weights", {"semantic": 0.7, "exact": 0.3}
                        )
                    )

                operations.append(operation)

        return operations

    def _parse_params(self, params_str: str) -> dict[str, Any]:
        """Parse parameters string into a dictionary.

        Handles:
        - Quoted strings: threshold='high'
        - Numbers: threshold=0.9
        - Lists: tools=['web_search', 'extract_numbers']
        - Dictionaries: weights={'semantic': 0.7, 'exact': 0.3}
        """
        if not params_str:
            return {}

        params = {}
        # Split on commas not inside brackets or quotes
        param_pairs = re.findall(
            r"""
            (?:[^,"]|"[^"]*"|'[^']*')+  # Match everything except comma, or quoted strings
        """,
            params_str,
            re.VERBOSE,
        )

        for pair in param_pairs:
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Try to evaluate the value (for lists, dicts, numbers)
            try:
                # Safely evaluate the value
                value = eval(value, {"__builtins__": {}}, {})
            except:
                # If evaluation fails, treat as string
                value = value.strip("'\"")

            params[key] = value

        return params
