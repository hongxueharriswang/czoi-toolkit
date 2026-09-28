"""PropertyStore: dictionary-like container for Property instances."""
from __future__ import annotations

from typing import Any, Iterator

from .property import Property


class PropertyStore:
    """A collection of named properties with typed access."""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._props: dict[str, Property] = {}
        if initial:
            for k, v in initial.items():
                self.set(k, v)

    def set(self, name: str, value: Any, type_hint: str = "any") -> None:
        self._props[name] = Property(name=name, value=value, type_hint=type_hint)

    def get(self, name: str, default: Any = None) -> Any:
        p = self._props.get(name)
        return p.value if p is not None else default

    def property(self, name: str) -> Property | None:
        return self._props.get(name)

    def remove(self, name: str) -> None:
        self._props.pop(name, None)

    def __contains__(self, name: str) -> bool:
        return name in self._props

    def __iter__(self) -> Iterator[str]:
        return iter(self._props)

    def items(self):
        return ((n, p.value) for n, p in self._props.items())

    def as_dict(self) -> dict[str, Any]:
        return {n: p.value for n, p in self._props.items()}

    def __repr__(self) -> str:
        return f"PropertyStore({self.as_dict()!r})"