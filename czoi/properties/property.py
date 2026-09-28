"""Typed attributes for zones, roles, users, and operations.

Properties are the "A" (Attributes) component of the CZOA 10-tuple —
state variables attached to any entity in the system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Property:
    """A single typed attribute."""

    name: str
    value: Any
    type_hint: str = "any"     # "str" | "int" | "float" | "bool" | "any"
    mutable: bool = True

    def __post_init__(self) -> None:
        if self.type_hint == "str" and not isinstance(self.value, str):
            raise TypeError(f"{self.name}: expected str, got {type(self.value)}")
        if self.type_hint == "int" and not isinstance(self.value, int):
            raise TypeError(f"{self.name}: expected int, got {type(self.value)}")
        if self.type_hint == "float" and not isinstance(self.value, (int, float)):
            raise TypeError(f"{self.name}: expected float, got {type(self.value)}")
        if self.type_hint == "bool" and not isinstance(self.value, bool):
            raise TypeError(f"{self.name}: expected bool, got {type(self.value)}")