"""ZoneBase: the recursive CZOA 10-tuple.

    S = (Z, R, U, A, O, N, E, Γ, Φ, Δ)

Every zone is a full CZOA system (paper §3, Definition 1).
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..core.exceptions import ZoneContainmentError, ZoneError
from ..operations.operation import Operation
from ..properties.store import PropertyStore
from ..roles.application import Application
from ..roles.role import Role
from ..roles.user import User


class ZoneBase:
    """Base class shared by AtomicZone and CompositeZone."""

    def __init__(
        self,
        name: str,
        parent: ZoneBase | None = None,
        properties: dict | None = None,
    ) -> None:
        if not name:
            raise ValueError("Zone name must be non-empty")

        self.name = name
        self.parent: ZoneBase | None = parent
        self.properties = PropertyStore(properties)

        # ---- The 10-tuple ---------------------------------------
        self.zones: dict[str, ZoneBase] = {}             # Z
        self.roles: dict[str, Role] = {}                 # R
        self.users: dict[str, User] = {}                 # U
        self.applications: dict[str, Application] = {}   # A
        self.operations: dict[str, Operation] = {}       # O
        self.neural: dict[str, Any] = {}                 # N
        self.embeddings: Any = None                      # E
        self.constraints: Any = None                     # Γ
        self.permission_engine: Any = None               # Φ
        self.daemons: list[Any] = []                     # Δ

        if parent is not None:
            parent._register_child(self)

    # -----------------------------------------------------------------
    # Z — zones
    # -----------------------------------------------------------------
    def _register_child(self, child: ZoneBase) -> None:
        if child.parent is not None and child.parent is not self:
            raise ZoneError(
                f"{child.name!r} already belongs to {child.parent.name!r}"
            )
        child.parent = self
        self.zones[child.name] = child
        self._inherit_into(child)

    def _inherit_into(self, child: ZoneBase) -> None:
        """Containment principle: roles/operations inherit downward."""
        for rn, r in self.roles.items():
            child.roles.setdefault(rn, r)
        for on, op in self.operations.items():
            child.operations.setdefault(on, op)
        # Share the infrastructure (engine, constraints, embeddings).
        child.permission_engine = self.permission_engine
        child.constraints = self.constraints
        child.embeddings = self.embeddings

    def add_zone(self, child: ZoneBase) -> ZoneBase:
        self._register_child(child)
        return child

    def walk(self) -> Iterator[ZoneBase]:
        yield self
        for c in self.zones.values():
            yield from c.walk()

    def ancestry(self) -> list[ZoneBase]:
        out, node = [], self
        while node is not None:
            out.append(node)
            node = node.parent
        return list(reversed(out))

    def is_ancestor_of(self, other: ZoneBase) -> bool:
        node = other.parent
        while node is not None:
            if node is self:
                return True
            node = node.parent
        return False

    def depth(self) -> int:
        return len(self.ancestry()) - 1

    # -----------------------------------------------------------------
    # R — roles
    # -----------------------------------------------------------------
    def add_role(self, role: Role) -> Role:
        if role.name in self.roles and self.roles[role.name] is not role:
            raise ZoneError(
                f"Role {role.name!r} already defined in {self.name!r}"
            )
        role.zone = self
        self.roles[role.name] = role
        for c in self.zones.values():
            c.roles.setdefault(role.name, role)
        self._invalidate_cache()
        return role

    def get_role(self, name: str) -> Role:
        try:
            return self.roles[name]
        except KeyError:
            raise ZoneError(
                f"Unknown role {name!r} in zone {self.name!r}"
            ) from None

    # -----------------------------------------------------------------
    # U — users
    # -----------------------------------------------------------------
    def add_user(self, user: User) -> User:
        if self.parent is not None and user.name not in self.parent.users:
            raise ZoneContainmentError(
                f"User {user.name!r} must be affiliated with parent "
                f"{self.parent.name!r} (containment principle)"
            )
        user.zone = self
        self.users[user.name] = user
        self._invalidate_cache()
        return user

    # -----------------------------------------------------------------
    # A / O
    # -----------------------------------------------------------------
    def add_application(self, app: Application) -> Application:
        app.zone = self
        self.applications[app.name] = app
        for op in app.operations.values():
            self.operations[op.qualified_name] = op
        return app

    def add_operation(self, op: Operation) -> Operation:
        self.operations[op.qualified_name] = op
        return op

    def get_operation(self, name: str) -> Operation:
        try:
            return self.operations[name]
        except KeyError:
            raise ZoneError(
                f"Unknown operation {name!r} in zone {self.name!r}"
            ) from None

    # -----------------------------------------------------------------
    # Role mutation helpers that invalidate the permission cache
    # -----------------------------------------------------------------
    def grant(self, role: Role, op: Operation) -> None:
        role.grant(op)
        self._invalidate_cache()

    def revoke(self, role: Role, op: Operation) -> None:
        role.revoke(op)
        self._invalidate_cache()

    # -----------------------------------------------------------------
    # N, E, Γ, Φ, Δ
    # -----------------------------------------------------------------
    def add_neural(self, name: str, component: Any) -> None:
        self.neural[name] = component

    def set_embeddings(self, service: Any) -> None:
        self.embeddings = service
        for c in self.zones.values():
            c.set_embeddings(service)

    def set_constraints(self, manager: Any) -> None:
        self.constraints = manager
        attach = getattr(manager, "attach", None)
        if callable(attach):
            attach(self)
        for c in self.zones.values():
            c.set_constraints(manager)

    def set_permission_engine(self, engine: Any) -> None:
        self.permission_engine = engine
        for c in self.zones.values():
            c.permission_engine = engine

    def add_daemon(self, daemon: Any) -> None:
        self.daemons.append(daemon)
        register = getattr(daemon, "register_with", None)
        if callable(register):
            register(self)

    # -----------------------------------------------------------------
    def _invalidate_cache(self) -> None:
        engine = self.permission_engine
        if engine is not None:
            invalidate = getattr(engine, "invalidate", None)
            if callable(invalidate):
                invalidate()

    # -----------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}({self.name!r}, "
            f"zones={len(self.zones)}, roles={len(self.roles)}, "
            f"users={len(self.users)}, ops={len(self.operations)})"
        )