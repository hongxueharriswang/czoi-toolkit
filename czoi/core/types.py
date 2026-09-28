"""Core types: Decision enum, PermissionTarget, etc."""
from __future__ import annotations

from enum import Enum
from typing import Union


class Decision(Enum):
    """Two-stage permission calculus result (paper §3, item 9)."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    INCONCLUSIVE = "INCONCLUSIVE"


class ConstraintKind(Enum):
    """The four constraint types from Γ = (I, T, G, C)."""

    IDENTITY = "I"
    TRIGGER = "T"
    GOAL = "G"
    ACCESS = "C"


class DaemonSignal(Enum):
    """Standard cross-daemon signalling tokens (paper §5.4)."""

    STATE_NORMAL = "STATE_NORMAL"
    STATE_WARNING = "STATE_WARNING"
    STATE_CRITICAL = "STATE_CRITICAL"
    REVOKE = "REVOKE"
    ESCALATE = "ESCALATE"


# Type aliases used in annotations
PermissionTarget = "Operation"  # forward ref; permissions are always on operations
Weight = float                   # in [0, 1]