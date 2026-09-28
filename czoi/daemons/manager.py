"""DaemonManager: async scheduler for constraint daemons."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Optional

from .base import Daemon


class DaemonManager:
    """Schedules daemons asynchronously with per-daemon intervals."""

    def __init__(
        self,
        default_interval: float = 1.0,
        max_workers: int = 4,
    ) -> None:
        self.default_interval = default_interval
        self.daemons: list[Daemon] = []
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: list[asyncio.Task] = []

    # -----------------------------------------------------------------
    def add(self, daemon: Daemon) -> None:
        self.daemons.append(daemon)

    def extend(self, daemons: Iterable[Daemon]) -> None:
        self.daemons.extend(daemons)

    # -----------------------------------------------------------------
    async def _run_daemon(self, daemon: Daemon) -> None:
        loop = asyncio.get_running_loop()
        while self._running and daemon.enabled:
            await loop.run_in_executor(self._executor, daemon.safe_monitor)
            await asyncio.sleep(daemon.interval or self.default_interval)

    # -----------------------------------------------------------------
    async def run(self, duration: Optional[float] = None) -> None:
        self._running = True
        self._tasks = [
            asyncio.create_task(self._run_daemon(d))
            for d in self.daemons
        ]
        try:
            if duration is not None:
                await asyncio.sleep(duration)
            else:
                await asyncio.gather(*self._tasks)
        finally:
            self._running = False
            for t in self._tasks:
                t.cancel()
            for t in self._tasks:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
            self._tasks = []

    def stop(self) -> None:
        self._running = False

    # -----------------------------------------------------------------
    def tick(self) -> None:
        """Synchronous single-pass invocation (for tests)."""
        for d in self.daemons:
            d.safe_monitor()

    def shutdown(self) -> None:
        self.stop()
        self._executor.shutdown(wait=False)