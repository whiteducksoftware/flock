"""Tests for async utility decorators."""

import asyncio

import pytest

from flock.utils.async_utils import AsyncLockRequired, async_lock_required


# Fix for Windows event loop policy
@pytest.fixture(scope="function", autouse=True)
def event_loop_policy():
    """Set event loop policy for Windows."""
    if asyncio.get_event_loop_policy().__class__.__name__ == "WindowsProactorEventLoopPolicy":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class TestAsyncLockRequired:
    """Tests for AsyncLockRequired decorator."""

    @pytest.mark.asyncio
    async def test_decorator_acquires_lock(self):
        """Test that decorator acquires lock before executing method."""

        class MyClass:
            def __init__(self):
                self._lock = asyncio.Lock()
                self.execution_order = []

            @async_lock_required()
            async def locked_method(self, name: str):
                self.execution_order.append(f"{name}_start")
                await asyncio.sleep(0.01)
                self.execution_order.append(f"{name}_end")

        obj = MyClass()

        # Run two methods concurrently - they should execute sequentially due to lock
        await asyncio.gather(
            obj.locked_method("first"), obj.locked_method("second")
        )

        # Verify sequential execution (one completes before other starts)
        assert obj.execution_order in [
            ["first_start", "first_end", "second_start", "second_end"],
            ["second_start", "second_end", "first_start", "first_end"],
        ]

    @pytest.mark.asyncio
    async def test_decorator_with_custom_lock_attr(self):
        """Test decorator with custom lock attribute name."""

        class MyClass:
            def __init__(self):
                self._my_lock = asyncio.Lock()
                self.called = False

            @async_lock_required(lock_attr="_my_lock")
            async def my_method(self):
                self.called = True
                return "success"

        obj = MyClass()
        result = await obj.my_method()

        assert result == "success"
        assert obj.called is True

    @pytest.mark.asyncio
    async def test_decorator_releases_lock_on_exception(self):
        """Test that lock is released even if method raises exception."""

        class MyClass:
            def __init__(self):
                self._lock = asyncio.Lock()

            @async_lock_required()
            async def failing_method(self):
                raise ValueError("Test error")

        obj = MyClass()

        # Method should raise exception
        with pytest.raises(ValueError, match="Test error"):
            await obj.failing_method()

        # Lock should be released (not acquired)
        assert not obj._lock.locked()

    @pytest.mark.asyncio
    async def test_decorator_preserves_return_value(self):
        """Test that decorator preserves method return value."""

        class MyClass:
            def __init__(self):
                self._lock = asyncio.Lock()

            @async_lock_required()
            async def return_value(self):
                return 42

        obj = MyClass()
        result = await obj.return_value()

        assert result == 42

    @pytest.mark.asyncio
    async def test_decorator_preserves_arguments(self):
        """Test that decorator preserves method arguments."""

        class MyClass:
            def __init__(self):
                self._lock = asyncio.Lock()

            @async_lock_required()
            async def method_with_args(self, a: int, b: str, c: float = 3.14):
                return {"a": a, "b": b, "c": c}

        obj = MyClass()
        result = await obj.method_with_args(1, "test", c=2.71)

        assert result == {"a": 1, "b": "test", "c": 2.71}

    @pytest.mark.asyncio
    async def test_direct_class_usage(self):
        """Test using AsyncLockRequired class directly."""

        class MyClass:
            def __init__(self):
                self._lock = asyncio.Lock()
                self.called = False

            @AsyncLockRequired()
            async def my_method(self):
                self.called = True

        obj = MyClass()
        await obj.my_method()

        assert obj.called is True
