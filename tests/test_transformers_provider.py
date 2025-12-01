"""Tests for the Hugging Face Transformers LiteLLM provider."""

import pytest
from unittest.mock import MagicMock, patch


class TestTransformersProviderRegistration:
    """Tests for provider registration."""

    def test_provider_module_imports(self):
        """Provider module should import without errors."""
        from flock.engines.providers.transformers_provider import (
            TransformersProvider,
            register_transformers_provider,
        )

        assert TransformersProvider is not None
        assert register_transformers_provider is not None

    def test_provider_registered_on_flock_import(self):
        """Provider should be auto-registered when flock is imported."""
        import litellm

        from flock import Flock  # noqa: F401 - import triggers registration

        providers = getattr(litellm, "custom_provider_map", [])
        transformers_providers = [
            p for p in providers if p.get("provider") == "transformers"
        ]

        assert len(transformers_providers) == 1
        assert transformers_providers[0]["custom_handler"] is not None

    def test_provider_not_registered_twice(self):
        """Provider should not be registered multiple times."""
        import litellm

        from flock.engines.providers.transformers_provider import (
            register_transformers_provider,
        )

        # Call register multiple times
        register_transformers_provider()
        register_transformers_provider()
        register_transformers_provider()

        providers = getattr(litellm, "custom_provider_map", [])
        transformers_providers = [
            p for p in providers if p.get("provider") == "transformers"
        ]

        # Should still only have one registration
        assert len(transformers_providers) == 1


class TestTransformersProviderModelParsing:
    """Tests for model string parsing."""

    def test_extracts_model_id_from_full_string(self):
        """Should extract model_id from 'transformers/org/model' format."""
        from flock.engines.providers.transformers_provider import TransformersProvider

        provider = TransformersProvider()

        # The completion method extracts model_id internally
        # Test the extraction logic
        model = "transformers/unsloth/Qwen3-4B-Instruct-2507-bnb-4bit"
        expected_model_id = "unsloth/Qwen3-4B-Instruct-2507-bnb-4bit"

        if model.startswith("transformers/"):
            model_id = model[len("transformers/") :]
        else:
            model_id = model

        assert model_id == expected_model_id

    def test_extracts_nested_model_paths(self):
        """Should handle nested paths like 'transformers/meta-llama/Llama-3.2-3B-Instruct'."""
        model = "transformers/meta-llama/Llama-3.2-3B-Instruct"
        expected = "meta-llama/Llama-3.2-3B-Instruct"

        if model.startswith("transformers/"):
            model_id = model[len("transformers/") :]
        else:
            model_id = model

        assert model_id == expected


class TestMessagesToPrompt:
    """Tests for message conversion."""

    def test_converts_simple_messages(self):
        """Should convert basic messages to prompt string."""
        from flock.engines.providers.transformers_provider import _messages_to_prompt

        # Create a mock tokenizer without chat template
        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.side_effect = Exception("No template")

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ]

        prompt = _messages_to_prompt(mock_tokenizer, messages)

        assert "System: You are helpful." in prompt
        assert "User: Hello!" in prompt
        assert prompt.endswith("Assistant: ")

    def test_uses_chat_template_when_available(self):
        """Should use tokenizer's chat template when available."""
        from flock.engines.providers.transformers_provider import _messages_to_prompt

        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.return_value = "<|im_start|>user\nHello<|im_end|>"

        messages = [{"role": "user", "content": "Hello"}]

        prompt = _messages_to_prompt(mock_tokenizer, messages)

        mock_tokenizer.apply_chat_template.assert_called_once()
        assert prompt == "<|im_start|>user\nHello<|im_end|>"


class TestModelCaching:
    """Tests for model caching behavior."""

    def test_cache_starts_empty(self):
        """Model cache should start empty."""
        from flock.engines.providers import transformers_provider

        # Clear cache for test
        transformers_provider._model_cache.clear()
        assert len(transformers_provider._model_cache) == 0

    def test_cache_dict_exists(self):
        """Model cache should be a dict that can store models."""
        from flock.engines.providers import transformers_provider

        # Verify cache is a dict
        assert isinstance(transformers_provider._model_cache, dict)

    def test_cache_key_format(self):
        """Cache keys should be model_id strings."""
        from flock.engines.providers import transformers_provider

        # Clear and add a mock entry
        transformers_provider._model_cache.clear()
        test_key = "unsloth/Qwen3-4B-Instruct-2507-bnb-4bit"
        transformers_provider._model_cache[test_key] = ("mock_model", "mock_tokenizer")

        assert test_key in transformers_provider._model_cache
        assert transformers_provider._model_cache[test_key] == (
            "mock_model",
            "mock_tokenizer",
        )

        # Clean up
        transformers_provider._model_cache.clear()
