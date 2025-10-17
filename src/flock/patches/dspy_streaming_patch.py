"""
Monkey-patch for DSPy's sync_send_to_stream function.

The original DSPy implementation blocks the event loop with future.result(),
causing deadlocks when using MCP tools with dashboard streaming.

This patch replaces it with a non-blocking fire-and-forget approach.
"""

import asyncio
import logging


logger = logging.getLogger(__name__)


def patched_sync_send_to_stream(stream, message):
    """Non-blocking replacement for DSPy's sync_send_to_stream.

    Instead of blocking with future.result(), this version:
    1. Schedules the send as a background task (fire-and-forget)
    2. Never blocks the calling thread
    3. Logs errors but doesn't raise them

    This allows MCP tool callbacks to complete without deadlocking.
    """

    async def _send():
        try:
            await stream.send(message)
        except Exception as e:
            logger.debug(f"DSPy status message send failed (non-critical): {e}")

    try:
        # Try to get the running event loop
        loop = asyncio.get_running_loop()

        # Schedule as a background task (fire-and-forget)
        # This won't block - the task runs independently
        loop.create_task(_send())

    except RuntimeError:
        # No event loop running - this is a sync context
        # We can safely create a new loop and run the task
        try:
            asyncio.run(_send())
        except Exception as e:
            logger.debug(
                f"DSPy status message send failed in sync context (non-critical): {e}"
            )


def apply_patch():
    """Apply the monkey-patch to DSPy's streaming module."""
    try:
        import dspy.streaming.messages as dspy_messages

        # Store original for reference (in case we need to restore)
        if not hasattr(dspy_messages, "_original_sync_send_to_stream"):
            dspy_messages._original_sync_send_to_stream = (
                dspy_messages.sync_send_to_stream
            )

        # Replace with our non-blocking version
        dspy_messages.sync_send_to_stream = patched_sync_send_to_stream

        logger.info(
            "Applied DSPy streaming patch - status messages are now non-blocking"
        )
        return True

    except Exception as e:
        logger.warning(f"Failed to apply DSPy streaming patch: {e}")
        return False


def restore_original():
    """Restore the original DSPy function (for testing/debugging)."""
    try:
        import dspy.streaming.messages as dspy_messages

        if hasattr(dspy_messages, "_original_sync_send_to_stream"):
            dspy_messages.sync_send_to_stream = (
                dspy_messages._original_sync_send_to_stream
            )
            logger.info("Restored original DSPy streaming function")
            return True

    except Exception as e:
        logger.warning(f"Failed to restore original DSPy function: {e}")
        return False
