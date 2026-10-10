"""Request budgets for decision models.

Hosted decision models limit how many requests a client may send per period
(the Microsoft-Decision-1 deployments, for example, 100 per minute). A
``RequestBudget`` keeps all deciders that share a model below such a limit:
requests over the budget wait for a free slot instead of failing with HTTP 429.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import deque
from collections.abc import Awaitable, Callable


PERIODS = {"s": 1.0, "min": 60.0, "h": 3600.0}
_RATE = re.compile(r"^\s*(\d+)\s*/\s*(s|min|h)\s*$")


class RequestBudget:
    """At most ``limit`` requests start within any ``period`` seconds.

    Callers reserve the earliest free slot before they wait, so concurrent
    callers never exceed the budget and are served in arrival order.
    """

    def __init__(
        self,
        limit: int,
        period: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if limit < 1 or period <= 0:
            raise ValueError(
                f"Invalid decision rate limit {limit}/{period}s: "
                "need at least one request per positive period."
            )
        self.limit = limit
        self.period = period
        self._clock = clock
        self._sleep = sleep
        # Start times of the last ``limit`` requests, reserved ones included
        self._starts: deque[float] = deque(maxlen=limit)

    @classmethod
    def parse(cls, rate: str) -> RequestBudget:
        """``"100/min"``, ``"5/s"`` or ``"1000/h"``."""
        match = _RATE.match(rate)
        if not match or int(match.group(1)) < 1:
            raise ValueError(
                f"Invalid decision rate limit {rate!r}; use 'N/s', 'N/min' or "
                "'N/h', for example '100/min'."
            )
        return cls(int(match.group(1)), PERIODS[match.group(2)])

    async def acquire(self) -> None:
        """Wait until a request may start."""
        now = self._clock()
        start = now
        if len(self._starts) == self.limit:
            start = max(now, self._starts[0] + self.period)
        self._starts.append(start)
        if start > now:
            await self._sleep(start - now)

    def __repr__(self) -> str:
        return f"RequestBudget({self.limit}, {self.period})"


__all__ = ["RequestBudget"]
