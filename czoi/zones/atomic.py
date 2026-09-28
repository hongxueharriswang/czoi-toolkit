"""AtomicZone: a leaf subsystem (Z_z = empty)."""
from __future__ import annotations

from typing import Optional

from .base import ZoneBase


class AtomicZone(ZoneBase):
    """A zone with no children; the recursion terminates here."""

    def __init__(
        self,
        name: str,
        parent: Optional[ZoneBase] = None,
        properties: Optional[dict] = None,
    ) -> None:
        super().__init__(name, parent, properties)

    def add_zone(self, child: ZoneBase) -> ZoneBase:
        raise TypeError(
            f"AtomicZone {self.name!r} cannot have child zones; "
            "use CompositeZone instead"
        )