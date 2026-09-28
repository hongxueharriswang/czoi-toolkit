"""
robot_transport.py — Warehouse robot transport simulation.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Exercises:
  * Recursive zone tree (Warehouse → Loading / Storage / Obstacle).
  * Applications and atomic operations (pick / drop / move / report).
  * Roles with base permissions (Transporter, Supervisor, Maintenance).
  * Real CZOA permission calculus (Φ) on every operation attempt.
  * Hierarchical daemons (Δ): FleetDaemon at root, BatteryDaemon and
    ObstacleDaemon as children that signal upward.
  * Attribute-based robot state via PropertyStore.
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

random.seed(42)

# ---- World constants -------------------------------------------------
LOADING_POINT = [10.0, 10.0]
STORAGE_POINT = [90.0, 90.0]
HOME_POINT = [50.0, 50.0]
ARRIVAL_RADIUS = 5.0
BOUNDARY = 100.0


# =====================================================================
# 1. Build the warehouse system
# =====================================================================
def build_system():
    """Construct the recursive zone tree, roles, and operations."""
    builder = CZOABuilder("WarehouseSystem")

    # ---- Zones: Warehouse (composite) with three atomic children ----
    warehouse = builder.add_zone("Warehouse", parent=builder.root)
    loading = builder.add_zone("LoadingZone", parent=warehouse, atomic=True)
    storage = builder.add_zone("StorageZone", parent=warehouse, atomic=True)
    obstacle = builder.add_zone("ObstacleArea", parent=warehouse, atomic=True)

    # ---- Application and atomic operations -------------------------
    app = Application("TransportApp", zone=warehouse)
    pick = app.add_operation(Operation("pick_object"))
    drop = app.add_operation(Operation("drop_object"))
    move = app.add_operation(Operation("move_to"))
    report = app.add_operation(Operation("report_status"))
    warehouse.add_application(app)

    # ---- Roles with base permissions (paper §3, item 2) ------------
    transporter = Role(
        "TransporterRobot",
        zone=warehouse,
        base_permissions=[pick, drop, move],
    )
    supervisor = Role(
        "SupervisorRobot",
        zone=warehouse,
        base_permissions=[report, move],
    )
    maintenance = Role(
        "MaintenanceRobot",
        zone=warehouse,
        base_permissions=[move, report],
    )
    warehouse.add_role(transporter)
    warehouse.add_role(supervisor)
    warehouse.add_role(maintenance)

    ops = {"pick": pick, "drop": drop, "move": move, "report": report}
    return builder, warehouse, loading, storage, obstacle, ops


# =====================================================================
# 2. Create robots, supervisor, maintainer
# =====================================================================
def create_users(builder, warehouse, n_robots: int = 10):
    robots = []
    for i in range(n_robots):
        r = User(
            f"robot_{i}",
            roles={"TransporterRobot"},
            attributes={
                "position": [
                    random.uniform(0, BOUNDARY),
                    random.uniform(0, BOUNDARY),
                ],
                "battery": 100.0,
                "payload": None,
                "speed": random.uniform(1.0, 3.0),
            },
        )
        # Containment principle: parent first, then the zone.
        builder.root.add_user(r)
        warehouse.add_user(r)
        robots.append(r)

    sup = User(
        "supervisor",
        roles={"SupervisorRobot"},
        attributes={"position": list(HOME_POINT), "battery": 100.0,
                    "payload": None, "speed": 1.0},
    )
    builder.root.add_user(sup)
    warehouse.add_user(sup)

    maint = User(
        "maintainer",
        roles={"MaintenanceRobot"},
        attributes={"position": list(LOADING_POINT), "battery": 100.0,
                    "payload": None, "speed": 1.0},
    )
    builder.root.add_user(maint)
    warehouse.add_user(maint)

    return robots, sup, maint


# =====================================================================
# 3. Daemons (Δ)
# =====================================================================
class BatteryDaemon(Daemon):
    """Emits STATE_WARNING for any robot below the battery threshold.

    Runs every simulated second. Signals bubble up to the FleetDaemon.
    """

    def __init__(self, robots, threshold: float = 20.0, parent=None):
        super().__init__("BatteryDaemon", parent=parent, interval=1.0)
        self.robots = robots
        self.threshold = threshold

    def monitor(self):
        for r in self.robots:
            batt = r.attributes.get("battery", 100.0)
            if batt < self.threshold:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"robot": r.name, "battery": round(batt, 2)},
                )


class ObstacleDaemon(Daemon):
    """Detects robots within `threshold` distance of one another."""

    def __init__(self, robots, threshold: float = 3.0, parent=None):
        super().__init__("ObstacleDaemon", parent=parent, interval=1.0)
        self.robots = robots
        self.threshold = threshold

    def monitor(self):
        for i, a in enumerate(self.robots):
            pa = a.attributes.get("position")
            for b in self.robots[i + 1:]:
                pb = b.attributes.get("position")
                if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) < self.threshold:
                    self.emit_signal(
                        DaemonSignal.STATE_CRITICAL,
                        {"robot_a": a.name, "robot_b": b.name},
                    )
                    return  # one alert per tick


class FleetDaemon(Daemon):
    """Root daemon: records signals from children and could issue
    global actions (e.g. rebalancing, emergency stop)."""

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
# 4. Inline simulation
# =====================================================================
class TransportSimulation:
    """Synchronous step-wise simulation.

    Every operation attempt goes through the real CZOI PermissionEngine,
    so the CZOA permission calculus (Φ) is exercised at every step.
    Robots that lack a required operation are denied by the engine
    rather than silently allowed.
    """

    def __init__(self, builder, warehouse, robots):
        self.builder = builder
        self.warehouse = warehouse
        self.robots = robots
        self.objects_in_loading = 20
        self.objects_in_storage = 0
        self.logs: list[tuple] = []
        self.time = 0.0

    # -----------------------------------------------------------------
    def step(self, dt: float = 1.0) -> None:
        self.time += dt
        engine = self.builder.permission_engine
        ops = self.warehouse.operations

        for r in list(self.robots):
            pos = r.attributes.get("position")
            speed = r.attributes.get("speed", 1.0)

            # ---- Random walk within [0, BOUNDARY]^2 ------------------
            pos[0] = max(0.0, min(BOUNDARY,
                                  pos[0] + random.uniform(-1, 1) * speed))
            pos[1] = max(0.0, min(BOUNDARY,
                                  pos[1] + random.uniform(-1, 1) * speed))

            # ---- Try to pick an object at the loading point ----------
            if (self._dist(pos, LOADING_POINT) < ARRIVAL_RADIUS
                    and self.objects_in_loading > 0
                    and r.attributes.get("payload") is None):
                op = ops["TransportApp.pick_object"]
                if engine.decide(r, op, self.warehouse) is Decision.ALLOW:
                    payload = f"obj_{self.objects_in_loading}"
                    r.attributes.set("payload", payload)
                    self.objects_in_loading -= 1
                    self._log(r, "pick", payload)

            # ---- Try to drop the payload at the storage point -------
            if (self._dist(pos, STORAGE_POINT) < ARRIVAL_RADIUS
                    and r.attributes.get("payload") is not None):
                op = ops["TransportApp.drop_object"]
                if engine.decide(r, op, self.warehouse) is Decision.ALLOW:
                    payload = r.attributes.get("payload")
                    self.objects_in_storage += 1
                    r.attributes.set("payload", None)
                    self._log(r, "drop", payload)

            # ---- Battery drain --------------------------------------
            batt = max(0.0, r.attributes.get("battery", 100.0) - 0.1)
            r.attributes.set("battery", batt)
            if batt <= 0.0:
                self._log(r, "dead", None)
                self.robots.remove(r)

    # -----------------------------------------------------------------
    def _log(self, robot: User, action: str, payload):
        self.logs.append((round(self.time, 2), robot.name, action, payload))

    @staticmethod
    def _dist(a, b) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])


# =====================================================================
# 5. Main
# =====================================================================
def main() -> None:
    builder, warehouse, loading, storage, obstacle, ops = build_system()
    robots, supervisor, maintainer = create_users(builder, warehouse, n_robots=10)

    # ---- Daemon hierarchy: FleetDaemon at the root, two children ----
    fleet = FleetDaemon()
    battery = BatteryDaemon(robots, threshold=20.0, parent=fleet)
    obstacle_d = ObstacleDaemon(robots, threshold=3.0, parent=fleet)

    builder.add_daemon(fleet)
    builder.add_daemon(battery)
    builder.add_daemon(obstacle_d)

    # ---- Sanity check: real CZOI permission decisions ---------------
    print("Permission sanity check (paper §3, item 9):")
    print("  transporter  pick :",
          builder.permission_engine.decide(
              robots[0], ops["pick"], warehouse).name)
    print("  supervisor   pick :",
          builder.permission_engine.decide(
              supervisor, ops["pick"], warehouse).name)
    print("  maintainer   pick :",
          builder.permission_engine.decide(
              maintainer, ops["pick"], warehouse).name)
    print("  maintainer   move :",
          builder.permission_engine.decide(
              maintainer, ops["move"], warehouse).name)
    print()

    # ---- Simulation: 600 simulated seconds -------------------------
    sim = TransportSimulation(builder, warehouse, robots)

    for step in range(600):
        sim.step(dt=1.0)
        if step % 5 == 0:                       # daemons every 5 sim-seconds
            builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    print(f"Objects transported : {sim.objects_in_storage}")
    print(f"Objects left in loading zone: {sim.objects_in_loading}")
    print(f"Robots alive        : {len(robots)}")
    print(f"Fleet warnings      : {len(fleet.warnings)}")
    print(f"Fleet criticals     : {len(fleet.criticals)}")

    if fleet.warnings:
        print("\nFirst 3 low-battery warnings:")
        for src, payload in fleet.warnings[:3]:
            print(f"  from {src}: {payload}")

    if fleet.criticals:
        print("\nFirst 3 proximity alerts:")
        for src, payload in fleet.criticals[:3]:
            print(f"  from {src}: {payload}")

    # ---- Permission cache statistics --------------------------------
    stats = builder.permission_engine.stats()
    print(f"\nPermission engine stats: {stats}")


if __name__ == "__main__":
    main()