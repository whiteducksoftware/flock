"""Tests for Webhook Context Management.

Spec: 002-webhook-notifications
Phase 3: Webhook Context Management
"""

import asyncio

import pytest


class TestWebhookContext:
    """Tests for WebhookContext dataclass."""

    def test_context_creation(self):
        """WebhookContext can be created with url and correlation_id."""
        from flock.api.webhooks import WebhookContext

        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret="my-secret",
            correlation_id="corr-123",
        )

        assert ctx.url == "https://example.com/webhook"
        assert ctx.secret == "my-secret"
        assert ctx.correlation_id == "corr-123"
        assert ctx.sequence == 0  # Default

    def test_context_without_secret(self):
        """WebhookContext secret can be None."""
        from flock.api.webhooks import WebhookContext

        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret=None,
            correlation_id="corr-123",
        )

        assert ctx.secret is None

    def test_next_sequence_increments(self):
        """next_sequence should increment and return the new value."""
        from flock.api.webhooks import WebhookContext

        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret=None,
            correlation_id="corr-123",
        )

        assert ctx.sequence == 0

        seq1 = ctx.next_sequence()
        assert seq1 == 1
        assert ctx.sequence == 1

        seq2 = ctx.next_sequence()
        assert seq2 == 2
        assert ctx.sequence == 2

        seq3 = ctx.next_sequence()
        assert seq3 == 3
        assert ctx.sequence == 3


class TestContextVarHelpers:
    """Tests for ContextVar helper functions."""

    def test_get_webhook_context_returns_none_when_not_set(self):
        """get_webhook_context should return None when not set."""
        from flock.api.webhooks import get_webhook_context, clear_webhook_context

        # Ensure clean state
        clear_webhook_context()

        result = get_webhook_context()
        assert result is None

    def test_set_and_get_webhook_context(self):
        """set_webhook_context should store context retrievable by get."""
        from flock.api.webhooks import (
            WebhookContext,
            set_webhook_context,
            get_webhook_context,
            clear_webhook_context,
        )

        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret="secret",
            correlation_id="corr-456",
        )

        try:
            set_webhook_context(ctx)
            retrieved = get_webhook_context()

            assert retrieved is not None
            assert retrieved.url == "https://example.com/webhook"
            assert retrieved.correlation_id == "corr-456"
        finally:
            clear_webhook_context()

    def test_clear_webhook_context(self):
        """clear_webhook_context should remove stored context."""
        from flock.api.webhooks import (
            WebhookContext,
            set_webhook_context,
            get_webhook_context,
            clear_webhook_context,
        )

        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret=None,
            correlation_id="corr-789",
        )

        set_webhook_context(ctx)
        assert get_webhook_context() is not None

        clear_webhook_context()
        assert get_webhook_context() is None


class TestContextVarIsolation:
    """Tests for ContextVar isolation between async tasks."""

    @pytest.mark.asyncio
    async def test_context_isolation_between_tasks(self):
        """ContextVar should be isolated between concurrent async tasks."""
        from flock.api.webhooks import (
            WebhookContext,
            set_webhook_context,
            get_webhook_context,
            clear_webhook_context,
        )

        results = {}

        async def task_a():
            ctx = WebhookContext(
                url="https://task-a.com/webhook",
                secret=None,
                correlation_id="task-a-corr",
            )
            set_webhook_context(ctx)
            await asyncio.sleep(0.01)  # Allow task switching
            retrieved = get_webhook_context()
            results["task_a"] = retrieved.correlation_id if retrieved else None
            clear_webhook_context()

        async def task_b():
            ctx = WebhookContext(
                url="https://task-b.com/webhook",
                secret=None,
                correlation_id="task-b-corr",
            )
            set_webhook_context(ctx)
            await asyncio.sleep(0.01)  # Allow task switching
            retrieved = get_webhook_context()
            results["task_b"] = retrieved.correlation_id if retrieved else None
            clear_webhook_context()

        # Run both tasks concurrently
        await asyncio.gather(task_a(), task_b())

        # Each task should see its own context
        assert results["task_a"] == "task-a-corr"
        assert results["task_b"] == "task-b-corr"

    @pytest.mark.asyncio
    async def test_context_not_shared_across_tasks(self):
        """Context set in one task should not be visible in another."""
        from flock.api.webhooks import (
            WebhookContext,
            set_webhook_context,
            get_webhook_context,
            clear_webhook_context,
        )

        task_b_saw_context = None

        async def task_a():
            ctx = WebhookContext(
                url="https://task-a.com/webhook",
                secret=None,
                correlation_id="task-a-only",
            )
            set_webhook_context(ctx)
            await asyncio.sleep(0.02)  # Wait for task_b to check
            clear_webhook_context()

        async def task_b():
            nonlocal task_b_saw_context
            await asyncio.sleep(0.01)  # Let task_a set its context
            # Task B should NOT see Task A's context
            task_b_saw_context = get_webhook_context()

        await asyncio.gather(task_a(), task_b())

        # Task B should not have seen Task A's context
        assert task_b_saw_context is None

    @pytest.mark.asyncio
    async def test_sequence_increments_independently_per_context(self):
        """Each context instance should have independent sequence counter."""
        from flock.api.webhooks import WebhookContext

        ctx1 = WebhookContext(
            url="https://example1.com",
            secret=None,
            correlation_id="corr-1",
        )

        ctx2 = WebhookContext(
            url="https://example2.com",
            secret=None,
            correlation_id="corr-2",
        )

        # Increment ctx1 several times
        ctx1.next_sequence()
        ctx1.next_sequence()
        ctx1.next_sequence()

        # ctx2 should still be at 0
        assert ctx1.sequence == 3
        assert ctx2.sequence == 0

        # Now increment ctx2
        ctx2.next_sequence()
        assert ctx2.sequence == 1
        assert ctx1.sequence == 3  # Unchanged
