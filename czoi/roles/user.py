"""User: an authenticated identity with zone affiliation and roles."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..properties.store import PropertyStore

if TYPE_CHECKING:
    from ..zones.base import ZoneBase


class User:
    __slots__ = ("attributes", "credentials", "name", "roles", "zone")

    def __init__(
        self,
        name: str,
        zone: ZoneBase | None = None,
        roles: set[str] | None = None,
        attributes: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
    ) -> None:
        if not name:
            raise ValueError("User name must be non-empty")
        self.name = name
        self.zone = zone
        self.roles = set(roles or ())
        self.attributes = PropertyStore(attributes)
        self.credentials = credentials or {}

    def has_role(self, name: str) -> bool:
        return name in self.roles

    def __repr__(self) -> str:
        return f"User({self.name!r}, roles={sorted(self.roles)!r})"

    def __hash__(self) -> int:
        return id(self)