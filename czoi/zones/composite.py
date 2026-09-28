"""CompositeZone: a zone that owns child zones.

Provides composition utilities mirroring the categorical operations
of CZOA_Rec (paper §4).
"""
from __future__ import annotations

import copy

from .base import ZoneBase


class CompositeZone(ZoneBase):
    """A zone that owns zero or more child zones."""

    def __init__(
        self,
        name: str,
        parent: ZoneBase | None = None,
        properties: dict | None = None,
    ) -> None:
        super().__init__(name, parent, properties)

    # -----------------------------------------------------------------
    # Categorical helpers
    # -----------------------------------------------------------------
    def clone(self, name: str | None = None) -> CompositeZone:
        """Structural clone — deep-copies roles, operations, properties."""
        new = CompositeZone(
            name=name or f"{self.name}_copy",
            properties=copy.deepcopy(self.properties.as_dict()),
        )
        # Copy roles (same Operation objects — operations are shared).
        for rn, r in self.roles.items():
            new_role = type(r)(
                name=r.name,
                base_permissions=list(r.base_permissions),
                properties=copy.deepcopy(r.properties.as_dict()),
            )
            new.add_role(new_role)
        # Re-wire junior relationships within the clone.
        for rn, r in self.roles.items():
            for jr in r.junior_roles:
                if jr.name in new.roles:
                    new.roles[rn].add_junior(new.roles[jr.name])
        # Recursively clone children.
        for child in self.zones.values():
            new_child = child.clone(name=child.name)
            new.add_zone(new_child)
        return new

    def product_with(
        self,
        other: ZoneBase,
        name: str,
        parent: ZoneBase | None = None,
    ) -> CompositeZone:
        """Parallel composition (categorical product).

        The result is a new CompositeZone containing clones of both
        operands as children. Originals are untouched.
        """
        composed = CompositeZone(name=name, parent=parent)
        composed.add_zone(self.clone(name=self.name))
        composed.add_zone(
            other.clone(name=other.name)
            if isinstance(other, CompositeZone)
            else CompositeZone(name=other.name, parent=composed)
        )
        return composed

    def as_tree_dict(self) -> dict:
        """F_tree: CZOA_Rec → Tree."""
        return {
            "zone": self.name,
            "roles": sorted(self.roles),
            "operations": sorted(self.operations),
            "children": [c.as_tree_dict() for c in self.zones.values()],
        }