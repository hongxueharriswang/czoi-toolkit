"""Constraint daemons (Δ): continuous monitors with hierarchy."""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..core.types import DaemonSignal
from ..zones.base import ZoneBase

log = logging.getLogger(__name__)


class Daemon:
    """Base class for constraint daemons.

    Hierarchy: child daemons signal upward via `emit_signal`; parents
    handle signals in `on_signal`.
    """

    default_interval: float = 1.0

    def __init__(
        self,
        name: str,
        parent: Optional["Daemon"] = None,
        interval: Optional[float] = None,
    ) -> None:
        self.name = name
        self.zone: Optional[ZoneBase] = None
        self.parent = parent
        self.children: list[Daemon] = []
        self.interval = interval if interval is not None \
            else self.default_interval
        self.enabled = True
        self._last_run: float = 0.0
        if parent is not None:
            parent.children.append(self)

    # -----------------------------------------------------------------
    def register_with(self, zone: ZoneBase) -> None:
        self.zone = zone

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------
    def start(self) -> None:
        self.enabled = True

    def stop(self) -> None:
        self.enabled = False

    # -----------------------------------------------------------------
    # Monitoring
    # -----------------------------------------------------------------
    def monitor(self) -> None:
        """Override in subclasses."""
        raise NotImplementedError

    def safe_monitor(self) -> None:
        """Run `monitor` with error isolation."""
        if not self.enabled:
            return
        try:
            self.monitor()
        except Exception:
            log.exception("Daemon %s raised during monitor()", self.name)

    # -----------------------------------------------------------------
    # Signals
    # -----------------------------------------------------------------
    def emit_signal(self, signal: DaemonSignal, payload: dict) -> None:
        if self.parent is not None:
            self.parent.handle_signal(signal, payload, source=self)

    def handle_signal(
        self,
        signal: DaemonSignal,
        payload: dict,
        source: Optional["Daemon"] = None,
    ) -> None:
        try:
            self.on_signal(signal, payload, source)
        except Exception:
            log.exception(
                "Daemon %s raised during on_signal(%s)", self.name, signal
            )
        if self.parent is not None:
            self.parent.handle_signal(signal, payload, source=source)

    def on_signal(
        self,
        signal: DaemonSignal,
        payload: dict,
        source: Optional["Daemon"] = None,
    ) -> None:
        """Override in subclasses."""

    # -----------------------------------------------------------------
    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"