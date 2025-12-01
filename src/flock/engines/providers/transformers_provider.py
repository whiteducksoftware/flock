"""LiteLLM custom provider for local Hugging Face Transformers models.

Enables running local models with the familiar model string syntax:

    flock = Flock("transformers/meta-llama/Llama-3.2-3B-Instruct")
    flock = Flock("transformers/unsloth/Qwen3-4B-Instruct-2507-bnb-4bit")

The model name after "transformers/" is passed directly to AutoModelForCausalLM
and AutoTokenizer from the Hugging Face transformers library.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

from litellm import CustomLLM
from litellm.types.utils import GenericStreamingChunk, ModelResponse

from flock.logging.logging import get_logger


logger = get_logger(__name__)

# Global model cache to avoid reloading
_model_cache: dict[str, tuple[Any, Any]] = {}


def _get_model_and_tokenizer(model_id: str) -> tuple[Any, Any]:
    """Load and cache model and tokenizer.

    Args:
        model_id: Hugging Face model identifier (e.g., "unsloth/Qwen3-4B-Instruct-2507-bnb-4bit")

    Returns:
        Tuple of (model, tokenizer)
    """
    if model_id in _model_cache:
        logger.debug(f"Using cached model: {model_id}")
        return _model_cache[model_id]

    logger.info(f"Loading transformers model: {model_id}")

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        raise ImportError(
            "transformers and torch are required for local model support. "
            "Install with: pip install transformers torch"
        ) from e

    # User specifies model_id - revision pinning is their responsibility
    tokenizer = AutoTokenizer.from_pretrained(model_id)  # nosec B615

    # Try device_map="auto" if accelerate is available, otherwise use default device
    try:
        import accelerate  # noqa: F401

        # User specifies model_id - revision pinning is their responsibility
        model = AutoModelForCausalLM.from_pretrained(  # nosec B615
            model_id,
            torch_dtype=torch.float32,
            device_map="auto",
        )
    except ImportError:
        logger.debug("accelerate not available, using default device placement")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # User specifies model_id - revision pinning is their responsibility
        model = AutoModelForCausalLM.from_pretrained(  # nosec B615
            model_id,
            torch_dtype=torch.float32,
        )
        model = model.to(device)

    # Ensure pad token is set
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    _model_cache[model_id] = (model, tokenizer)
    logger.info(f"Model loaded successfully: {model_id}")

    return model, tokenizer


def _messages_to_prompt(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    """Convert OpenAI-style messages to a prompt string.

    Uses the tokenizer's chat template if available, otherwise falls back
    to a simple format.
    """
    # Try to use chat template if available
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            pass  # Fall back to manual formatting

    # Simple fallback format
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            parts.append(f"System: {content}\n")
        elif role == "assistant":
            parts.append(f"Assistant: {content}\n")
        else:
            parts.append(f"User: {content}\n")
    parts.append("Assistant: ")
    return "".join(parts)


class TransformersProvider(CustomLLM):
    """LiteLLM custom provider for local Hugging Face Transformers models.

    Inherits from CustomLLM to integrate with LiteLLM's provider system.
    """

    def completion(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: ModelResponse,
        print_verbose: Any,
        encoding: Any,
        api_key: str,
        logging_obj: Any,
        optional_params: dict,
        acompletion: Any = None,
        litellm_params: Any = None,
        logger_fn: Any = None,
        headers: dict = {},
        timeout: float | None = None,
        client: Any = None,
    ) -> ModelResponse:
        """Generate completion using local transformers model.

        Args:
            model: Model string in format "transformers/org/model-name"
            messages: OpenAI-style messages list
            model_response: LiteLLM ModelResponse to populate
            optional_params: Additional generation parameters

        Returns:
            Populated ModelResponse
        """
        import torch
        from litellm.types.utils import Choices, Message, Usage

        # Extract model_id from "transformers/org/model-name" format
        if model.startswith("transformers/"):
            model_id = model[len("transformers/") :]
        else:
            model_id = model

        # Load model and tokenizer
        hf_model, tokenizer = _get_model_and_tokenizer(model_id)

        # Convert messages to prompt
        prompt = _messages_to_prompt(tokenizer, messages)

        # Tokenize input
        inputs = tokenizer(prompt, return_tensors="pt", padding=True)
        inputs = {k: v.to(hf_model.device) for k, v in inputs.items()}

        # Get generation parameters
        max_tokens = optional_params.get("max_tokens", 1024)
        temperature = optional_params.get("temperature", 0.7)

        # Generate
        start_time = time.time()
        with torch.no_grad():
            outputs = hf_model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature if temperature > 0 else None,
                do_sample=temperature > 0,
                pad_token_id=tokenizer.pad_token_id,
            )

        # Decode response (only the new tokens)
        input_length = inputs["input_ids"].shape[1]
        generated_tokens = outputs[0][input_length:]
        response_text = tokenizer.decode(generated_tokens, skip_special_tokens=True)

        # Calculate usage
        completion_tokens = len(generated_tokens)
        prompt_tokens = input_length

        # Populate response
        model_response.choices = [
            Choices(
                index=0,
                message=Message(role="assistant", content=response_text),
                finish_reason="stop",
            )
        ]
        model_response.model = model
        model_response.usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        logger.debug(
            f"Generated {completion_tokens} tokens in {time.time() - start_time:.2f}s"
        )

        return model_response

    def streaming(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: ModelResponse,
        print_verbose: Any,
        encoding: Any,
        api_key: str,
        logging_obj: Any,
        optional_params: dict,
        acompletion: Any = None,
        litellm_params: Any = None,
        logger_fn: Any = None,
        headers: dict = {},
        timeout: float | None = None,
        client: Any = None,
    ) -> Iterator[GenericStreamingChunk]:
        """Stream completion using local transformers model.

        Uses TextIteratorStreamer for token-by-token streaming.
        """
        import threading

        from transformers import TextIteratorStreamer

        # Extract model_id
        if model.startswith("transformers/"):
            model_id = model[len("transformers/") :]
        else:
            model_id = model

        # Load model and tokenizer
        hf_model, tokenizer = _get_model_and_tokenizer(model_id)

        # Convert messages to prompt
        prompt = _messages_to_prompt(tokenizer, messages)

        # Tokenize input
        inputs = tokenizer(prompt, return_tensors="pt", padding=True)
        inputs = {k: v.to(hf_model.device) for k, v in inputs.items()}

        # Get generation parameters
        max_tokens = optional_params.get("max_tokens", 1024)
        temperature = optional_params.get("temperature", 0.7)

        # Create streamer
        streamer = TextIteratorStreamer(
            tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        # Generation kwargs
        generation_kwargs = {
            **inputs,
            "max_new_tokens": max_tokens,
            "temperature": temperature if temperature > 0 else None,
            "do_sample": temperature > 0,
            "pad_token_id": tokenizer.pad_token_id,
            "streamer": streamer,
        }

        # Run generation in background thread
        thread = threading.Thread(target=hf_model.generate, kwargs=generation_kwargs)
        thread.start()

        # Yield tokens as they come
        # TextIteratorStreamer blocks until next token or generation complete
        for token_text in streamer:
            if token_text:
                yield GenericStreamingChunk(
                    text=token_text,
                    tool_use=None,
                    is_finished=False,
                    finish_reason="",
                    usage=None,
                    index=0,
                )

        # Final chunk
        yield GenericStreamingChunk(
            text="",
            tool_use=None,
            is_finished=True,
            finish_reason="stop",
            usage=None,
            index=0,
        )

        # Thread should be done since streamer iteration completed,
        # but use timeout as safety measure to avoid hanging
        thread.join(timeout=5.0)

    async def acompletion(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: ModelResponse,
        print_verbose: Any,
        encoding: Any,
        api_key: str,
        logging_obj: Any,
        optional_params: dict,
        acompletion: Any = None,
        litellm_params: Any = None,
        logger_fn: Any = None,
        headers: dict = {},
        timeout: float | None = None,
        client: Any = None,
    ) -> ModelResponse:
        """Async version of completion - runs sync version in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.completion(
                model=model,
                messages=messages,
                api_base=api_base,
                custom_prompt_dict=custom_prompt_dict,
                model_response=model_response,
                print_verbose=print_verbose,
                encoding=encoding,
                api_key=api_key,
                logging_obj=logging_obj,
                optional_params=optional_params,
                acompletion=acompletion,
                litellm_params=litellm_params,
                logger_fn=logger_fn,
                headers=headers,
                timeout=timeout,
                client=client,
            ),
        )

    async def astreaming(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: ModelResponse,
        print_verbose: Any,
        encoding: Any,
        api_key: str,
        logging_obj: Any,
        optional_params: dict,
        acompletion: Any = None,
        litellm_params: Any = None,
        logger_fn: Any = None,
        headers: dict = {},
        timeout: float | None = None,
        client: Any = None,
    ) -> AsyncIterator[GenericStreamingChunk]:
        """Async streaming using queue-based approach."""
        import queue
        import threading

        from transformers import TextIteratorStreamer

        # Extract model_id
        if model.startswith("transformers/"):
            model_id = model[len("transformers/") :]
        else:
            model_id = model

        # Load model and tokenizer
        hf_model, tokenizer = _get_model_and_tokenizer(model_id)

        # Convert messages to prompt
        prompt = _messages_to_prompt(tokenizer, messages)

        # Tokenize input
        inputs = tokenizer(prompt, return_tensors="pt", padding=True)
        inputs = {k: v.to(hf_model.device) for k, v in inputs.items()}

        # Get generation parameters
        max_tokens = optional_params.get("max_tokens", 1024)
        temperature = optional_params.get("temperature", 0.7)

        # Create streamer
        streamer = TextIteratorStreamer(
            tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        # Use a queue to communicate between threads
        token_queue: queue.Queue[str | None] = queue.Queue()

        def generate_with_streaming():
            """Run generation and stream tokens to queue."""
            try:
                generation_kwargs = {
                    **inputs,
                    "max_new_tokens": max_tokens,
                    "temperature": temperature if temperature > 0 else None,
                    "do_sample": temperature > 0,
                    "pad_token_id": tokenizer.pad_token_id,
                    "streamer": streamer,
                }
                # Start generation in a separate thread
                gen_thread = threading.Thread(
                    target=lambda: hf_model.generate(**generation_kwargs)
                )
                gen_thread.start()

                # Read from streamer and put to queue
                # This blocks until generation is complete
                for token_text in streamer:
                    if token_text:
                        token_queue.put(token_text)

                # Wait for generation thread with timeout
                gen_thread.join(timeout=5.0)
            except Exception as e:
                logger.error(f"Generation error: {e}")
            finally:
                token_queue.put(None)  # Signal completion

        # Start the streaming thread
        stream_thread = threading.Thread(target=generate_with_streaming)
        stream_thread.start()

        # Yield tokens asynchronously
        loop = asyncio.get_event_loop()
        while True:
            token = await loop.run_in_executor(None, token_queue.get)
            if token is None:
                break
            yield GenericStreamingChunk(
                text=token,
                tool_use=None,
                is_finished=False,
                finish_reason="",
                usage=None,
                index=0,
            )

        # Final chunk
        yield GenericStreamingChunk(
            text="",
            tool_use=None,
            is_finished=True,
            finish_reason="stop",
            usage=None,
            index=0,
        )

        # Wait for streaming thread with timeout to avoid hanging
        stream_thread.join(timeout=5.0)


def register_transformers_provider() -> None:
    """Register the transformers provider with LiteLLM.

    Call this once at startup to enable the "transformers/" model prefix.
    """
    try:
        import litellm
    except ImportError:
        logger.warning(
            "litellm not available, skipping transformers provider registration"
        )
        return

    provider = TransformersProvider()

    # Register with LiteLLM's custom provider map
    litellm.custom_provider_map = getattr(litellm, "custom_provider_map", [])

    # Check if already registered
    for entry in litellm.custom_provider_map:
        if entry.get("provider") == "transformers":
            logger.debug("Transformers provider already registered")
            return

    litellm.custom_provider_map.append({
        "provider": "transformers",
        "custom_handler": provider,
    })

    logger.info("Registered transformers provider with LiteLLM")


__all__ = ["TransformersProvider", "register_transformers_provider"]
