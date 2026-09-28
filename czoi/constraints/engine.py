"""ConstraintManager (Γ): bridges CZOA to the UniLog toolkit.

The manager is attached to the ROOT of the zone tree and is shared by
every child. Evaluation builds a CZOIModel on demand for the requested
zone, so zone-specific constraints see the correct local state.

Γ = (I, T, G, C) — identity, trigger, goal, access.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from ..core.exceptions import ConstraintError, UniLogBridgeError
from ..core.types import ConstraintKind
from ..operations.operation import Operation
from ..roles.role import Role
from ..roles.user import User
from ..zones.base import ZoneBase

try:
    from unilog.parser import UniLangParser
    from unilog.engine import InferenceEngine, Model, World
    _UNILOG_AVAILABLE = True
except ImportError:                                        # pragma: no cover
    UniLangParser = None                                   # type: ignore
    InferenceEngine = None                                 # type: ignore
    Model = object                                         # type: ignore
    World = object                                         # type: ignore
    _UNILOG_AVAILABLE = False


# ---------------------------------------------------------------------
# UniLog Model backed by a live CZOI zone
# ---------------------------------------------------------------------
class CZOIModel(Model if _UNILOG_AVAILABLE else object):
    """A UniLog Model built from a snapshot of a CZOI zone.

    The model exposes:
      * domains: Zone, Role, User, Operation
      * functions: parent(z)
      * predicates: inZone, childOf, hasRole, canPerform, plus any
        user-registered predicates.
    """

    def __init__(
        self,
        zone: ZoneBase,
        request: Optional[dict] = None,
        extra_predicates: Optional[dict[str, Callable]] = None,
    ) -> None:
        self.zone = zone
        self.request = request or {}
        self._world = World(0)
        self._zones = list(zone.walk())
        self._roles: list[Role] = list(
            {id(r): r for z in self._zones for r in z.roles.values()}.values()
        )
        self._users: list[User] = list(
            {id(u): u for z in self._zones for u in z.users.values()}.values()
        )
        self._ops: list[Operation] = list(
            {id(o): o for z in self._zones for o in z.operations.values()}.values()
        )
        self._extra_predicates = extra_predicates or {}

        # Build a lookup from qualified name -> entity (for term eval).
        self._constants: dict[str, Any] = {}
        for z in self._zones:
            self._constants[z.name] = z
        for r in self._roles:
            self._constants[r.qualified_name] = r
            self._constants[r.name] = r
        for u in self._users:
            self._constants[u.name] = u
        for o in self._ops:
            self._constants[o.qualified_name] = o
            self._constants[o.name] = o

    # -----------------------------------------------------------------
    # UniLog Model interface
    # -----------------------------------------------------------------
    def worlds(self):
        return {self._world}

    def valuation(self, w, atom: str, args: tuple) -> bool:
        return bool(self._dispatch(atom, args))

    def accessibility(self, w, modality, agent=None):
        return {self._world}

    def domain(self):
        return set(self._zones + self._roles + self._users + self._ops)

    def interpret(self, term, assignment):
        """Resolve a term (string, AST constant, or AST variable)."""
        # Bound variable?
        if assignment and term in assignment:
            return assignment[term]
        # Named entity (constant)?
        if isinstance(term, str):
            if term in self._constants:
                return self._constants[term]
            # Fall through: literal
            return term
        # UniLog AST constant node → look up its name
        name = getattr(term, "name", None)
        if name is not None:
            if assignment and name in assignment:
                return assignment[name]
            if name in self._constants:
                return self._constants[name]
            return name
        return term

    def probability(self, world, event):
        return 0.0

    def preference(self, world, w1, w2):
        return False

    # -----------------------------------------------------------------
    # Predicate dispatch
    # -----------------------------------------------------------------
    def _dispatch(self, atom: str, args: tuple) -> bool:
        if atom == "__true__":
            return True

        # User-registered predicates take precedence.
        fn = self._extra_predicates.get(atom)
        if fn is not None:
            try:
                return bool(fn(*args))
            except Exception:
                return False

        if atom == "inZone" and len(args) == 2:
            u, z = args
            return hasattr(z, "users") and getattr(u, "name", None) in z.users
        if atom == "childOf" and len(args) == 2:
            c, p = args
            return getattr(c, "parent", None) is p
        if atom == "hasRole" and len(args) == 2:
            u, r = args
            return getattr(r, "name", None) in getattr(u, "roles", ())
        if atom == "canPerform" and len(args) == 2:
            u, o = args
            engine = self.zone.permission_engine
            if engine is None:
                return False
            return (
                engine.evaluate_local(u, o, self.zone).name == "ALLOW"
            )
        # Closed-world assumption for unknown predicates.
        return False


# ---------------------------------------------------------------------
# ConstraintManager
# ---------------------------------------------------------------------
class ConstraintManager:
    """Γ = (I, T, G, C) — UniLog-backed constraint store."""

    def __init__(self) -> None:
        if not _UNILOG_AVAILABLE:
            raise UniLogBridgeError(
                "The unilog-toolkit is required. "
                "Install with: pip install unilog-toolkit"
            )
        self.root: Optional[ZoneBase] = None
        self.parser = UniLangParser()
        self.engine = InferenceEngine.get_instance()
        self._formulas: dict[ConstraintKind, list[Any]] = {
            k: [] for k in ConstraintKind
        }
        self._extra_predicates: dict[str, Callable] = {}

    # -----------------------------------------------------------------
    def attach(self, zone: ZoneBase) -> None:
        """Attach once at the root. Subsequent attaches are ignored."""
        if self.root is None:
            self.root = zone
        elif self.root is not zone and not self.root.is_ancestor_of(zone):
            raise ConstraintError(
                f"ConstraintManager already bound to {self.root.name!r}; "
                f"cannot attach to unrelated zone {zone.name!r}"
            )

    # -----------------------------------------------------------------
    # User predicates
    # -----------------------------------------------------------------
    def register_predicate(self, name: str, fn: Callable) -> None:
        self._extra_predicates[name] = fn

    # -----------------------------------------------------------------
    # Loading
    # -----------------------------------------------------------------
    def add(
        self,
        kind: ConstraintKind,
        source: str,
        name: Optional[str] = None,
    ) -> Any:
        try:
            formula = self.parser.parse_string(source)
        except Exception as exc:
            raise ConstraintError(
                f"Failed to parse {kind.value} constraint: {exc}"
            ) from exc
        self._formulas[kind].append(formula)
        return formula

    def add_identity(self, source: str) -> Any:
        return self.add(ConstraintKind.IDENTITY, source)

    def add_trigger(self, source: str) -> Any:
        return self.add(ConstraintKind.TRIGGER, source)

    def add_goal(self, source: str) -> Any:
        return self.add(ConstraintKind.GOAL, source)

    def add_access(self, source: str) -> Any:
        return self.add(ConstraintKind.ACCESS, source)

    def count(self, kind: Optional[ConstraintKind] = None) -> int:
        if kind is None:
            return sum(len(v) for v in self._formulas.values())
        return len(self._formulas[kind])

    def clear(self) -> None:
        for v in self._formulas.values():
            v.clear()

    # -----------------------------------------------------------------
    # Evaluation
    # -----------------------------------------------------------------
    def _model(
        self,
        zone: Optional[ZoneBase],
        request: Optional[dict],
    ) -> CZOIModel:
        target = zone or self.root
        if target is None:
            raise ConstraintError("ConstraintManager is not attached")
        return CZOIModel(
            target,
            request=request,
            extra_predicates=self._extra_predicates,
        )

    def check_zone(
        self,
        zone: Optional[ZoneBase] = None,
        request: Optional[dict] = None,
    ) -> dict[str, bool]:
        model = self._model(zone, request)
        results: dict[str, bool] = {}
        for kind, formulas in self._formulas.items():
            ok = True
            for f in formulas:
                try:
                    if not bool(self.engine.evaluate(f, model, model._world)):
                        ok = False
                        break
                except Exception:
                    ok = False
                    break
            results[kind.value] = ok
        return results

    def check_all(self, request: Optional[dict] = None) -> dict[str, bool]:
        """Backward-compatible alias for `check_zone(root)`."""
        return self.check_zone(self.root, request)

    def is_satisfied(
        self,
        user: User,
        operation: Operation,
        zone: ZoneBase,
    ) -> bool:
        """Hook used by PermissionEngine for ACCESS constraints."""
        if self.root is None:
            return True
        request = {"user": user, "op": operation, "zone": zone}
        model = CZOIModel(
            zone,
            request=request,
            extra_predicates=self._extra_predicates,
        )
        for f in self._formulas[ConstraintKind.ACCESS]:
            try:
                if not bool(self.engine.evaluate(f, model, model._world)):
                    return False
            except Exception:
                return False
        return True