"""Operation: an atomic executable action.

Permissions are granted on Operations, never on Applications. This
preserves the orthogonality of the CZOA 10-tuple (paper §3, item 5).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..properties.store import PropertyStore

if TYPE_CHECKING:
    from ..roles.application import Application


class Operation:
    """An atomic executable action identified by application.operation."""

    __slots__ = ("application", "name", "properties")

    def __init__(
        self,
        name: str,
        application: Application | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if not name:
            raise ValueError("Operation name must be non-empty")
        self.name = name
        self.application = application
        self.properties = PropertyStore(properties)

    @property
    def qualified_name(self) -> str:
        return self.name if self.application is None \
            else f"{self.application.name}.{self.name}"

    def __repr__(self) -> str:
        return f"Operation({self.qualified_name!r})"

    def __hash__(self) -> int:
        return hash(self.qualified_name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Operation) \
            and self.qualified_name == other.qualified_name