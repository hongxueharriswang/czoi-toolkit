"""PermissionEngine (Φ): the two-stage recursive decision function.

    P_effective(r, z) =
        P_base^z(r)
        ∪ ⋃_{r' ∈ seniority_z(r)} P_base^z(r')
        ∪ ⋃_{z_child ∈ Z_z} γ(z_child, r)
        ∪ Φ_parent^{-1}(r, z)

Paper §3, item 9.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ..core.types import Decision
from ..operations.operation import Operation
from ..roles.role import Role
from ..roles.user import User
from ..zones.base import ZoneBase


# ---------------------------------------------------------------------
# Audit record
# ---------------------------------------------------------------------
@dataclass
class DecisionRecord:
    timestamp: datetime
    user: str
    operation: str
    zone: str
    decision: Decision
    stage: str          # "local" | "parent-override" | "root-deny"
    reason: str = ""


# ---------------------------------------------------------------------
# Neural contribution hook
# ---------------------------------------------------------------------
class NeuralContribution:
    """Optional callable that contributes to a permission decision.

    Signature: `(user, operation, zone, base_decision) -> Decision`
    """

    def __init__(self, fn) -> None:
        self.fn = fn

    def __call__(self, user, operation, zone, base) -> Decision:
        return self.fn(user, operation, zone, base)


# ---------------------------------------------------------------------
# PermissionEngine
# ---------------------------------------------------------------------
class PermissionEngine:
    """Recursive two-stage permission calculus with caching and audit."""

    def __init__(
        self,
        cache_enabled: bool = True,
        audit_enabled: bool = False,
    ) -> None:
        self.cache_enabled = cache_enabled
        self.audit_enabled = audit_enabled
        self._cache: dict[tuple[int, int, int], Decision] = {}
        self._stats = {"hits": 0, "misses": 0, "parent_lookups": 0, "denies": 0}
        self.audit: list[DecisionRecord] = []
        self._neural: Optional[NeuralContribution] = None

    # -----------------------------------------------------------------
    # Configuration
    # -----------------------------------------------------------------
    def set_neural_contribution(
        self, contribution: Optional[NeuralContribution]
    ) -> None:
        self._neural = contribution

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    def decide(
        self,
        user: User,
        operation: Operation,
        zone: ZoneBase,
    ) -> Decision:
        key = (id(user), id(operation), id(zone))
        if self.cache_enabled and key in self._cache:
            self._stats["hits"] += 1
            decision = self._cache[key]
            self._record(user, operation, zone, decision, "cache")
            return decision

        self._stats["misses"] += 1
        decision, stage = self._decide_recursive(user, operation, zone)

        if self.cache_enabled:
            self._cache[key] = decision
        if decision is Decision.DENY:
            self._stats["denies"] += 1
        self._record(user, operation, zone, decision, stage)
        return decision

    def evaluate_local(
        self,
        user: User,
        operation: Operation,
        zone: ZoneBase,
    ) -> Decision:
        """Public single-stage decision — used by CZOIModel.canPerform."""
        return self._local_decide(user, operation, zone)

    def invalidate(self) -> None:
        self._cache.clear()

    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    # -----------------------------------------------------------------
    # Recursion
    # -----------------------------------------------------------------
    def _decide_recursive(
        self,
        user: User,
        operation: Operation,
        zone: ZoneBase,
    ) -> tuple[Decision, str]:
        local = self._local_decide(user, operation, zone)

        # Apply neural contribution if configured (paper §5.3).
        if self._neural is not None and local is Decision.ALLOW:
            local = self._neural(user, operation, zone, local)

        if local is not Decision.INCONCLUSIVE:
            return local, "local"

        if zone.parent is None:
            return Decision.DENY, "root-deny"

        self._stats["parent_lookups"] += 1
        decision, _ = self._decide_recursive(user, operation, zone.parent)
        return decision, "parent-override"

    # -----------------------------------------------------------------
    def _local_decide(
        self,
        user: User,
        operation: Operation,
        zone: ZoneBase,
    ) -> Decision:
        roles = self._roles_in_zone(user, zone)
        if not roles:
            return Decision.INCONCLUSIVE

        effective = self._effective_permissions(roles)
        if operation not in effective:
            return Decision.INCONCLUSIVE

        # Evaluate access constraints (kind == C).
        if zone.constraints is not None:
            checker = getattr(zone.constraints, "is_satisfied", None)
            if callable(checker) and not checker(user, operation, zone):
                return Decision.DENY

        return Decision.ALLOW

    # -----------------------------------------------------------------
    def _roles_in_zone(self, user: User, zone: ZoneBase) -> set[Role]:
        return {zone.roles[n] for n in user.roles if n in zone.roles}

    def _effective_permissions(self, roles: set[Role]) -> set[Operation]:
        perms: set[Operation] = set()
        seen: set[Role] = set()
        stack = list(roles)
        while stack:
            r = stack.pop()
            if r in seen:
                continue
            seen.add(r)
            perms |= r.base_permissions
            stack.extend(r.junior_roles)
        return perms

    # -----------------------------------------------------------------
    def _record(
        self,
        user: User,
        operation: Operation,
        zone: ZoneBase,
        decision: Decision,
        stage: str,
    ) -> None:
        if not self.audit_enabled:
            return
        self.audit.append(DecisionRecord(
            timestamp=datetime.now(timezone.utc),
            user=user.name,
            operation=operation.qualified_name,
            zone=zone.name,
            decision=decision,
            stage=stage,
        ))