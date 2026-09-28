"""Factory: fluent builder for complete CZOA systems."""
from __future__ import annotations

from typing import Optional

from ..constraints.engine import ConstraintManager
from ..daemons.manager import DaemonManager
from ..embedding.service import EmbeddingService
from ..permissions.engine import PermissionEngine
from ..zones.base import ZoneBase
from ..zones.atomic import AtomicZone
from ..zones.composite import CompositeZone


class CZOABuilder:
    """Wires together a complete CZOA system."""

    def __init__(self, name: str) -> None:
        self.root = CompositeZone(name=name)
        self.permission_engine = PermissionEngine()
        self.constraint_manager = ConstraintManager()
        self.daemon_manager = DaemonManager()
        self.embedding_service = EmbeddingService()

        # Attach infrastructure to the root; children inherit via
        # _inherit_into.
        self.root.set_permission_engine(self.permission_engine)
        self.root.set_constraints(self.constraint_manager)
        self.root.set_embeddings(self.embedding_service)

    # -----------------------------------------------------------------
    def add_zone(
        self,
        name: str,
        parent: Optional[ZoneBase] = None,
        atomic: bool = False,
    ) -> ZoneBase:
        parent = parent or self.root
        cls = AtomicZone if atomic else CompositeZone
        # Inheritance of engine/constraints/embeddings happens in
        # ZoneBase._inherit_into when the child is registered.
        return cls(name=name, parent=parent)

    # -----------------------------------------------------------------
    def add_access_constraint(self, source: str) -> None:
        self.constraint_manager.add_access(source)

    def add_identity_constraint(self, source: str) -> None:
        self.constraint_manager.add_identity(source)

    def add_trigger_constraint(self, source: str) -> None:
        self.constraint_manager.add_trigger(source)

    def add_goal_constraint(self, source: str) -> None:
        self.constraint_manager.add_goal(source)

    def register_predicate(self, name: str, fn) -> None:
        self.constraint_manager.register_predicate(name, fn)

    # -----------------------------------------------------------------
    def add_daemon(self, daemon) -> None:
        self.root.add_daemon(daemon)
        self.daemon_manager.add(daemon)

    # -----------------------------------------------------------------
    def build(self) -> ZoneBase:
        return self.root