"""CZOI exception hierarchy."""


class CZOIError(Exception):
    """Base class for all CZOI errors."""


# ---- Zone layer --------------------------------------------------
class ZoneError(CZOIError):
    """Zone-hierarchy violations (containment, inheritance)."""


class ZoneContainmentError(ZoneError):
    """A child zone violated the containment principle U_child ⊆ U_parent."""


class ZoneRecursionError(ZoneError):
    """A cycle was introduced in the zone tree."""


# ---- Roles / users / apps ---------------------------------------
class RoleError(CZOIError):
    """Role-definition or seniority problems."""


class UserError(CZOIError):
    """User-identity or affiliation problems."""


class ApplicationError(CZOIError):
    """Application / operation problems."""


# ---- Permissions / constraints ----------------------------------
class PermissionError(CZOIError):
    """Permission-calculus violations."""


class ConstraintError(CZOIError):
    """Constraint-manager problems."""


class SafetyViolation(CZOIError):
    """An adaptive update violated a safety invariant (Theorem 7)."""


# ---- UniLog bridge ----------------------------------------------
class UniLogBridgeError(CZOIError):
    """Raised when the UniLog toolkit cannot be used."""