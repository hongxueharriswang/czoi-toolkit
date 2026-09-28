"""Role: a job function defined in a specific zone.

The intra-zone seniority relation is modelled by `junior_roles`
(``self >=_z junior``). Roles are inherited downward through the
zone tree.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..operations.operation import Operation
from ..properties.store import PropertyStore

if TYPE_CHECKING:
    from ..zones.base import ZoneBase


class Role:
    __slots__ = (
        "base_permissions",
        "junior_roles",
        "name",
        "properties",
        "zone",
    )

    def __init__(
        self,
        name: str,
        zone: ZoneBase | None = None,
        base_permissions: list[Operation] | None = None,
        properties: dict | None = None,
    ) -> None:
        if not name:
            raise ValueError("Role name must be non-empty")
        self.name = name
        self.zone = zone
        self.base_permissions: set[Operation] = set(base_permissions or [])
        self.junior_roles: set[Role] = set()
        self.properties = PropertyStore(properties)

    # ---- Permissions ---------------------------------------------
    def grant(self, op: Operation) -> None:
        self.base_permissions.add(op)

    def revoke(self, op: Operation) -> None:
        self.base_permissions.discard(op)

    # ---- Seniority -----------------------------------------------
    def add_junior(self, junior: Role) -> None:
        self.junior_roles.add(junior)

    # ---- Identity ------------------------------------------------
    @property
    def qualified_name(self) -> str:
        return self.name if self.zone is None \
            else f"{self.zone.name}:{self.name}"

    def __repr__(self) -> str:
        return (
            f"Role({self.qualified_name!r}, "
            f"perms={len(self.base_permissions)}, "
            f"juniors={len(self.junior_roles)})"
        )

    def __hash__(self) -> int:
        return id(self)