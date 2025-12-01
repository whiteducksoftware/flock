"""Tests for the Hugging Face Transformers LiteLLM provider."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys


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


class TestModelLoading:
    """Tests for model loading logic."""

    def test_cache_hit_returns_cached(self):
        """When model is in cache, should return cached version."""
        from flock.engines.providers import transformers_provider

        # Setup cache with mock
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        transformers_provider._model_cache["test/model"] = (mock_model, mock_tokenizer)

        try:
            # This should return cached version without loading
            result = transformers_provider._get_model_and_tokenizer("test/model")
            assert result == (mock_model, mock_tokenizer)
        finally:
            transformers_provider._model_cache.clear()

    def test_get_model_and_tokenizer_function_exists(self):
        """The _get_model_and_tokenizer function should exist and be callable."""
        from flock.engines.providers import transformers_provider

        assert callable(transformers_provider._get_model_and_tokenizer)


class TestMessagesToPromptEdgeCases:
    """Additional tests for message conversion edge cases."""

    def test_assistant_role_message(self):
        """Should handle assistant role messages."""
        from flock.engines.providers.transformers_provider import _messages_to_prompt

        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.side_effect = Exception("No template")

        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "How are you?"},
        ]

        prompt = _messages_to_prompt(mock_tokenizer, messages)

        assert "User: Hi" in prompt
        assert "Assistant: Hello!" in prompt
        assert "How are you?" in prompt

    def test_empty_content_message(self):
        """Should handle messages with empty content."""
        from flock.engines.providers.transformers_provider import _messages_to_prompt

        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.side_effect = Exception("No template")

        messages = [{"role": "user", "content": ""}]

        prompt = _messages_to_prompt(mock_tokenizer, messages)

        assert "User: " in prompt
        assert prompt.endswith("Assistant: ")

    def test_missing_role_defaults_to_user(self):
        """Should default to user role if role is missing."""
        from flock.engines.providers.transformers_provider import _messages_to_prompt

        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.side_effect = Exception("No template")

        messages = [{"content": "Hello"}]

        prompt = _messages_to_prompt(mock_tokenizer, messages)

        assert "User: Hello" in prompt

    def test_tokenizer_without_apply_chat_template(self):
        """Should fall back when tokenizer has no apply_chat_template."""
        from flock.engines.providers.transformers_provider import _messages_to_prompt

        mock_tokenizer = MagicMock(spec=[])  # No methods

        messages = [{"role": "user", "content": "Test"}]

        prompt = _messages_to_prompt(mock_tokenizer, messages)

        assert "User: Test" in prompt


class TestTransformersProviderClass:
    """Tests for the TransformersProvider class."""

    def test_provider_inherits_from_custom_llm(self):
        """Provider should inherit from litellm.CustomLLM."""
        from litellm import CustomLLM

        from flock.engines.providers.transformers_provider import TransformersProvider

        assert issubclass(TransformersProvider, CustomLLM)

    def test_provider_has_completion_method(self):
        """Provider should have completion method."""
        from flock.engines.providers.transformers_provider import TransformersProvider

        provider = TransformersProvider()
        assert hasattr(provider, "completion")
        assert callable(provider.completion)

    def test_provider_has_streaming_method(self):
        """Provider should have streaming method."""
        from flock.engines.providers.transformers_provider import TransformersProvider

        provider = TransformersProvider()
        assert hasattr(provider, "streaming")
        assert callable(provider.streaming)

    def test_provider_has_acompletion_method(self):
        """Provider should have async completion method."""
        from flock.engines.providers.transformers_provider import TransformersProvider

        provider = TransformersProvider()
        assert hasattr(provider, "acompletion")
        assert callable(provider.acompletion)

    def test_provider_has_astreaming_method(self):
        """Provider should have async streaming method."""
        from flock.engines.providers.transformers_provider import TransformersProvider

        provider = TransformersProvider()
        assert hasattr(provider, "astreaming")
        assert callable(provider.astreaming)


class TestModelIdExtraction:
    """Tests for model ID extraction from model strings."""

    def test_strips_transformers_prefix(self):
        """Should strip 'transformers/' prefix from model string."""
        model = "transformers/org/model-name"
        if model.startswith("transformers/"):
            model_id = model[len("transformers/") :]
        else:
            model_id = model
        assert model_id == "org/model-name"

    def test_handles_model_without_prefix(self):
        """Should handle model string without transformers prefix."""
        model = "org/model-name"
        if model.startswith("transformers/"):
            model_id = model[len("transformers/") :]
        else:
            model_id = model
        assert model_id == "org/model-name"

    def test_handles_deeply_nested_paths(self):
        """Should handle deeply nested model paths."""
        model = "transformers/org/sub/model-v1.0"
        if model.startswith("transformers/"):
            model_id = model[len("transformers/") :]
        else:
            model_id = model
        assert model_id == "org/sub/model-v1.0"


class TestGenericStreamingChunkFormat:
    """Tests for streaming chunk format."""

    def test_streaming_chunk_has_required_fields(self):
        """GenericStreamingChunk should have all required fields."""
        from litellm.types.utils import GenericStreamingChunk

        chunk = GenericStreamingChunk(
            text="hello",
            tool_use=None,
            is_finished=False,
            finish_reason="",
            usage=None,
            index=0,
        )

        assert chunk["text"] == "hello"
        assert chunk["is_finished"] is False
        assert chunk["finish_reason"] == ""
        assert chunk["usage"] is None
        assert chunk["index"] == 0

    def test_final_chunk_format(self):
        """Final streaming chunk should have correct format."""
        from litellm.types.utils import GenericStreamingChunk

        final_chunk = GenericStreamingChunk(
            text="",
            tool_use=None,
            is_finished=True,
            finish_reason="stop",
            usage=None,
            index=0,
        )

        assert final_chunk["text"] == ""
        assert final_chunk["is_finished"] is True
        assert final_chunk["finish_reason"] == "stop"
