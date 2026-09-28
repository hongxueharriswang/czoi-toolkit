# czoi/core/composition.py
def compose_systems(sys1: System, sys2: System, name: str) -> System:
    """Compose two CZOA systems into a new system (product)."""
    new_system = System(name)
    new_system.zones = {**sys1.zones, **sys2.zones}
    new_system.roles = {**sys1.roles, **sys2.roles}
    # ... merge other components
    return new_system