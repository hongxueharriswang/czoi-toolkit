"""Application: a structural module that groups related operations."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..operations.operation import Operation
from ..properties.store import PropertyStore

if TYPE_CHECKING:
    from ..zones.base import ZoneBase


class Application:
    """A deployable module exposing a set of atomic operations."""

    __slots__ = ("name", "operations", "properties", "zone")

    def __init__(
        self,
        name: str,
        zone: ZoneBase | None = None,
        properties: dict | None = None,
    ) -> None:
        if not name:
            raise ValueError("Application name must be non-empty")
        self.name = name
        self.zone = zone
        self.operations: dict[str, Operation] = {}
        self.properties = PropertyStore(properties)

    def add_operation(self, op: Operation) -> Operation:
        if op.application is not None and op.application is not self:
            raise ValueError(
                f"Operation {op.name!r} already belongs to "
                f"{op.application.name!r}"
            )
        op.application = self
        self.operations[op.name] = op
        return op

    def __repr__(self) -> str:
        return f"Application({self.name!r}, ops={len(self.operations)})"