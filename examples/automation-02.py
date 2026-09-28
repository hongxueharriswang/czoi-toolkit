"""
warehouse_agv.py — Warehouse AGV fleet simulation.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Exercises:
  * Recursive zone tree: Warehouse → Aisle1 / Aisle2 / Charging / Delivery.
  * Per-zone capacity constraints enforced by a CapacityDaemon.
  * Applications and atomic operations (move, charge, load, unload).
  * Real CZOI permission calculus (Φ) on every AGV action.
  * Hierarchical daemons (Δ): FleetDaemon at root, BatteryDaemon and
    CapacityDaemon as children.
  * Attribute-based AGV state via PropertyStore.
"""
from __future__ import annotations

import math
import random

from czoi import (
    Application,
    CZOABuilder,
    Daemon,
    DaemonSignal,
    Decision,
    Operation,
    Role,
    User,
)

random.seed(7)

# ---- World constants -------------------------------------------------
ZONE_CAPACITY = 5
BATTERY_LOW = 20.0
BATTERY_CHARGE_RATE = 2.0
BATTERY_DRAIN = 0.5


# =====================================================================
# 1. Build the warehouse system
# =====================================================================
def build_system():
    """Construct the zone tree, roles, and operations."""
    builder = CZOABuilder("WarehouseSystem")

    # ---- Zones -----------------------------------------------------
    warehouse = builder.add_zone("Warehouse", parent=builder.root)
    aisle1 = builder.add_zone("Aisle1", parent=warehouse, atomic=True)
    aisle2 = builder.add_zone("Aisle2", parent=warehouse, atomic=True)
    charging = builder.add_zone("ChargingStation", parent=warehouse, atomic=True)
    delivery = builder.add_zone("DeliveryBay", parent=warehouse, atomic=True)

    # Capacity is an attribute of every zone.
    for z in (aisle1, aisle2, charging, delivery):
        z.properties.set("capacity", ZONE_CAPACITY, type_hint="int")

    # ---- Application and atomic operations -------------------------
    app = Application("WarehouseApp", zone=warehouse)
    move = app.add_operation(Operation("move"))
    charge = app.add_operation(Operation("charge"))
    load = app.add_operation(Operation("load_pallet"))
    unload = app.add_operation(Operation("unload_pallet"))
    warehouse.add_application(app)

    # ---- Roles and base permissions --------------------------------
    agv_role = Role(
        "AGV",
        zone=warehouse,
        base_permissions=[move, charge, load, unload],
    )
    manager_role = Role(
        "WarehouseManager",
        zone=warehouse,
        base_permissions=[move],   # read-only; cannot load/unload
    )
    warehouse.add_role(agv_role)
    warehouse.add_role(manager_role)

    ops = {
        "move": move,
        "charge": charge,
        "load": load,
        "unload": unload,
    }
    zones = {
        "warehouse": warehouse,
        "aisle1": aisle1,
        "aisle2": aisle2,
        "charging": charging,
        "delivery": delivery,
    }
    return builder, zones, ops


# =====================================================================
# 2. Create AGVs and the manager
# =====================================================================
def create_users(builder, warehouse, n_agvs: int = 8):
    agvs = []
    for i in range(n_agvs):
        agv = User(
            f"AGV_{i}",
            roles={"AGV"},
            attributes={
                "battery": 100.0,
                "position": ("Aisle1", random.uniform(0.0, 10.0)),
                "task": None,
            },
        )
        builder.root.add_user(agv)
        warehouse.add_user(agv)
        agvs.append(agv)

    manager = User(
        "manager",
        roles={"WarehouseManager"},
        attributes={"position": ("Warehouse", 0.0)},
    )
    builder.root.add_user(manager)
    warehouse.add_user(manager)
    return agvs, manager


# =====================================================================
# 3. Daemons (Δ)
# =====================================================================
class BatteryDaemon(Daemon):
    """Signals STATE_WARNING when an AGV's battery drops below threshold."""

    def __init__(self, agvs, threshold: float = BATTERY_LOW, parent=None):
        super().__init__("BatteryDaemon", parent=parent, interval=1.0)
        self.agvs = agvs
        self.threshold = threshold

    def monitor(self):
        for agv in self.agvs:
            batt = agv.attributes.get("battery", 100.0)
            if batt < self.threshold:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"agv": agv.name, "battery": round(batt, 2)},
                )


class CapacityDaemon(Daemon):
    """Detects zones whose current occupancy exceeds capacity.

    Occupancy is computed from the `position` attribute of every AGV.
    """

    def __init__(self, zones, agvs, parent=None):
        super().__init__("CapacityDaemon", parent=parent, interval=1.0)
        self.zones = zones
        self.agvs = agvs

    def monitor(self):
        for name, zone in self.zones.items():
            if name == "warehouse":
                continue
            cap = zone.properties.get("capacity", ZONE_CAPACITY)
            occupancy = sum(
                1 for a in self.agvs
                if a.attributes.get("position", (None,))[0] == zone.name
            )
            if occupancy > cap:
                self.emit_signal(
                    DaemonSignal.STATE_CRITICAL,
                    {"zone": zone.name, "occupancy": occupancy, "capacity": cap},
                )


class FleetDaemon(Daemon):
    """Root daemon: records signals and could trigger global responses."""

    def __init__(self, parent=None):
        super().__init__("FleetDaemon", parent=parent, interval=2.0)
        self.warnings: list[tuple] = []
        self.criticals: list[tuple] = []

    def on_signal(self, signal, payload, source=None):
        src = source.name if source is not None else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))


# =====================================================================
# 4. Simulation
# =====================================================================
class WarehouseSimulation:
    """Cyclic AGV workflow: Delivery → Aisle → (charge if low) → repeat.

    Every load/unload/charge decision goes through the real CZOI
    PermissionEngine. If an AGV lacks an operation, the engine refuses
    and the AGV idles (this never happens for AGVs, but does for the
    manager, whose role lacks load/unload).
    """

    def __init__(self, builder, zones, ops, agvs):
        self.builder = builder
        self.zones = zones
        self.ops = ops
        self.agvs = agvs
        self.pallets_in = 50
        self.pallets_out = 0
        self.time = 0.0
        self.logs: list[tuple] = []

    # -----------------------------------------------------------------
    def step(self, dt: float = 10.0) -> None:
        self.time += dt
        engine = self.builder.permission_engine
        warehouse = self.zones["warehouse"]

        for agv in list(self.agvs):
            pos_name, pos_x = agv.attributes.get("position", ("Aisle1", 0.0))
            task = agv.attributes.get("task")
            battery = agv.attributes.get("battery", 100.0)

            # ---- Low battery → divert to ChargingStation -----------
            if battery < BATTERY_LOW and pos_name != "ChargingStation":
                agv.attributes.set("position", ("ChargingStation", 0.0))
                self._log(agv, "move_to_charge", None)
                continue

            # ---- At ChargingStation → charge -----------------------
            if pos_name == "ChargingStation":
                op = self.ops["charge"]
                if engine.decide(agv, op, warehouse) is Decision.ALLOW:
                    new_batt = min(100.0, battery + BATTERY_CHARGE_RATE)
                    agv.attributes.set("battery", new_batt)
                    self._log(agv, "charge", round(new_batt, 1))
                if agv.attributes.get("battery", 0) >= 95.0:
                    agv.attributes.set("position", ("Aisle1", 0.0))
                continue

            # ---- No task → go to Delivery Bay ----------------------
            if task is None:
                if pos_name != "DeliveryBay":
                    agv.attributes.set("position", ("DeliveryBay", 0.0))
                    self._log(agv, "move_to_delivery", None)
                    continue
                # At delivery, try to load
                if self.pallets_in > 0:
                    op = self.ops["load"]
                    if engine.decide(agv, op, warehouse) is Decision.ALLOW:
                        pallet = f"pallet_{self.pallets_in}"
                        agv.attributes.set("task", pallet)
                        self.pallets_in -= 1
                        self._log(agv, "load", pallet)
                else:
                    self._log(agv, "idle_no_pallets", None)
                continue

            # ---- Has task → go to an aisle -------------------------
            if pos_name not in ("Aisle1", "Aisle2"):
                target = random.choice(["Aisle1", "Aisle2"])
                agv.attributes.set("position", (target, random.uniform(0.0, 10.0)))
                self._log(agv, "move_to_aisle", target)
                continue

            # At aisle, try to unload
            op = self.ops["unload"]
            if engine.decide(agv, op, warehouse) is Decision.ALLOW:
                if random.random() < 0.4:
                    self.pallets_out += 1
                    self._log(agv, "unload", task)
                    agv.attributes.set("task", None)

            # ---- Battery drain -------------------------------------
            batt = max(0.0, agv.attributes.get("battery", 100.0) - BATTERY_DRAIN)
            agv.attributes.set("battery", batt)

    # -----------------------------------------------------------------
    def _log(self, agv: User, action: str, payload):
        self.logs.append((round(self.time, 1), agv.name, action, payload))


# =====================================================================
# 5. Main
# =====================================================================
def main() -> None:
    builder, zones, ops = build_system()
    agvs, manager = create_users(builder, zones["warehouse"], n_agvs=8)

    # ---- Daemon hierarchy: FleetDaemon at root, two children --------
    fleet = FleetDaemon()
    battery = BatteryDaemon(agvs, threshold=BATTERY_LOW, parent=fleet)
    capacity = CapacityDaemon(
        {k: v for k, v in zones.items() if k != "warehouse"},
        agvs,
        parent=fleet,
    )
    builder.add_daemon(fleet)
    builder.add_daemon(battery)
    builder.add_daemon(capacity)

    # ---- Sanity check: real CZOI permission decisions ---------------
    warehouse = zones["warehouse"]
    engine = builder.permission_engine
    print("Permission sanity check (paper §3, item 9):")
    print("  AGV_0   load   :", engine.decide(agvs[0], ops["load"], warehouse).name)
    print("  AGV_0   unload :", engine.decide(agvs[0], ops["unload"], warehouse).name)
    print("  manager load   :", engine.decide(manager, ops["load"], warehouse).name)
    print("  manager move   :", engine.decide(manager, ops["move"], warehouse).name)
    print()

    # ---- Simulation: 30 minutes at 10-second steps -----------------
    sim = WarehouseSimulation(builder, zones, ops, agvs)
    steps = 30 * 6                          # 30 min / 10 s = 180 steps
    for s in range(steps):
        sim.step(dt=10.0)
        if s % 3 == 0:                      # daemons every 30 sim-seconds
            builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    print(f"Pallets loaded   : {50 - sim.pallets_in}")
    print(f"Pallets unloaded : {sim.pallets_out}")
    print(f"Pallets still in delivery: {sim.pallets_in}")
    print(f"AGVs tracked     : {len(agvs)}")
    print(f"Fleet warnings   : {len(fleet.warnings)}")
    print(f"Fleet criticals  : {len(fleet.criticals)}")

    if fleet.criticals:
        print("\nFirst 3 capacity alerts:")
        for src, payload in fleet.criticals[:3]:
            print(f"  from {src}: {payload}")

    if fleet.warnings:
        print("\nFirst 3 low-battery warnings:")
        for src, payload in fleet.warnings[:3]:
            print(f"  from {src}: {payload}")

    print(f"\nPermission engine stats: {engine.stats()}")


if __name__ == "__main__":
    main()