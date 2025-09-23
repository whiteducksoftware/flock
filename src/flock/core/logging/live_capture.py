from __future__ import annotations

import io
import re
import sys
import threading
import time
from collections import deque
from typing import Deque, List, Literal, MutableMapping

__all__ = [
    "enable_live_log_capture",
    "get_live_log_store",
    "LiveLogStore",
]

AnsiSource = Literal["stdout", "stderr"]
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class LiveLogStore:
    """Thread-safe ring buffer that keeps recent CLI log lines."""

    def __init__(self, max_lines: int = 800) -> None:
        self._lines: Deque[dict[str, object]] = deque(maxlen=max_lines)
        self._buffers: MutableMapping[AnsiSource, str] = {"stdout": "", "stderr": ""}
        self._lock = threading.Lock()

    def append_chunk(self, chunk: str, source: AnsiSource) -> None:
        """Append raw stream data, splitting into sanitized log lines."""
        if not chunk:
            return
        normalized = chunk.replace("\r\n", "\n").replace("\r", "\n")
        with self._lock:
            combined = self._buffers[source] + normalized
            parts = combined.split("\n")
            if combined.endswith("\n"):
                complete, remainder = parts[:-1], ""
            else:
                complete, remainder = parts[:-1], parts[-1]
            self._buffers[source] = remainder

            timestamp = time.time()
            for raw_line in complete:
                cleaned = ANSI_ESCAPE_PATTERN.sub("", raw_line).rstrip("\r")
                # Preserve deliberate blank lines but normalise whitespace-only strings
                if cleaned and cleaned.strip() == "":
                    cleaned = ""
                self._lines.append(
                    {
                        "timestamp": timestamp,
                        "stream": source,
                        "text": cleaned,
                    }
                )
                timestamp += 1e-6  # keep ordering stable for same chunk

    def get_entries(self, *, limit: int | None = None) -> List[dict[str, object]]:
        """Return a copy of the most recent log entries (oldest first)."""
        with self._lock:
            snapshot = list(self._lines)
        if limit is None:
            return snapshot
        if limit <= 0:
            return []
        return snapshot[-limit:]

    def clear(self) -> None:
        """Clear buffered log lines and pending chunks."""
        with self._lock:
            self._lines.clear()
            self._buffers = {"stdout": "", "stderr": ""}


class _TeeStream(io.TextIOBase):
    """Duplicate writes to the original stream and the live log store."""

    def __init__(self, wrapped: io.TextIOBase, source: AnsiSource, store: LiveLogStore) -> None:
        self._wrapped = wrapped
        self._source = source
        self._store = store

    def write(self, data: str) -> int:  # type: ignore[override]
        self._store.append_chunk(data, self._source)
        return self._wrapped.write(data)

    def flush(self) -> None:  # type: ignore[override]
        self._wrapped.flush()

    def isatty(self) -> bool:  # type: ignore[override]
        return self._wrapped.isatty()

    def fileno(self) -> int:  # type: ignore[override]
        return self._wrapped.fileno()

    def readable(self) -> bool:  # type: ignore[override]
        return False

    def writable(self) -> bool:  # type: ignore[override]
        return True

    def seekable(self) -> bool:  # type: ignore[override]
        return False

    def close(self) -> None:  # type: ignore[override]
        self._wrapped.close()

    @property
    def closed(self) -> bool:  # type: ignore[override]
        return self._wrapped.closed

    @property
    def encoding(self) -> str | None:  # type: ignore[override]
        return getattr(self._wrapped, "encoding", None)

    def __getattr__(self, item: str):
        return getattr(self._wrapped, item)


_live_log_store = LiveLogStore()
_capture_enabled = False


def enable_live_log_capture() -> None:
    """Wrap stdout/stderr so CLI output is mirrored into the live log store."""
    global _capture_enabled
    if _capture_enabled:
        return

    sys.stdout = _TeeStream(sys.stdout, "stdout", _live_log_store)
    sys.stderr = _TeeStream(sys.stderr, "stderr", _live_log_store)
    _capture_enabled = True


def get_live_log_store() -> LiveLogStore:
    """Expose the singleton live log store for dependency injection."""
    return _live_log_store
