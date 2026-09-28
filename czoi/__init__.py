"""CZOI — Constrained Zoned-Object Implementation toolkit.

Reference implementation of the Constrained Zoned-Object Architecture
(CZOA) integrating the UniLog toolkit for formal constraint
specification and evaluation.

Paper: H. Wang, "Constrained Zoned-Object Architecture (CZOA):
A Unified Framework for Building Secure and Intelligent Integrated
Organizational Systems", 2026.
"""
from .constraints.engine import ConstraintManager, CZOIModel
from .core.exceptions import (
    ApplicationError,
    ConstraintError,
    CZOIError,
    PermissionError,
    RoleError,
    SafetyViolation,
    UniLogBridgeError,
    UserError,
    ZoneContainmentError,
    ZoneError,
    ZoneRecursionError,
)
from .core.types import ConstraintKind, DaemonSignal, Decision
from .daemons.base import Daemon
from .daemons.manager import DaemonManager
from .embedding.service import EmbeddingService
from .neural.components import AnomalyDetector, MiningResult, Predictor, RoleMiner
from .operations.operation import Operation
from .permissions.engine import PermissionEngine
from .properties.property import Property
from .properties.store import PropertyStore
from .roles.application import Application
from .roles.role import Role
from .roles.user import User
from .toolkit.factory import CZOABuilder
from .zones.atomic import AtomicZone
from .zones.base import ZoneBase
from .zones.composite import CompositeZone

__version__ = "1.0.0"

__all__ = [
    "AnomalyDetector",
    "Application",
    "ApplicationError",
    "AtomicZone",
    "CZOABuilder",
    # Exceptions
    "CZOIError",
    "CZOIModel",
    "CompositeZone",
    "ConstraintError",
    "ConstraintKind",
    "ConstraintManager",
    "Daemon",
    "DaemonManager",
    "DaemonSignal",
    # Types
    "Decision",
    "EmbeddingService",
    "MiningResult",
    "Operation",
    # Runtime
    "PermissionEngine",
    "PermissionError",
    "Predictor",
    # Entities
    "Property",
    "PropertyStore",
    "Role",
    "RoleError",
    "RoleMiner",
    "SafetyViolation",
    "UniLogBridgeError",
    "User",
    "UserError",
    # Zones
    "ZoneBase",
    "ZoneContainmentError",
    "ZoneError",
    "ZoneRecursionError",
]