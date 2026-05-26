"""A mixin class for parsing agent prompts and building clean signatures for DSPy."""

# DEPRECATED! This mixin is no longer used in the current version of Flock. It was used to parse agent prompts and build clean signatures for DSPy.
# TODO: DELETE THIS FILE!

from flock.core.util.input_resolver import split_top_level


class PromptParserMixin:
    """A mixin class for parsing agent prompts and building clean signatures for DSPy."""

    def _parse_key_descriptions(self, keys_str: str) -> list[tuple[str, str]]:
        """Parse a comma-separated string into a list of (key, description) tuples.

        This function processes a configuration string that defines one or more keys, where each key may
        include a type hint and an optional human-readable description. The expected format for each key is:

            key: type_hint | description

        If the pipe symbol ("|") is absent, the description is set to an empty string.

        The splitting is performed using split_top_level() so that commas inside type hints are preserved.

        For example, given:
            "query: str | The search query, context: dict | The full conversation context"
        it returns:
            [("query", "The search query"), ("context", "The full conversation context")]

        Args:
            keys_str (str): A comma-separated string of key definitions.

        Returns:
            List[Tuple[str, str]]: A list of (key, description) tuples.
        """
        key_descs = []
        for part in split_top_level(keys_str):
            if not part:
                continue
            if "|" in part:
                key_type_part, desc = part.split("|", 1)
                desc = desc.strip()
            else:
                key_type_part = part
                desc = ""
            key = key_type_part.split(":", 1)[0].strip()
            key_descs.append((key, desc))
        return key_descs

    def _build_clean_signature(self, keys_str: str) -> str:
        """Build a clean signature string from the configuration string by removing the description parts.

        Given a string like:
            "query: str | The search query, context: dict | The full conversation context"
        this method returns:
            "query: str, context: dict"

        This function uses split_top_level() to avoid splitting on commas that are inside type hints.

        Args:
            keys_str (str): The configuration string containing keys, type hints, and optional descriptions.

        Returns:
            str: A clean signature string with only keys and type hints.
        """
        parts = []
        for part in split_top_level(keys_str):
            if not part:
                continue
            if "|" in part:
                clean_part = part.split("|", 1)[0].strip()
            else:
                clean_part = part.strip()
            parts.append(clean_part)
        return ", ".join(parts)

    def _build_descriptions(self) -> tuple[dict[str, str], dict[str, str]]:
        """Build dictionaries of input and output descriptions from the agent's configuration.

        Returns:
            A tuple containing:
            - input_desc: A dictionary mapping each input key (without type hints) to its description.
            - output_desc: A dictionary mapping each output key (without type hints) to its description.
        """
        input_desc: dict[str, str] = {}
        if self.input:
            for key, desc in self._parse_key_descriptions(self.input):
                input_desc[key] = desc

        output_desc: dict[str, str] = {}
        if self.output:
            for key, desc in self._parse_key_descriptions(self.output):
                output_desc[key] = desc

        return input_desc, output_desc

    def _build_prompt(
        self, input_desc: dict[str, str], output_desc: dict[str, str]
    ) -> str:
        """Build a clean signature prompt from the agent's configuration.

        This method uses the original input and output strings (removing the description parts)
        to create a signature string that is passed to DSPy. For example, if:
        - self.input is "query: str | The search query, context: dict | The full conversation context"
        - self.output is "result: str | The result"
        then the prompt will be:
        "query: str, context: dict -> result: str"

        **Note:** The descriptive metadata is preserved in the dictionaries obtained from _build_descriptions,
        which are passed separately to DSPy.

        Args:
            input_desc: Dictionary of input key descriptions (for metadata only).
            output_desc: Dictionary of output key descriptions (for metadata only).

        Returns:
            A clean signature string for DSPy.
        """
        clean_input = (
            self._build_clean_signature(self.input) if self.input else ""
        )
        clean_output = (
            self._build_clean_signature(self.output) if self.output else ""
        )
        # Combine the clean input and output signatures using "->"
        return f"{clean_input} -> {clean_output}"
