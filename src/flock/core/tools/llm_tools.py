import hashlib
import json
import re
from collections.abc import Callable
from typing import Any

import nltk

from flock.core.logging.trace_and_logged import traced_and_logged

# Ensure NLTK data is downloaded
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords")


@traced_and_logged
def split_by_sentences(text: str) -> list[str]:
    return nltk.sent_tokenize(text)


@traced_and_logged
def split_by_characters(
    text: str, chunk_size: int = 4000, overlap: int = 200
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    if not text:
        return []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        # If we're not at the end and the next character isn't a space, try to find a suitable break point
        if end < text_length and text[end] not in [
            " ",
            "\n",
            ".",
            ",",
            "!",
            "?",
            ";",
            ":",
            "-",
        ]:
            # Look for the last occurrence of a good break character
            break_chars = [" ", "\n", ".", ",", "!", "?", ";", ":", "-"]
            for i in range(end, max(start, end - 100), -1):
                if text[i] in break_chars:
                    end = i + 1  # Include the break character
                    break

        chunks.append(text[start:end])
        start = end - overlap if end < text_length else text_length

    return chunks


@traced_and_logged
def split_by_tokens(
    text: str,
    tokenizer: Callable[[str], list[str]],
    max_tokens: int = 1024,
    overlap_tokens: int = 100,
) -> list[str]:
    tokens = tokenizer(text)
    chunks = []

    i = 0
    while i < len(tokens):
        chunk = tokens[i : i + max_tokens]
        chunks.append("".join(chunk))
        i += max_tokens - overlap_tokens

    return chunks


@traced_and_logged
def split_by_separator(text: str, separator: str = "\n\n") -> list[str]:
    if not text:
        return []

    chunks = text.split(separator)
    return [chunk for chunk in chunks if chunk.strip()]


@traced_and_logged
def recursive_text_splitter(
    text: str,
    chunk_size: int = 4000,
    separators: list[str] = ["\n\n", "\n", ". ", ", ", " ", ""],
    keep_separator: bool = True,
) -> list[str]:
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    if not separators:
        return [
            text[:chunk_size],
            *recursive_text_splitter(text[chunk_size:], chunk_size, separators),
        ]

    separator = separators[0]
    new_separators = separators[1:]

    if separator == "":
        # If we're at the character level, just split by characters
        return split_by_characters(text, chunk_size=chunk_size, overlap=0)

    splits = text.split(separator)
    separator_len = len(separator) if keep_separator else 0

    # Add separator back to the chunks if needed
    if keep_separator and separator:
        splits = [f"{split}{separator}" for split in splits[:-1]] + [splits[-1]]

    # Process each split
    result = []
    current_chunk = []
    current_length = 0

    for split in splits:
        split_len = len(split)

        if split_len > chunk_size:
            # If current split is too large, handle current chunk and recursively split this large piece
            if current_chunk:
                result.append("".join(current_chunk))
                current_chunk = []
                current_length = 0

            # Recursively split this large piece
            smaller_chunks = recursive_text_splitter(
                split, chunk_size, new_separators, keep_separator
            )
            result.extend(smaller_chunks)
        elif current_length + split_len <= chunk_size:
            # If we can fit this split in the current chunk, add it
            current_chunk.append(split)
            current_length += split_len
        else:
            # If we can't fit this split, complete the current chunk and start a new one
            result.append("".join(current_chunk))
            current_chunk = [split]
            current_length = split_len

    # Don't forget the last chunk
    if current_chunk:
        result.append("".join(current_chunk))

    return result


@traced_and_logged
def chunk_text_for_embedding(
    text: str, file_name: str, chunk_size: int = 1000, overlap: int = 100
) -> list[dict[str, Any]]:
    chunks = split_by_characters(text, chunk_size=chunk_size, overlap=overlap)

    # Create metadata for each chunk
    result = []
    for i, chunk in enumerate(chunks):
        result.append(
            {
                "chunk_id": file_name + "_" + str(i),
                "text": chunk,
                "file": file_name,
                "total_chunks": len(chunks),
            }
        )

    return result


@traced_and_logged
def split_code_by_functions(code: str) -> list[dict[str, Any]]:
    if not code:
        return []

    # Basic pattern for Python functions
    function_pattern = re.compile(
        r"(^|\n)def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)(?:\s*->.*?)?:"
    )
    matches = list(function_pattern.finditer(code))

    if not matches:
        return [{"name": "Main", "content": code, "type": "code"}]

    functions = []

    # Process each function
    for i in range(len(matches)):
        current_match = matches[i]
        function_name = current_match.group(2)

        # Determine function content
        if i < len(matches) - 1:
            next_function_start = matches[i + 1].start()
            content = code[current_match.start() : next_function_start]
        else:
            content = code[current_match.start() :]

        functions.append(
            {
                "name": function_name,
                "content": content.strip(),
                "type": "function",
            }
        )

    # Check if there's content before the first function
    if matches[0].start() > 0:
        preamble = code[: matches[0].start()].strip()
        if preamble:
            functions.insert(
                0,
                {"name": "Imports/Setup", "content": preamble, "type": "code"},
            )

    return functions


@traced_and_logged
def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens using tiktoken."""
    if not text:
        return 0

    try:
        import tiktoken

        # Map model names to encoding types
        if model.startswith(("gpt-4", "gpt-3.5")):
            encoding_name = "cl100k_base"  # For newer OpenAI models
        elif model.startswith("text-davinci"):
            encoding_name = "p50k_base"  # For older OpenAI models
        elif "llama" in model.lower() or "mistral" in model.lower():
            encoding_name = (
                "cl100k_base"  # Best approximation for LLaMA/Mistral
            )
        else:
            # Default to cl100k_base as fallback
            encoding_name = "cl100k_base"

        # Try to get the specific encoder for the model if available
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fall back to the encoding name
            encoding = tiktoken.get_encoding(encoding_name)

        # Count tokens
        token_integers = encoding.encode(text)
        return len(token_integers)

    except ImportError:
        # Fallback to character-based estimation if tiktoken is not installed
        return count_tokens_estimate(text, model)


@traced_and_logged
def count_tokens_estimate(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Estimate token count for different models."""
    if not text:
        return 0

    # Rough token estimations for different models
    if model.startswith(("gpt-3", "gpt-4")):
        # OpenAI models: ~4 chars per token
        return len(text) // 4 + 1
    elif model.startswith("claude"):
        # Anthropic models: ~3.5 chars per token
        return len(text) // 3.5 + 1
    elif "llama" in model.lower():
        # LLaMA-based models: ~3.7 chars per token
        return len(text) // 3.7 + 1
    else:
        # Default estimation
        return len(text) // 4 + 1


@traced_and_logged
def truncate_to_token_limit(
    text: str, max_tokens: int = 4000, model: str = "gpt-3.5-turbo"
) -> str:
    if not text:
        return ""

    # Try to use tiktoken for accurate truncation
    try:
        import tiktoken

        # Get appropriate encoding
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fall back to cl100k_base (used by most newer models)
            encoding = tiktoken.get_encoding("cl100k_base")

        # Encode the text to tokens
        tokens = encoding.encode(text)

        # If we're already under the limit, return the original text
        if len(tokens) <= max_tokens:
            return text

        # Truncate tokens and decode back to text
        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)

    except ImportError:
        # Fallback to the character-based method if tiktoken is not available
        estimated_tokens = count_tokens_estimate(text, model)

        if estimated_tokens <= max_tokens:
            return text

        # Calculate approximate character limit
        char_per_token = 4  # Default for most models
        if model.startswith("claude"):
            char_per_token = 3.5
        elif "llama" in model.lower():
            char_per_token = 3.7

        char_limit = int(max_tokens * char_per_token)

        # Try to find a good breaking point
        if char_limit < len(text):
            # Look for sentence or paragraph break near the limit
            for i in range(char_limit - 1, max(0, char_limit - 100), -1):
                if i < len(text) and text[i] in [".", "!", "?", "\n"]:
                    return text[: i + 1]

        # Fallback to hard truncation
        return text[:char_limit]


@traced_and_logged
def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    if not text:
        return []

    # Get stopwords
    try:
        from nltk.corpus import stopwords

        stop_words = set(stopwords.words("english"))
    except:
        # Fallback basic stopwords if NLTK data isn't available
        stop_words = {
            "i",
            "me",
            "my",
            "myself",
            "we",
            "our",
            "ours",
            "ourselves",
            "you",
            "you're",
            "you've",
            "you'll",
            "you'd",
            "your",
            "yours",
            "yourself",
            "yourselves",
            "he",
            "him",
            "his",
            "himself",
            "she",
            "she's",
            "her",
            "hers",
            "herself",
            "it",
            "it's",
            "its",
            "itself",
            "they",
            "them",
            "their",
            "theirs",
            "themselves",
            "what",
            "which",
            "who",
            "whom",
            "this",
            "that",
            "that'll",
            "these",
            "those",
            "am",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "having",
            "do",
            "does",
            "did",
            "doing",
            "a",
            "an",
            "the",
            "and",
            "but",
            "if",
            "or",
            "because",
            "as",
            "until",
            "while",
            "of",
            "at",
            "by",
            "for",
            "with",
            "about",
            "against",
            "between",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "to",
            "from",
            "up",
            "down",
            "in",
            "out",
            "on",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
        }

    # Tokenize and remove punctuation
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

    # Remove stopwords
    words = [word for word in words if word not in stop_words]

    # Count word frequencies
    word_freq = {}
    for word in words:
        if word in word_freq:
            word_freq[word] += 1
        else:
            word_freq[word] = 1

    # Sort by frequency
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    # Return top N keywords
    return [word for word, freq in sorted_words[:top_n]]


@traced_and_logged
def clean_text(
    text: str,
    remove_urls: bool = True,
    remove_html: bool = True,
    normalize_whitespace: bool = True,
) -> str:
    if not text:
        return ""

    result = text

    # Remove URLs
    if remove_urls:
        result = re.sub(r"https?://\S+|www\.\S+", "", result)

    # Remove HTML tags
    if remove_html:
        result = re.sub(r"<.*?>", "", result)

    # Normalize whitespace
    if normalize_whitespace:
        # Replace multiple spaces, tabs, newlines with a single space
        result = re.sub(r"\s+", " ", result)
        result = result.strip()

    return result


@traced_and_logged
def format_chat_history(
    messages: list[dict[str, str]],
    format_type: str = "text",
    system_prefix: str = "System: ",
    user_prefix: str = "User: ",
    assistant_prefix: str = "Assistant: ",
) -> str:
    if not messages:
        return ""

    result = []

    if format_type == "text":
        for msg in messages:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")

            if role == "system":
                result.append(f"{system_prefix}{content}")
            elif role == "user":
                result.append(f"{user_prefix}{content}")
            elif role == "assistant":
                result.append(f"{assistant_prefix}{content}")
            else:
                result.append(f"{role.capitalize()}: {content}")

        return "\n\n".join(result)

    elif format_type == "markdown":
        for msg in messages:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")

            if role == "system":
                result.append(f"**{system_prefix.strip()}** {content}")
            elif role == "user":
                result.append(f"**{user_prefix.strip()}** {content}")
            elif role == "assistant":
                result.append(f"**{assistant_prefix.strip()}** {content}")
            else:
                result.append(f"**{role.capitalize()}:** {content}")

        return "\n\n".join(result)

    else:
        raise ValueError(f"Unsupported format type: {format_type}")


@traced_and_logged
def extract_json_from_text(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    # Find JSON-like patterns between curly braces
    json_pattern = re.compile(r"({[\s\S]*?})")
    json_matches = json_pattern.findall(text)

    # Try to parse each match
    for json_str in json_matches:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            continue

    # Try to find JSON with markdown code blocks
    code_block_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")
    code_blocks = code_block_pattern.findall(text)

    for block in code_blocks:
        # Clean up any trailing ``` that might have been captured
        block = block.replace("```", "")
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue

    # No valid JSON found
    return None


@traced_and_logged
def calculate_text_hash(text: str, algorithm: str = "sha256") -> str:
    if not text:
        return ""

    if algorithm == "md5":
        return hashlib.md5(text.encode()).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(text.encode()).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(text.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


@traced_and_logged
def format_table_from_dicts(data: list[dict[str, Any]]) -> str:
    if not data:
        return ""

    # Extract all possible keys
    keys = set()
    for item in data:
        keys.update(item.keys())

    # Convert to list and sort for consistent output
    keys = sorted(list(keys))

    # Calculate column widths
    widths = {key: len(key) for key in keys}
    for item in data:
        for key in keys:
            if key in item:
                value_str = str(item[key])
                widths[key] = max(widths[key], len(value_str))

    # Create header
    header = " | ".join(f"{key:{widths[key]}}" for key in keys)
    separator = "-+-".join("-" * widths[key] for key in keys)

    # Create rows
    rows = []
    for item in data:
        row = " | ".join(f"{item.get(key, '')!s:{widths[key]}}" for key in keys)
        rows.append(row)

    # Combine everything
    return f"{header}\n{separator}\n" + "\n".join(rows)


@traced_and_logged
def detect_language(text: str) -> str:
    """Simple language detection"""
    if not text or len(text.strip()) < 10:
        return "unknown"

    try:
        # Try to use langdetect if available
        from langdetect import detect

        return detect(text)
    except ImportError:
        # Fallback to simple detection based on character frequency
        # This is very simplistic and only works for a few common languages
        text = text.lower()

        # Count character frequencies that may indicate certain languages
        special_chars = {
            "á": 0,
            "é": 0,
            "í": 0,
            "ó": 0,
            "ú": 0,
            "ü": 0,
            "ñ": 0,  # Spanish
            "ä": 0,
            "ö": 0,
            "ß": 0,  # German
            "ç": 0,
            "à": 0,
            "è": 0,
            "ù": 0,  # French
            "å": 0,
            "ø": 0,  # Nordic
            "й": 0,
            "ы": 0,
            "ъ": 0,
            "э": 0,  # Russian/Cyrillic
            "的": 0,
            "是": 0,
            "在": 0,  # Chinese
            "の": 0,
            "は": 0,
            "で": 0,  # Japanese
            "한": 0,
            "국": 0,
            "어": 0,  # Korean
        }

        for char in text:
            if char in special_chars:
                special_chars[char] += 1

        # Detect based on character frequencies
        spanish = sum(
            special_chars[c] for c in ["á", "é", "í", "ó", "ú", "ü", "ñ"]
        )
        german = sum(special_chars[c] for c in ["ä", "ö", "ß"])
        french = sum(special_chars[c] for c in ["ç", "à", "è", "ù"])
        nordic = sum(special_chars[c] for c in ["å", "ø"])
        russian = sum(special_chars[c] for c in ["й", "ы", "ъ", "э"])
        chinese = sum(special_chars[c] for c in ["的", "是", "在"])
        japanese = sum(special_chars[c] for c in ["の", "は", "で"])
        korean = sum(special_chars[c] for c in ["한", "국", "어"])

        scores = {
            "es": spanish,
            "de": german,
            "fr": french,
            "no": nordic,
            "ru": russian,
            "zh": chinese,
            "ja": japanese,
            "ko": korean,
        }

        # If we have a clear signal from special characters
        max_score = max(scores.values())
        if max_score > 0:
            return max(scores, key=scores.get)

        # Otherwise assume English (very simplistic)
        return "en"


@traced_and_logged
def tiktoken_split(
    text: str,
    model: str = "gpt-3.5-turbo",
    chunk_size: int = 1000,
    overlap: int = 50,
) -> list[str]:
    """Split text based on tiktoken tokens with proper overlap handling."""
    if not text:
        return []

    try:
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")

        # Encode the text to tokens
        tokens = encoding.encode(text)
        total_tokens = len(tokens)

        # Check if we need to split at all
        if total_tokens <= chunk_size:
            return [text]

        # Create chunks with overlap
        chunks = []
        start_idx = 0

        while start_idx < total_tokens:
            # Define the end of this chunk
            end_idx = min(start_idx + chunk_size, total_tokens)

            # Decode this chunk of tokens back to text
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

            # Move to the next chunk, accounting for overlap
            start_idx += chunk_size - overlap

            # Avoid tiny final chunks
            if start_idx < total_tokens and start_idx + overlap >= total_tokens:
                break

        return chunks
    except ImportError:
        # Fallback to character-based chunking if tiktoken is not available
        return split_by_characters(
            text, chunk_size=chunk_size * 4, overlap=overlap * 4
        )
